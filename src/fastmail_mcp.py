#!/usr/bin/env python3
import os
import asyncio
import httpx
from typing import Optional
from mcp.server.fastmcp import FastMCP

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
                "properties": ["id", "subject", "from", "to", "cc", "bcc", "receivedAt", "sentAt", "textBody", "htmlBody", "bodyValues", "attachments"],
                "fetchTextBodyValues": True
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


mcp = FastMCP("fastmail-mcp")
fastmail_client = None


def get_client() -> FastmailClient:
    global fastmail_client
    if fastmail_client is None:
        token = os.getenv("FASTMAIL_API_TOKEN", "")
        if not token:
            raise ValueError("FASTMAIL_API_TOKEN environment variable must be set")
        fastmail_client = FastmailClient(token)
    return fastmail_client


@mcp.tool()
async def search_emails(query: str = "", limit: int = 10, mailbox: str = "") -> str:
    """Search emails in your Fastmail account. You can search by text query and optionally filter by mailbox (e.g., 'inbox', 'sent', 'archive').
    
    Args:
        query: Search query text to find in emails (searches subject, body, from, to). Leave empty to get recent emails.
        limit: Maximum number of emails to return (default: 10, max: 50)
        mailbox: Filter by mailbox name (e.g., 'inbox', 'sent', 'archive', 'trash'). Optional.
    """
    try:
        client = get_client()
        limit = min(int(limit), 50)
        mailbox_filter = mailbox if mailbox else None
        
        result = await client.search_emails(query, limit, mailbox_filter)
        
        emails = []
        for response in result.get("methodResponses", []):
            if response[0] == "Email/get":
                emails = response[1].get("list", [])
                break
        
        if not emails:
            return "No emails found matching your search criteria."
        
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
        
        return f"Found {len(emails)} email(s):\n\n" + "\n---\n".join(formatted_emails)
        
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def get_email(email_id: str) -> str:
    """Get the full content of a specific email by its ID, including body, attachments, and all metadata.
    
    Args:
        email_id: The unique ID of the email to retrieve
    """
    try:
        if not email_id:
            return "Error: email_id is required"
        
        client = get_client()
        result = await client.get_email(email_id)
        
        email = None
        for response in result.get("methodResponses", []):
            if response[0] == "Email/get":
                emails_list = response[1].get("list", [])
                if emails_list:
                    email = emails_list[0]
                break
        
        if not email:
            return f"Email with ID {email_id} not found"
        
        from_addr = email.get("from", [{}])[0].get("email", "Unknown")
        from_name = email.get("from", [{}])[0].get("name", "")
        to_list = ", ".join([f"{t.get('name', '')} <{t.get('email', '')}>" for t in email.get("to", [])])
        
        body_text = ""
        text_body_ids = email.get("textBody", [])
        body_values = email.get("bodyValues", {})
        
        if text_body_ids and body_values:
            for part in text_body_ids:
                part_id = part.get("partId") if isinstance(part, dict) else part
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
        
        return formatted_email
        
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def list_mailboxes() -> str:
    """List all mailboxes in your Fastmail account with their names, roles, and email counts."""
    try:
        client = get_client()
        result = await client.list_mailboxes()
        
        mailboxes = []
        for response in result.get("methodResponses", []):
            if response[0] == "Mailbox/get":
                mailboxes = response[1].get("list", [])
                break
        
        if not mailboxes:
            return "No mailboxes found"
        
        formatted_mailboxes = []
        for mailbox in mailboxes:
            formatted_mailboxes.append(
                f"Name: {mailbox.get('name', 'Unknown')}\n"
                f"ID: {mailbox['id']}\n"
                f"Role: {mailbox.get('role', 'None')}\n"
                f"Total Emails: {mailbox.get('totalEmails', 0)}\n"
                f"Unread Emails: {mailbox.get('unreadEmails', 0)}"
            )
        
        return f"Found {len(mailboxes)} mailbox(es):\n\n" + "\n---\n".join(formatted_mailboxes)
        
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
    else:
        mcp.run(transport="stdio")
