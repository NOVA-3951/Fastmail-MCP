#!/usr/bin/env python3
import os
import asyncio
import httpx
from typing import Optional
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent, ToolAnnotations


def get_api_token() -> str:
    """Get Fastmail API token from various environment variable formats.
    
    Smithery may pass config as environment variables with different naming conventions.
    """
    return (
        os.getenv("FASTMAIL_API_TOKEN", "") or
        os.getenv("fastmailApiToken", "") or
        os.getenv("fastmail_api_token", "") or
        os.getenv("CONFIG_FASTMAIL_API_TOKEN", "") or
        os.getenv("CONFIG_fastmailApiToken", "") or
        os.getenv("SMITHERY_FASTMAIL_API_TOKEN", "") or
        os.getenv("SMITHERY_fastmailApiToken", "") or
        os.getenv("MCP_FASTMAIL_API_TOKEN", "") or
        os.getenv("MCP_fastmailApiToken", "")
    )


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
        if not self.api_url:
            raise ValueError("API URL not available - session may have failed")
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


mcp = FastMCP(
    "fastmail-mcp",
    instructions="""You are an AI assistant with access to the user's Fastmail email account. 
You can search emails, read email content, and list mailboxes. 
Always be helpful and respect user privacy. 
When searching, provide clear summaries of found emails.
When reading emails, present the content in a readable format."""
)
fastmail_client = None


def get_client() -> FastmailClient:
    global fastmail_client
    if fastmail_client is None:
        token = get_api_token()
        if not token:
            raise ValueError("FASTMAIL_API_TOKEN is not configured. Please provide your Fastmail API token in the configuration.")
        fastmail_client = FastmailClient(token)
    return fastmail_client


def is_token_configured() -> bool:
    return bool(get_api_token())


@mcp.tool(
    annotations=ToolAnnotations(
        title="Search Emails",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True
    )
)
async def search_emails(
    query: str = "",
    limit: int = 10,
    mailbox: str = ""
) -> str:
    """Search emails in your Fastmail account by text query and optionally filter by mailbox.
    
    This tool searches across email subjects, bodies, sender addresses, and recipient addresses.
    Results are sorted by date with the most recent emails first.
    
    Args:
        query: Search query text to find in emails. Searches subject, body, from, and to fields. Leave empty to get the most recent emails.
        limit: Maximum number of emails to return. Default is 10, maximum allowed is 50. Use smaller values for faster responses.
        mailbox: Filter results to a specific mailbox/folder. Common values: 'inbox', 'sent', 'drafts', 'archive', 'trash', 'spam'. Leave empty to search all mailboxes.
    
    Returns:
        A formatted list of matching emails with ID, subject, sender, date, and preview.
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
        return f"Error searching emails: {str(e)}"


@mcp.tool(
    annotations=ToolAnnotations(
        title="Get Email Content",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
async def get_email(email_id: str) -> str:
    """Retrieve the full content of a specific email by its unique ID.
    
    This tool fetches complete email details including the full body text,
    attachment information, and all metadata. Use the email ID from search results.
    
    Args:
        email_id: The unique identifier of the email to retrieve. Obtain this from the search_emails tool results.
    
    Returns:
        The complete email with subject, sender, recipients, date, body text, and attachment list.
    """
    try:
        if not email_id:
            return "Error: email_id is required. Use search_emails first to find email IDs."
        
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
            return f"Email with ID '{email_id}' not found. The email may have been deleted or the ID may be incorrect."
        
        from_addr = email.get("from", [{}])[0].get("email", "Unknown")
        from_name = email.get("from", [{}])[0].get("name", "")
        to_list = ", ".join([f"{t.get('name', '')} <{t.get('email', '')}>" for t in email.get("to", [])])
        cc_list = ", ".join([f"{t.get('name', '')} <{t.get('email', '')}>" for t in email.get("cc", [])]) if email.get("cc") else ""
        
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
        
        cc_line = f"\nCC: {cc_list}" if cc_list else ""
        
        formatted_email = (
            f"Subject: {email.get('subject', 'No subject')}\n"
            f"From: {from_name} <{from_addr}>\n"
            f"To: {to_list}"
            f"{cc_line}\n"
            f"Date: {email.get('receivedAt', 'Unknown')}\n"
            f"{attachments_info}\n"
            f"\n--- Email Body ---\n{body_text}"
        )
        
        return formatted_email
        
    except Exception as e:
        return f"Error retrieving email: {str(e)}"


@mcp.tool(
    annotations=ToolAnnotations(
        title="List Mailboxes",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False
    )
)
async def list_mailboxes() -> str:
    """List all mailboxes (folders) in your Fastmail account with email counts.
    
    This tool retrieves all available mailboxes including inbox, sent, drafts,
    archive, trash, spam, and any custom folders. Shows the total and unread
    email count for each mailbox.
    
    Returns:
        A formatted list of all mailboxes with their names, roles, total emails, and unread counts.
    """
    try:
        client = get_client()
        result = await client.list_mailboxes()
        
        mailboxes = []
        for response in result.get("methodResponses", []):
            if response[0] == "Mailbox/get":
                mailboxes = response[1].get("list", [])
                break
        
        if not mailboxes:
            return "No mailboxes found in this account."
        
        formatted_mailboxes = []
        for mailbox in mailboxes:
            role = mailbox.get('role', 'custom')
            formatted_mailboxes.append(
                f"Name: {mailbox.get('name', 'Unknown')}\n"
                f"Role: {role if role else 'custom'}\n"
                f"Total Emails: {mailbox.get('totalEmails', 0)}\n"
                f"Unread Emails: {mailbox.get('unreadEmails', 0)}"
            )
        
        return f"Found {len(mailboxes)} mailbox(es):\n\n" + "\n---\n".join(formatted_mailboxes)
        
    except Exception as e:
        return f"Error listing mailboxes: {str(e)}"


@mcp.prompt()
def check_inbox() -> str:
    """Check your inbox for recent emails."""
    return "Please show me my most recent emails from my inbox. Use the search_emails tool with mailbox='inbox' and limit=10."


@mcp.prompt()
def search_from_sender(sender: str) -> str:
    """Search for emails from a specific sender."""
    return f"Please search for all emails from {sender}. Use the search_emails tool with query='{sender}'."


@mcp.prompt()
def check_unread() -> str:
    """Check for unread emails across all mailboxes."""
    return "Please list all my mailboxes and tell me which ones have unread emails. Use the list_mailboxes tool."


@mcp.prompt()
def find_attachments(topic: str) -> str:
    """Find emails with attachments about a topic."""
    return f"Please search for emails about '{topic}' and show me which ones have attachments. Use search_emails to find them, then use get_email on promising results to check for attachments."


@mcp.resource("mailboxes://list")
async def get_mailboxes_resource() -> str:
    """List of all mailboxes in the Fastmail account."""
    try:
        client = get_client()
        result = await client.list_mailboxes()
        
        mailboxes = []
        for response in result.get("methodResponses", []):
            if response[0] == "Mailbox/get":
                mailboxes = response[1].get("list", [])
                break
        
        if not mailboxes:
            return "No mailboxes found."
        
        lines = ["# Fastmail Mailboxes", ""]
        for mb in mailboxes:
            role = mb.get('role', 'custom') or 'custom'
            lines.append(f"- **{mb.get('name', 'Unknown')}** ({role}): {mb.get('totalEmails', 0)} total, {mb.get('unreadEmails', 0)} unread")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.resource("emails://recent")
async def get_recent_emails_resource() -> str:
    """Most recent 10 emails from the inbox."""
    try:
        client = get_client()
        result = await client.search_emails("", 10, "inbox")
        
        emails = []
        for response in result.get("methodResponses", []):
            if response[0] == "Email/get":
                emails = response[1].get("list", [])
                break
        
        if not emails:
            return "No recent emails found."
        
        lines = ["# Recent Emails", ""]
        for email in emails:
            from_addr = email.get("from", [{}])[0].get("email", "Unknown")
            from_name = email.get("from", [{}])[0].get("name", from_addr)
            subject = email.get('subject', 'No subject')
            date = email.get('receivedAt', 'Unknown')
            lines.append(f"- **{subject}** from {from_name} ({date})")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        import uvicorn
        from starlette.applications import Starlette
        from starlette.routing import Mount
        import contextlib
        
        mcp.settings.stateless_http = True
        
        @contextlib.asynccontextmanager
        async def lifespan(app):
            async with mcp.session_manager.run():
                yield
        
        app = Starlette(
            routes=[Mount("/", mcp.streamable_http_app())],
            lifespan=lifespan
        )
        
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        mcp.run(transport="stdio")
