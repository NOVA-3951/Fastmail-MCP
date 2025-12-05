# Fastmail MCP Server

## Overview
This is an MCP (Model Context Protocol) server that enables AI assistants like Claude to access and search your Fastmail emails via the JMAP API. The server provides secure, read-only access to your email account through standardized MCP tools.

## Purpose
- Connect AI assistants to Fastmail email accounts
- Search and view emails using natural language
- List mailboxes and email metadata
- Provide secure authentication using Fastmail API tokens

## Current State
The MCP server is implemented and ready to use with MCP-compatible clients (Claude Desktop, VS Code, Cursor, etc.).

## Recent Changes
- 2024-12-05: Initial implementation with JMAP API integration
- Added three core tools: search_emails, get_email, list_mailboxes
- Implemented async FastmailClient with session management
- Created connection test utility

## Project Architecture

### Structure
```
├── src/
│   └── fastmail_mcp.py       # Main MCP server implementation
├── test_connection.py         # Connection test utility
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variable template
├── .gitignore                # Git ignore rules
└── README.md                 # User documentation
```

### Key Components

1. **FastmailClient**: Handles JMAP API communication
   - Session management with token caching
   - Email search, retrieval, and mailbox listing
   - Async HTTP client using httpx

2. **MCP Server**: Exposes tools via stdio
   - search_emails: Search by text/mailbox
   - get_email: Retrieve full email content
   - list_mailboxes: List all folders

3. **Authentication**: Bearer token authentication
   - API token from Fastmail settings
   - Secure environment variable storage

### Dependencies
- mcp>=1.1.0: MCP SDK for server implementation
- httpx>=0.27.0: Async HTTP client for JMAP API
- python-dotenv>=1.0.0: Environment variable management

## Usage

### Setup
1. Get Fastmail API token from: https://app.fastmail.com/settings/security/tokens/new
2. Create `.env` file: `cp .env.example .env`
3. Add token to `.env`: `FASTMAIL_API_TOKEN=your_token`
4. Install dependencies: `pip install -r requirements.txt`
5. Test connection: `python test_connection.py`

### Integration with Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "fastmail": {
      "command": "python",
      "args": ["/absolute/path/to/src/fastmail_mcp.py"],
      "env": {
        "FASTMAIL_API_TOKEN": "your_token_here"
      }
    }
  }
}
```

### Available MCP Tools

1. **search_emails**
   - Search emails by query text
   - Filter by mailbox (inbox, sent, etc.)
   - Limit results (max 50)

2. **get_email**
   - Retrieve full email by ID
   - Includes body, attachments, metadata

3. **list_mailboxes**
   - List all folders
   - Shows email counts (total, unread)

## Security Notes
- API token provides full account access
- Never commit `.env` file or expose tokens
- Token stored securely in environment variables
- Server has read-only access (no sending/deleting)

## Technical Decisions

### JMAP over IMAP
- Modern JSON-based protocol
- Single HTTP endpoint vs multiple connections
- Better suited for web/API integrations
- Standardized by IETF (RFC 8620, RFC 8621)

### Async Architecture
- Non-blocking I/O for better performance
- httpx AsyncClient for concurrent requests
- Compatible with MCP's async server model

### MCP Protocol
- Standard interface for AI-to-data connections
- Works across multiple AI clients
- Tools expose email functionality naturally to LLMs

## Known Limitations
- Read-only access (no sending, deleting, or moving emails)
- API rate limits apply (handled gracefully)
- Requires Fastmail account with API access

## Future Enhancements
- Add email composition/sending capability
- Support for attachments download
- Calendar integration via JMAP
- Contacts access
- Advanced search filters (date ranges, flags)
