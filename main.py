#!/usr/bin/env python3
"""
Explicit HTTP entry point for Smithery deployment.
This file starts the MCP server in HTTP mode for remote access.
"""
import os
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import JSONResponse
import contextlib

from fastmail_mcp import mcp

mcp.settings.stateless_http = True
mcp.settings.host = "0.0.0.0"

mcp.settings.transport_security.enable_dns_rebinding_protection = False
mcp.settings.transport_security.allowed_hosts = [
    "*",
    "smithery.run:*",
    "*.smithery.run:*",
    "localhost:*",
    "127.0.0.1:*",
]
mcp.settings.transport_security.allowed_origins = [
    "*",
    "https://smithery.run",
    "https://*.smithery.run",
    "http://localhost:*",
    "http://127.0.0.1:*",
]

mcp_http_app = mcp.streamable_http_app()

@contextlib.asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield

async def health_check(request):
    return JSONResponse({"status": "ok"})

async def debug_env(request):
    """Debug endpoint to check environment variables (remove in production)."""
    env_vars = {k: v[:20] + "..." if len(v) > 20 else v 
                for k, v in os.environ.items() 
                if "token" in k.lower() or "api" in k.lower() or "key" in k.lower() or "fastmail" in k.lower()}
    return JSONResponse({
        "token_found": bool(os.getenv("FASTMAIL_API_TOKEN") or os.getenv("fastmailApiToken")),
        "env_hints": list(env_vars.keys())
    })

app = Starlette(
    routes=[
        Route("/health", health_check),
        Route("/debug", debug_env),
        Mount("/mcp", app=mcp_http_app),
        Mount("/", app=mcp_http_app),
    ],
    lifespan=lifespan
)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        forwarded_allow_ips="*",
        proxy_headers=True
    )
