"""Commercial Gateway & Cloud Deployment Agent: Manages paid marketplace syndication & hosting."""

from __future__ import annotations

import secrets
from typing import Any

from krmaazha_binance_mcp.agents.base import AgentMessage, AgentMetadata, BaseAgent


class CommercialGatewayAgent(BaseAgent):
    """Specialized agent governing commercial gateway authentication and cloud hosting."""

    METADATA = AgentMetadata(
        agent_id="commercial_gateway",
        name="Commercial Gateway & Cloud Deployment Agent",
        icon="🚀",
        role_description=(
            "Governs commercial MCP marketplace syndication, gateway token verification "
            "(x-mcprush-token), per-request tenant credential isolation (X-Env headers), "
            "Railway cloud hosting, and unit economics."
        ),
        governing_skill="mcprush-gateway-deployment",
        responsibilities=(
            "Validate incoming MCPRush gateway tokens (x-mcprush-token) via constant-time check",
            "Extract and isolate per-buyer credentials from X-Env headers into request context",
            "Audit Railway deployment readiness (persistent SSE, zero cold starts, health checks)",
            "Enforce tenant rate limits and defend upstream Binance IP weight budget (1200 wt/min)",
            "Model subscription plan margins (Starter $19/mo, Pro $49/mo) and free trial quotas",
            "Prevent cross-tenant credential leakage across concurrent asynchronous requests",
        ),
        hard_boundaries=(
            "Never execute a tool call without a verified x-mcprush-token in gateway mode",
            "Never leak tenant API keys or secrets in error traces, logs, or responses",
            "Never allow one tenant to consume > 20% of upstream IP rate limit budget in 1 minute",
            "Always maintain fallback to local/self-hosted stdio mode for open-source users",
        ),
        tools_used=(
            "verify_gateway_token",
            "extract_tenant_credentials",
            "evaluate_pricing_tier_margin",
            "check_railway_readiness",
        ),
    )

    def __init__(self) -> None:
        super().__init__(self.METADATA)

    @staticmethod
    def verify_gateway_token(provided_token: str | None, expected_token: str | None) -> bool:
        """Verify x-mcprush-token using constant-time comparison to prevent timing attacks."""
        if not provided_token or not expected_token:
            return False
        return secrets.compare_digest(provided_token.strip(), expected_token.strip())

    @staticmethod
    def extract_tenant_credentials(headers: dict[str, str]) -> dict[str, str | None]:
        """Extract buyer-specific credentials passed via X-Env headers behind MCPRush gateway."""
        norm_headers = {k.lower(): v for k, v in headers.items()}
        return {
            "env": norm_headers.get("x-env-binance-env", "testnet"),
            "api_key": norm_headers.get("x-env-binance-read-api-key"),
            "api_secret": norm_headers.get("x-env-binance-read-api-secret"),
        }

    @staticmethod
    def evaluate_pricing_tier_margin(
        plan_name: str,
        price_monthly_usd: float,
        call_quota: int,
        railway_monthly_base_usd: float = 5.0,
    ) -> dict[str, Any]:
        """Audit unit economics, rate limit impact, and gross margins for a subscription plan."""
        avg_weight_per_call = 1.0
        total_monthly_weight = call_quota * avg_weight_per_call
        avg_weight_per_minute = total_monthly_weight / 43200.0
        pct_of_binance_limit = (avg_weight_per_minute / 1200.0) * 100.0

        net_profit_single_user = price_monthly_usd - railway_monthly_base_usd
        margin_single_user_pct = (
            (net_profit_single_user / price_monthly_usd) * 100.0 if price_monthly_usd > 0 else 0.0
        )

        is_healthy = pct_of_binance_limit < 5.0 and margin_single_user_pct > 50.0
        return {
            "plan_name": plan_name,
            "monthly_price": price_monthly_usd,
            "monthly_calls": call_quota,
            "avg_weight_per_minute": round(avg_weight_per_minute, 4),
            "pct_of_binance_limit": round(pct_of_binance_limit, 4),
            "railway_base_cost": railway_monthly_base_usd,
            "net_profit_at_1_subscriber": round(net_profit_single_user, 2),
            "margin_at_1_subscriber_pct": round(margin_single_user_pct, 1),
            "status": "HEALTHY" if is_healthy else "REVIEW",
        }

    @staticmethod
    def audit_railway_settings(
        builder: str = "dockerfile",
        has_pending_changes: bool = False,
        account_status: str = "active",
        config_path: str | None = None,
    ) -> dict[str, Any]:
        """Audit specific Railway settings: builder type, pending changes, and billing status."""
        is_dockerfile = builder.lower() == "dockerfile"
        has_stale_config = bool(config_path and "pulse-revenue" in config_path)
        builder_ready = is_dockerfile and not has_stale_config

        is_paid_or_active = account_status.lower() in ("active", "paid", "hobby", "pro")

        issues: list[str] = []
        if not builder_ready:
            issues.append(
                "Builder misconfigured: switch from Nixpacks/stale config to Dockerfile"
            )
        if has_pending_changes:
            issues.append(
                "Pending staged changes detected: click Deploy (Shift+Enter) to apply"
            )
        if not is_paid_or_active:
            issues.append(
                "Railway trial expired: add payment card or upgrade to $5/mo Hobby plan"
            )

        return {
            "builder_status": "READY" if builder_ready else "MISCONFIGURED_BUILDER",
            "deployment_status": "READY" if not has_pending_changes else "NEEDS_DEPLOY",
            "account_status": "HEALTHY" if is_paid_or_active else "TRIAL_EXPIRED",
            "issues": issues,
            "can_deploy": builder_ready and not has_pending_changes and is_paid_or_active,
        }

    @staticmethod
    def check_railway_readiness(
        has_dockerfile: bool,
        has_port_env: bool,
        has_sse_transport: bool,
        has_token_auth: bool,
    ) -> dict[str, str]:
        """Check cloud deployment readiness for Railway hosting."""
        return {
            "containerization": "READY" if has_dockerfile else "NEEDS_DOCKERFILE",
            "port_configuration": "READY" if has_port_env else "NEEDS_PORT_ENV",
            "sse_transport": "READY" if has_sse_transport else "NEEDS_SSE_FLAG",
            "gateway_auth": "READY" if has_token_auth else "NEEDS_TOKEN_MIDDLEWARE",
        }

    def evaluate(self, context: dict[str, Any]) -> AgentMessage:
        """Evaluate commercial gateway deployment status, unit economics, and cloud readiness."""
        plan_name = context.get("plan_name", "Starter")
        price = float(context.get("price", 19.0))
        quota = int(context.get("quota", 10000))

        margin_info = self.evaluate_pricing_tier_margin(plan_name, price, quota)
        readiness = self.check_railway_readiness(
            has_dockerfile=context.get("has_dockerfile", True),
            has_port_env=context.get("has_port_env", True),
            has_sse_transport=context.get("has_sse_transport", True),
            has_token_auth=context.get("has_token_auth", True),
        )
        railway_audit = self.audit_railway_settings(
            builder=str(context.get("builder", "dockerfile")),
            has_pending_changes=bool(context.get("has_pending_changes", False)),
            account_status=str(context.get("account_status", "active")),
            config_path=context.get("config_path"),
        )

        margin_pct = margin_info["margin_at_1_subscriber_pct"]
        status = margin_info["status"]
        if railway_audit["issues"]:
            issue_str = "; ".join(railway_audit["issues"])
            summary = (
                f"[QUANTITATIVE ESTIMATE] Commercial Gateway: Action Required before deployment. "
                f"Issues: {issue_str}."
            )
        else:
            summary = (
                f"[QUANTITATIVE ESTIMATE] Commercial Gateway: Ready for Railway deployment under "
                f"{plan_name} plan (${price}/mo, {quota:,} calls). Net margin: {margin_pct}%. "
                f"Status: {status}."
            )

        return AgentMessage(
            sender_id=self.metadata.agent_id,
            sender_name=self.metadata.name,
            epistemic_tag="[QUANTITATIVE ESTIMATE]",
            summary=summary,
            details={
                "readiness": readiness,
                "railway_audit": railway_audit,
                "margin_analysis": margin_info,
                "tier": plan_name,
                "quota": quota,
            },
        )
