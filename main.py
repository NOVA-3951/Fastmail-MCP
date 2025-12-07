#!/usr/bin/env python3
"""
HTTP entry point for Smithery deployment.
Handles configuration from query parameters as required by Smithery HTTP transport.
"""
import os
import uvicorn
from contextvars import ContextVar
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, Response
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
import contextlib

request_config: ContextVar[dict] = ContextVar("request_config", default={})

from fastmail_mcp import mcp, set_request_config_var

set_request_config_var(request_config)

class ConfigMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        config = dict(request.query_params)
        token = request_config.set(config)
        try:
            response = await call_next(request)
            return response
        finally:
            request_config.reset(token)

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
    return JSONResponse({"status": "ok", "service": "fastmail-mcp"})

async def mcp_handler(request):
    config = dict(request.query_params)
    token = request_config.set(config)
    try:
        response = await mcp_http_app(request.scope, request.receive, request._send)
        return response
    except Exception:
        scope = request.scope
        receive = request.receive
        
        async def send(message):
            pass
        
        await mcp_http_app(scope, receive, send)
        return Response(status_code=200)
    finally:
        request_config.reset(token)

async def mcp_options(request):
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, mcp-session-id, *",
            "Access-Control-Expose-Headers": "mcp-session-id, mcp-protocol-version",
        }
    )

from starlette.routing import Mount

app = Starlette(
    routes=[
        Route("/health", health_check, methods=["GET"]),
        Mount("/mcp", app=mcp_http_app),
        Mount("/", app=mcp_http_app),
    ],
    middleware=[Middleware(ConfigMiddleware)],
    lifespan=lifespan
)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8081"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Starting Fastmail MCP server on {host}:{port}")
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        forwarded_allow_ips="*",
        proxy_headers=True
    )
