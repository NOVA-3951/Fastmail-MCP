# Fastmail MCP Server

[![smithery badge](https://smithery.ai/badge/@NOVA-3951/fastmail)](https://smithery.ai/server/@NOVA-3951/fastmail)

An MCP (Model Context Protocol) server that provides AI assistants with secure access to your Fastmail emails via the JMAP API.

## Features

- 🔍 **Search Emails**: Search your emails by text query and filter by mailbox
- 📧 **Get Email Details**: Retrieve full email content including body and attachments
- 📁 **List Mailboxes**: View all your mailboxes with email counts
- 🔒 **Secure**: Uses Fastmail API tokens with proper authentication

## Prerequisites

- Python 3.12+
- A Fastmail account
- Fastmail API token (instructions below)

## Getting Your Fastmail API Token

1. Log into your Fastmail account
2. Go to **Settings → Privacy & Security → Integrations → API Tokens**
   - Or visit: https://app.fastmail.com/settings/security/tokens/new
3. Create a new API token with the following scopes:
   - `urn:ietf:params:jmap:core` (Required)
   - `urn:ietf:params:jmap:mail` (Required for email access)
4. Copy the generated token - you'll need it for setup

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root:
```bash
cp .env.example .env
```

4. Edit `.env` and add your Fastmail API token:
```
FASTMAIL_API_TOKEN=your_actual_token_here
```

## Configuration for AI Clients

### Claude Desktop

Add this to your Claude Desktop config file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "fastmail": {
      "command": "python",
      "args": ["/absolute/path/to/fastmail_mcp.py"],
      "env": {
        "FASTMAIL_API_TOKEN": "your_fastmail_api_token_here"
      }
    }
  }
}
```

Replace `/absolute/path/to/` with the actual path to this project.

### Other MCP Clients

For other MCP-compatible clients (VS Code, Cursor, etc.), configure them to run:

```bash
python /path/to/fastmail_mcp.py
```

Make sure to set the `FASTMAIL_API_TOKEN` environment variable.

### Smithery Deployment

This server is configured for deployment on [Smithery](https://smithery.ai), a platform for hosting and sharing MCP servers. When deployed to Smithery, users provide their Fastmail API token through Smithery's configuration flow - no token is required at build time.

**Deploy to Smithery:**

1. Push this repository to GitHub
2. Go to the Smithery dashboard and click **"Deploy"**
3. Select **"From GitHub"** and connect your repository
4. Smithery will build and host your server automatically

When users install your server from Smithery, they'll be prompted to enter their Fastmail API token through Smithery's secure configuration interface.

**Use via Smithery CLI:**

```bash
# Install Smithery CLI
npm install -g @smithery/cli

# Run the server (you'll be prompted for your API token)
smithery run @your-username/fastmail-mcp --config '{"FASTMAIL_API_TOKEN":"your_token"}'
```

**Add to Claude Desktop via Smithery:**

```json
{
  "mcpServers": {
    "fastmail": {
      "command": "npx",
      "args": [
        "-y",
        "@smithery/cli@latest",
        "run",
        "@your-username/fastmail-mcp",
        "--config",
        "{\"FASTMAIL_API_TOKEN\":\"your_token_here\"}"
      ]
    }
  }
}
```

**HTTP Mode (for Smithery/remote deployment):**

The server supports both stdio (local) and HTTP (remote) transports:

```bash
# Run in HTTP mode on port 8000
python fastmail_mcp.py --http

# Run in stdio mode (default, for local use)
python fastmail_mcp.py
```

## Available Tools

### 1. search_emails

Search emails in your Fastmail account.

**Parameters:**
- `query` (string, optional): Search text (searches subject, body, from, to)
- `limit` (number, optional): Max emails to return (default: 10, max: 50)
- `mailbox` (string, optional): Filter by mailbox (e.g., "inbox", "sent", "archive")

**Example usage in Claude:**
> "Search my emails for messages about 'project deadline'"
> "Show me the last 5 emails in my inbox"
> "Find emails from john@example.com"

### 2. get_email

Get the full content of a specific email.

**Parameters:**
- `email_id` (string, required): The email ID from search results

**Example usage in Claude:**
> "Show me the full content of email ID abc123"
> "Get the email body for that message"

### 3. list_mailboxes

List all mailboxes with their email counts.

**Example usage in Claude:**
> "What mailboxes do I have?"
> "Show me my folders and how many emails are in each"

## Testing

You can test the MCP server using the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector python fastmail_mcp.py
```

This opens a web UI where you can manually test the tools.

## Security Notes

- Your API token grants full access to your Fastmail account - keep it secure
- Never commit your `.env` file or expose your API token
- The MCP server only has read access (no sending or deleting emails)
- Consider creating a dedicated API token just for this MCP server

## Troubleshooting

**"FASTMAIL_API_TOKEN environment variable must be set"**
- Make sure your `.env` file exists and contains your API token
- For Claude Desktop, ensure the token is in the config file

**"401 Unauthorized"**
- Check that your API token is correct and hasn't been revoked
- Ensure the token has the required scopes

**No emails returned**
- Try broadening your search query
- Check that the mailbox name is correct (use `list_mailboxes` to see available mailboxes)

## API Rate Limits

Fastmail has rate limits on API requests. The MCP server handles this gracefully, but avoid making excessive requests in short periods.

## License

MIT License - feel free to modify and use as needed.

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## Resources

- [Fastmail API Documentation](https://www.fastmail.com/dev/)
- [JMAP Specification](https://jmap.io/)
- [Model Context Protocol](https://modelcontextprotocol.io/)