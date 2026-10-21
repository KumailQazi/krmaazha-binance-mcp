"""Commercial MCPRush Gateway Server with token verification and dynamic tenant scoping."""

from __future__ import annotations

import contextvars
import os
import secrets
from dataclasses import dataclass
from typing import Any

import uvicorn
from binance.client import Client
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from krmaazha_binance_mcp.server import mcp


@dataclass(frozen=True)
class TenantContext:
    """Request-scoped tenant credentials extracted from X-Env headers."""

    env: str
    api_key: str | None
    api_secret: str | None


# Request-scoped context variable isolating credentials across concurrent requests
current_tenant_ctx: contextvars.ContextVar[TenantContext | None] = contextvars.ContextVar(
    "current_tenant_ctx", default=None
)


def get_current_client() -> Client:
    """Resolve the Binance client for the active request context or fall back to server env."""
    ctx = current_tenant_ctx.get()
    if ctx and ctx.api_key and ctx.api_secret:
        return Client(ctx.api_key, ctx.api_secret, testnet=(ctx.env == "testnet"))

    # Fallback to server environment keys if available
    env_key = os.environ.get("BINANCE_READ_API_KEY", "")
    env_sec = os.environ.get("BINANCE_READ_API_SECRET", "")
    is_testnet = os.environ.get("BINANCE_ENV", "testnet").lower() == "testnet"
    return Client(env_key, env_sec, testnet=is_testnet)


class McprushAuthMiddleware(BaseHTTPMiddleware):
    """Verifies the x-mcprush-token header on every incoming request from MCPRush gateway."""

    def __init__(self, app: Any, expected_token: str | None = None) -> None:
        super().__init__(app)
        self.expected_token = expected_token or os.environ.get("MCPRUSH_VERIFICATION_TOKEN")

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        # Allow open health checks for Railway container orchestration
        if request.url.path in ("/health", "/ping", "/", "/robots.txt"):
            return await call_next(request)

        token = request.headers.get("x-mcprush-token")

        # Constant-time comparison defends against timing attacks
        valid = (
            bool(self.expected_token)
            and bool(token)
            and secrets.compare_digest(token.strip(), self.expected_token.strip())  # type: ignore[union-attr]
        )
        if not valid:
            return JSONResponse(
                {
                    "error": "Unauthorized",
                    "message": (
                        "Missing or invalid x-mcprush-token header. "
                        "Reinstall/reconnect through the MCPRush gateway."
                    ),
                },
                status_code=401,
            )

        return await call_next(request)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Extracts buyer-specific Binance credentials passed via X-Env headers."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        env = request.headers.get("x-env-binance-env", "testnet")
        api_key = request.headers.get("x-env-binance-read-api-key")
        api_secret = request.headers.get("x-env-binance-read-api-secret")

        tenant = TenantContext(env=env, api_key=api_key, api_secret=api_secret)
        token = current_tenant_ctx.set(tenant)
        try:
            return await call_next(request)
        finally:
            current_tenant_ctx.reset(token)


async def healthcheck(request: Request) -> JSONResponse:
    """Healthcheck endpoint for Railway and uptime monitors."""
    auth_enabled = bool(os.environ.get("MCPRUSH_VERIFICATION_TOKEN"))
    return JSONResponse(
        {
            "status": "ok",
            "service": "krmaazha-binance-mcp",
            "transport": "sse",
            "gateway_auth": "enabled" if auth_enabled else "unconfigured",
        }
    )


def create_gateway_app() -> Starlette:
    """Build production Starlette app with authentication, SSE transport, and tenant isolation."""
    # 1. Obtain native FastMCP SSE application
    app = mcp.sse_app()

    # 2. Add healthcheck endpoints
    app.routes.insert(0, Route("/health", healthcheck, methods=["GET"]))
    app.routes.insert(0, Route("/ping", healthcheck, methods=["GET"]))

    # 3. Alias /mcp to /sse so both https://domain/mcp and https://domain/sse work
    for r in app.routes:
        if getattr(r, "path", None) == "/sse" and isinstance(r, Route):
            app.routes.insert(0, Route("/mcp", r.endpoint, methods=["GET"]))
            break

    # 4. Attach gateway verification and tenant isolation middlewares
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(McprushAuthMiddleware)

    return app


def main() -> None:
    """Run the production gateway server on host and port specified by Railway."""
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    app = create_gateway_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
