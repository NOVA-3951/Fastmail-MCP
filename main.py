#!/usr/bin/env python3
"""
Explicit HTTP entry point for Smithery deployment.
This file starts the MCP server in HTTP mode for remote access.
"""
import os
import sys
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount
import contextlib

from fastmail_mcp import mcp

mcp.settings.stateless_http = True

@contextlib.asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield

app = Starlette(
    routes=[Mount("/", mcp.streamable_http_app())],
    lifespan=lifespan
)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
