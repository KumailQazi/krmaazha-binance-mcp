"""Unit tests for the MCPRush commercial gateway server and middlewares."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from krmaazha_binance_mcp.gateway_server import (
    McprushAuthMiddleware,
    TenantContextMiddleware,
    create_gateway_app,
    get_current_client,
)


def test_gateway_healthcheck():
    app = create_gateway_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "krmaazha-binance-mcp"


def test_mcprush_auth_middleware_blocks_unauthorized(monkeypatch):
    monkeypatch.setenv("MCPRUSH_VERIFICATION_TOKEN", "valid-secret-token-123")

    async def mock_endpoint(request: Request):
        return PlainTextResponse("success")

    app = Starlette(
        routes=[Route("/protected", mock_endpoint)],
        middleware=[Middleware(McprushAuthMiddleware)],
    )
    client = TestClient(app)

    # 1. No token header -> 401
    resp_no_token = client.get("/protected")
    assert resp_no_token.status_code == 401
    assert "Missing or invalid x-mcprush-token" in resp_no_token.json()["message"]

    # 2. Wrong token header -> 401
    resp_wrong_token = client.get("/protected", headers={"x-mcprush-token": "wrong-token"})
    assert resp_wrong_token.status_code == 401

    # 3. Valid token header -> 200
    resp_valid = client.get("/protected", headers={"x-mcprush-token": "valid-secret-token-123"})
    assert resp_valid.status_code == 200
    assert resp_valid.text == "success"


def test_tenant_context_middleware_extracts_headers():
    captured_client = {}

    async def inspect_client_endpoint(request: Request):
        c = get_current_client()
        captured_client["api_key"] = c.API_KEY
        captured_client["api_secret"] = c.API_SECRET
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[Route("/tenant-test", inspect_client_endpoint)],
        middleware=[Middleware(TenantContextMiddleware)],
    )
    client = TestClient(app)

    headers = {
        "x-env-binance-env": "testnet",
        "x-env-binance-read-api-key": "buyer_test_key",
        "x-env-binance-read-api-secret": "buyer_test_secret",
    }
    resp = client.get("/tenant-test", headers=headers)
    assert resp.status_code == 200
    assert captured_client["api_key"] == "buyer_test_key"
    assert captured_client["api_secret"] == "buyer_test_secret"
