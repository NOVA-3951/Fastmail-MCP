#!/usr/bin/env python3
import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

FASTMAIL_API_TOKEN = os.getenv("FASTMAIL_API_TOKEN", "")
SESSION_URL = "https://api.fastmail.com/jmap/session"


async def test_connection():
    print("=" * 60)
    print("Fastmail MCP Server - Connection Test")
    print("=" * 60)
    print()
    
    if not FASTMAIL_API_TOKEN:
        print("❌ ERROR: FASTMAIL_API_TOKEN environment variable is not set")
        print()
        print("Please follow these steps:")
        print("1. Copy .env.example to .env")
        print("2. Get your Fastmail API token from:")
        print("   https://app.fastmail.com/settings/security/tokens/new")
        print("3. Add the token to your .env file")
        print()
        return False
    
    print(f"✓ API Token found (length: {len(FASTMAIL_API_TOKEN)} chars)")
    print()
    
    try:
        async with httpx.AsyncClient() as client:
            print("Testing connection to Fastmail JMAP API...")
            headers = {
                "Authorization": f"Bearer {FASTMAIL_API_TOKEN}",
                "Content-Type": "application/json"
            }
            
            response = await client.get(SESSION_URL, headers=headers)
            response.raise_for_status()
            session_data = response.json()
            
            print("✓ Successfully connected to Fastmail!")
            print()
            
            account_id = session_data.get("primaryAccounts", {}).get("urn:ietf:params:jmap:mail")
            api_url = session_data.get("apiUrl")
            username = session_data.get("username")
            
            print(f"Account ID: {account_id}")
            print(f"Username: {username}")
            print(f"API URL: {api_url}")
            print()
            
            capabilities = session_data.get("capabilities", {})
            print("Available capabilities:")
            for cap in capabilities.keys():
                print(f"  - {cap}")
            print()
            
            print("=" * 60)
            print("✓ Connection test successful!")
            print()
            print("Your Fastmail MCP server is ready to use.")
            print()
            print("To use this MCP server with Claude Desktop, add this to your")
            print("Claude Desktop config file:")
            print()
            print('  "mcpServers": {')
            print('    "fastmail": {')
            print('      "command": "python",')
            current_dir = os.getcwd()
            print(f'      "args": ["{current_dir}/src/fastmail_mcp.py"],')
            print('      "env": {')
            print(f'        "FASTMAIL_API_TOKEN": "{FASTMAIL_API_TOKEN[:10]}..."')
            print('      }')
            print('    }')
            print('  }')
            print()
            print("=" * 60)
            return True
            
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code}")
        print(f"   {e.response.text}")
        print()
        if e.response.status_code == 401:
            print("This usually means your API token is invalid or expired.")
            print("Please generate a new token and update your .env file.")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    exit(0 if success else 1)
