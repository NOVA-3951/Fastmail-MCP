#!/usr/bin/env python3
import os
import asyncio
import httpx
from typing import Any, Optional
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from dotenv import load_dotenv

load_dotenv()

FASTMAIL_API_TOKEN = os.getenv("FASTMAIL_API_TOKEN", "")
SESSION_URL = "https://api.fastmail.com/jmap/session"


class FastmailClient:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.session_data = None
        self.account_id = None
        self.api_url = None
        self.client = httpx.AsyncClient()

    async def get_session(self):
        if self.session_data is None:
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            response = await self.client.get(SESSION_URL, headers=headers)
            response.raise_for_status()
            self.session_data = response.json()
            self.account_id = self.session_data["primaryAccounts"]["urn:ietf:params:jmap:mail"]
            self.api_url = self.session_data["apiUrl"]
        return self.session_data

    async def make_jmap_request(self, method_calls: list) -> dict:
        await self.get_session()
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "using": [
                "urn:ietf:params:jmap:core",
                "urn:ietf:params:jmap:mail"
            ],
            "methodCalls": method_calls
        }
        response = await self.client.post(self.api_url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    async def search_emails(self, query: str = "", limit: int = 10, mailbox: Optional[str] = None) -> dict:
        filter_conditions = {}
        
        if query:
            filter_conditions["text"] = query
        
        if mailbox:
            mailbox_id = await self.get_mailbox_id(mailbox)
            if mailbox_id:
                filter_conditions["inMailbox"] = mailbox_id
        
        method_calls = [
            ["Email/query", {
                "accountId": self.account_id,
                "filter": filter_conditions if filter_conditions else None,
                "sort": [{"property": "receivedAt", "isAscending": False}],
                "limit": limit
            }, "q1"],
            ["Email/get", {
                "accountId": self.account_id,
                "#ids": {
                    "resultOf": "q1",
                    "name": "Email/query",
                    "path": "/ids"
                },
                "properties": ["id", "subject", "from", "to", "receivedAt", "preview", "mailboxIds"]
            }, "g1"]
        ]
        
        result = await self.make_jmap_request(method_calls)
        return result

    async def get_email(self, email_id: str) -> dict:
        method_calls = [
            ["Email/get", {
                "accountId": self.account_id,
                "ids": [email_id],
                "properties": ["id", "subject", "from", "to", "cc", "bcc", "receivedAt", "sentAt", "textBody", "htmlBody", "bodyValues", "attachments"]
            }, "g1"]
        ]
        
        result = await self.make_jmap_request(method_calls)
        return result

    async def list_mailboxes(self) -> dict:
        method_calls = [
            ["Mailbox/get", {
                "accountId": self.account_id,
                "properties": ["id", "name", "role", "totalEmails", "unreadEmails"]
            }, "m1"]
        ]
        
        result = await self.make_jmap_request(method_calls)
        return result

    async def get_mailbox_id(self, mailbox_name: str) -> Optional[str]:
        mailboxes_result = await self.list_mailboxes()
        mailboxes = mailboxes_result.get("methodResponses", [[]])[0][1].get("list", [])
        
        for mailbox in mailboxes:
            if mailbox["name"].lower() == mailbox_name.lower() or mailbox.get("role", "").lower() == mailbox_name.lower():
                return mailbox["id"]
        
        return None

    async def close(self):
        await self.client.aclose()


async def main():
    if not FASTMAIL_API_TOKEN:
        raise ValueError("FASTMAIL_API_TOKEN environment variable must be set")

    fastmail_client = FastmailClient(FASTMAIL_API_TOKEN)
    
    server = Server("fastmail-mcp")

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return [
            Tool(
                name="search_emails",
                description="Search emails in your Fastmail account. You can search by text query and optionally filter by mailbox (e.g., 'inbox', 'sent', 'archive').",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query text to find in emails (searches subject, body, from, to). Leave empty to get recent emails."
                        },
                        "limit": {
                            "type": "number",
                            "description": "Maximum number of emails to return (default: 10, max: 50)",
                            "default": 10
                        },
                        "mailbox": {
                            "type": "string",
                            "description": "Filter by mailbox name (e.g., 'inbox', 'sent', 'archive', 'trash'). Optional."
                        }
                    }
                }
            ),
            Tool(
                name="get_email",
                description="Get the full content of a specific email by its ID, including body, attachments, and all metadata.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "email_id": {
                            "type": "string",
                            "description": "The unique ID of the email to retrieve"
                        }
                    },
                    "required": ["email_id"]
                }
            ),
            Tool(
                name="list_mailboxes",
                description="List all mailboxes in your Fastmail account with their names, roles, and email counts.",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            )
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        if arguments is None:
            arguments = {}

        try:
            if name == "search_emails":
                query = arguments.get("query", "")
                limit = min(int(arguments.get("limit", 10)), 50)
                mailbox = arguments.get("mailbox")
                
                result = await fastmail_client.search_emails(query, limit, mailbox)
                
                emails = []
                for response in result.get("methodResponses", []):
                    if response[0] == "Email/get":
                        emails = response[1].get("list", [])
                        break
                
                if not emails:
                    return [TextContent(
                        type="text",
                        text="No emails found matching your search criteria."
                    )]
                
                formatted_emails = []
                for email in emails:
                    from_addr = email.get("from", [{}])[0].get("email", "Unknown")
                    from_name = email.get("from", [{}])[0].get("name", "")
                    formatted_emails.append(
                        f"ID: {email['id']}\n"
                        f"Subject: {email.get('subject', 'No subject')}\n"
                        f"From: {from_name} <{from_addr}>\n"
                        f"Date: {email.get('receivedAt', 'Unknown')}\n"
                        f"Preview: {email.get('preview', '')}\n"
                    )
                
                return [TextContent(
                    type="text",
                    text=f"Found {len(emails)} email(s):\n\n" + "\n---\n".join(formatted_emails)
                )]
            
            elif name == "get_email":
                email_id = arguments.get("email_id")
                if not email_id:
                    return [TextContent(type="text", text="Error: email_id is required")]
                
                result = await fastmail_client.get_email(email_id)
                
                email = None
                for response in result.get("methodResponses", []):
                    if response[0] == "Email/get":
                        emails_list = response[1].get("list", [])
                        if emails_list:
                            email = emails_list[0]
                        break
                
                if not email:
                    return [TextContent(type="text", text=f"Email with ID {email_id} not found")]
                
                from_addr = email.get("from", [{}])[0].get("email", "Unknown")
                from_name = email.get("from", [{}])[0].get("name", "")
                to_list = ", ".join([f"{t.get('name', '')} <{t.get('email', '')}>" for t in email.get("to", [])])
                
                body_text = ""
                text_body_ids = email.get("textBody", [])
                body_values = email.get("bodyValues", {})
                
                if text_body_ids and body_values:
                    for part_id in text_body_ids:
                        if part_id in body_values:
                            body_text = body_values[part_id].get("value", "")
                            break
                
                attachments_info = ""
                if email.get("attachments"):
                    attachments_info = "\n\nAttachments:\n" + "\n".join([
                        f"- {att.get('name', 'Unknown')} ({att.get('type', 'Unknown type')}, {att.get('size', 0)} bytes)"
                        for att in email["attachments"]
                    ])
                
                formatted_email = (
                    f"Subject: {email.get('subject', 'No subject')}\n"
                    f"From: {from_name} <{from_addr}>\n"
                    f"To: {to_list}\n"
                    f"Date: {email.get('receivedAt', 'Unknown')}\n"
                    f"{attachments_info}\n"
                    f"\n--- Email Body ---\n{body_text}"
                )
                
                return [TextContent(type="text", text=formatted_email)]
            
            elif name == "list_mailboxes":
                result = await fastmail_client.list_mailboxes()
                
                mailboxes = []
                for response in result.get("methodResponses", []):
                    if response[0] == "Mailbox/get":
                        mailboxes = response[1].get("list", [])
                        break
                
                if not mailboxes:
                    return [TextContent(type="text", text="No mailboxes found")]
                
                formatted_mailboxes = []
                for mailbox in mailboxes:
                    formatted_mailboxes.append(
                        f"Name: {mailbox.get('name', 'Unknown')}\n"
                        f"ID: {mailbox['id']}\n"
                        f"Role: {mailbox.get('role', 'None')}\n"
                        f"Total Emails: {mailbox.get('totalEmails', 0)}\n"
                        f"Unread Emails: {mailbox.get('unreadEmails', 0)}"
                    )
                
                return [TextContent(
                    type="text",
                    text=f"Found {len(mailboxes)} mailbox(es):\n\n" + "\n---\n".join(formatted_mailboxes)
                )]
            
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
                
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="fastmail-mcp",
                    server_version="1.0.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )
    finally:
        await fastmail_client.close()


if __name__ == "__main__":
    asyncio.run(main())
