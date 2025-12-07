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
mcp.settings.transport_security.allowed_hosts = ["*"]
mcp.settings.transport_security.allowed_origins = ["*"]

mcp_http_app = mcp.streamable_http_app()

@contextlib.asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield

async def health_check(request):
    return JSONResponse({"status": "ok"})

app = Starlette(
    routes=[
        Route("/health", health_check),
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
