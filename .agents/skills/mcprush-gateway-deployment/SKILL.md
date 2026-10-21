---
name: mcprush-gateway-deployment
description: >-
  Production deployment guide for commercial MCP servers behind the MCPRush marketplace gateway.
  Covers Railway cloud hosting, HTTPS SSE streaming, x-mcprush-token authentication middleware,
  dynamic per-request credential injection (X-Env headers), Docker containerization, and unit economics.
---

# Commercial Gateway Deployment Skill: MCPRush & Railway

This skill guides the engineering, containerization, and cloud deployment of commercial Model Context Protocol (MCP) servers operating behind the **MCPRush** marketplace gateway on **Railway**.

---

## 1. Architectural Role of Commercial Gateways

When commercializing an MCP server on marketplace platforms like MCPRush:
* **The Gateway handles**: Billing, recurring subscriptions (e.g., $19/mo Starter, $49/mo Pro), buyer access management, call metering, and TLS termination.
* **The Server must provide**:
  1. **Persistent HTTPS Endpoint**: A live, non-sleeping URL supporting Server-Sent Events (SSE) or Streamable HTTP.
  2. **Gateway Verification Token**: An authentication check verifying `x-mcprush-token` on every incoming request.
  3. **Dynamic Tenant Credentials**: Buyer-specific API credentials passed via `X-Env-...` headers rather than static server environment variables.

---

## 2. Infrastructure Platform Validation: Railway vs Alternatives

| Platform | Pricing / Credit | Cold Start / Sleep | SSE / Streaming Support | Verdict for Commercial MCP |
|---|---|---|---|---|
| **Railway** | $5 free trial / $5/mo Hobby | **Zero (Always-On)** | **Native, persistent connection** | **Recommended Standard**: Fast, predictable, zero cold-start timeouts. |
| **Fly.io** | $5/mo free allowance | Zero (Always-On) | Native, Docker-based | Strong alternative; slightly more complex CLI orchestration. |
| **Render** | Free tier available | **Sleeps after 15m** (40–60s delay) | Drops when asleep | **Rejected**: 40s+ cold starts trigger MCPRush gateway 504 timeouts. |
| **Cloudflare Workers** | Generous free tier | Zero | Request-length constrained | **Incompatible**: Cannot easily run heavy Python C-extensions (Pandas, python-binance). |
| **AWS Lambda / Vercel** | Free tiers | 2–5s cold start | Stateless, disconnects long SSE streams | **Not Recommended**: Serverless architectures disrupt stateful MCP lifespans. |

---

## 3. Technical Implementation Specification

### 3.1 Gateway Token Verification Middleware (`x-mcprush-token`)
Every request routed through the MCPRush gateway includes the header:
```http
x-mcprush-token: <buyer-assigned-token>
```

The server must reject unauthenticated direct callers with `HTTP 401 Unauthorized` or `HTTP 403 Forbidden` if the token is missing or does not match the configured `MCPRUSH_VERIFICATION_TOKEN`.

```python
# ASGI / Starlette Middleware Pattern
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import os
import secrets

class McprushAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, expected_token: str | None = None):
        super().__init__(app)
        self.expected_token = expected_token or os.environ.get("MCPRUSH_VERIFICATION_TOKEN")

    async def dispatch(self, request, call_next):
        # Allow open health checks for Railway container orchestration
        if request.url.path in ("/health", "/ping", "/"):
            return await call_next(request)

        token = request.headers.get("x-mcprush-token")
        if not self.expected_token:
            # If no token configured in environment, warn or enforce security
            return JSONResponse({"error": "Gateway authentication not configured on server"}, status_code=500)

        # Constant-time comparison prevents timing side-channel attacks
        if not token or not secrets.compare_digest(token, self.expected_token):
            return JSONResponse(
                {"error": "Unauthorized: Missing or invalid x-mcprush-token header. Reconnect via MCPRush gateway."},
                status_code=401,
            )

        return await call_next(request)
```

---

### 3.2 Dynamic Per-Request Tenant Credential Injection (`X-Env-...`)
Behind the gateway, buyer credentials are strip-filtered from process environments and transmitted as request headers:
* `X-Env-BINANCE-ENV` (`mainnet` or `testnet`)
* `X-Env-BINANCE-READ-API-KEY`
* `X-Env-BINANCE-READ-API-SECRET`

In asynchronous Python, this requires **`contextvars`** to ensure thread and coroutine isolation without cross-tenant bleed:

```python
import contextvars
from dataclasses import dataclass
from binance.client import Client

@dataclass(frozen=True)
class TenantContext:
    env: str
    api_key: str
    api_secret: str

current_tenant: contextvars.ContextVar[TenantContext | None] = contextvars.ContextVar(
    "current_tenant", default=None
)

def resolve_client() -> Client:
    """Resolve Binance client scoped to the current active HTTP request."""
    ctx = current_tenant.get()
    if ctx and ctx.api_key and ctx.api_secret:
        return Client(ctx.api_key, ctx.api_secret, testnet=(ctx.env == "testnet"))
    # Fallback to server environment keys if running in single-tenant/self-hosted mode
    return Client(
        os.environ.get("BINANCE_READ_API_KEY", ""),
        os.environ.get("BINANCE_READ_API_SECRET", ""),
        testnet=(os.environ.get("BINANCE_ENV", "testnet") == "testnet"),
    )
```

---

## 4. Production Dockerfile for Railway

```dockerfile
# Multi-stage lean Python container
FROM python:3.12-slim-bookworm as builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir --upgrade pip hatchling uvicorn starlette
COPY src/ src/
RUN pip install --no-cache-dir .

FROM python:3.12-slim-bookworm as runner
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    TRANSPORT=sse

EXPOSE 8000

CMD ["python", "-m", "krmaazha_binance_mcp.server", "--transport", "sse", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 5. Unit Economics & Margin Defense

| Tier | Price | Monthly Call Quota | Binance Weight Cost | Railway Cost | Net Profit Margin |
|---|---|---|---|---|---|
| **Free Trial** | $0 | 250 calls / 3 days | ~250 weight | Absorbed in base | Acquisition funnel |
| **Starter** | $19/mo | 10,000 calls | ~10k weight (~0.23 wt/min) | $5/mo fixed base | **~73% (1 user) to 95%+ (5 users)** |
| **Pro** | $49/mo | 50,000 calls | ~50k weight (~1.15 wt/min) | $5/mo fixed base | **~89% (1 user) to 98%+ (5 users)** |

### Safeguards:
1. **IP Weight Consumption**: 10,000 calls/mo averages only **0.23 wt/min** out of Binance's 1,200 wt/min IP rate limit. Upstream Binance API cost is $0.
2. **Abuse Protection**: Implement a per-token burst throttle (e.g. max 10 requests/sec) to prevent a rogue buyer from exhausting the container or IP rate limit in a single burst.

---

## 6. Railway Cloud Operations & Deployment Troubleshooting

When deploying commercial MCP servers to Railway, common deployment blockers must be automatically audited and resolved:

### 6.1 Builder Misconfiguration (Nixpacks vs Dockerfile)
* **Symptom**: Railway Settings shows `Builder: The value is set in /railway.toml Nixpacks (Deprecated)` or links to an outdated repository.
* **Root Cause**: The service was cloned or configured with legacy Config-as-Code pointing to an old repository.
* **Resolution**:
  1. In Railway Service -> **Settings** -> **Build** -> **Builder**, change from `Nixpacks` to **`Dockerfile`**.
  2. In Railway Service -> **Settings** -> **Config-as-code**, clear any path referencing `/railway.toml` from old repos.
  3. Ensure root `Dockerfile` and `railway.toml` specify `builder = "dockerfile"`.

### 6.2 Pending Staged Changes
* **Symptom**: Railway top bar displays `Apply N changes | Deploy ⇧+Enter`.
* **Root Cause**: Variables, domain ports, or build settings were modified in the web UI but not committed to a deployment.
* **Resolution**: Click **Deploy** (or press `Shift + Enter`) to apply staged environment variables and triggers.

### 6.3 Account Trial Status & Billing Gates
* **Symptom**: Top bar displays `Trial expired` and deployment fails to start or remains paused.
* **Root Cause**: Railway provides a one-time $5 trial credit. Once expired, container provisioning and scaling are halted.
* **Resolution**:
  1. Navigate to Railway Workspace -> **Upgrade**.
  2. Select the **Hobby Plan** ($5/mo with $5 included usage) or link a verified credit card.
  3. Once active, deployments immediately resume container builds.
