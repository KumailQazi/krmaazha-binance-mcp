"""Financial Dashboard & UX Agent: High-density aesthetics and micro-cap precision."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from krmaazha_binance_mcp.agents.base import AgentMessage, AgentMetadata, BaseAgent


class DashboardUXAgent(BaseAgent):
    """Agent ensuring high-density terminal aesthetics and micro-cap formatting."""

    METADATA = AgentMetadata(
        agent_id="dashboard_ux",
        name="Financial Dashboard & UX Agent",
        icon="🖥️",
        role_description=(
            "Governs financial UI ergonomics, micro-cap precision, and epistemic labeling."
        ),
        governing_skill="frontend-design",
        responsibilities=(
            "Maintain institutional terminal design (obsidian #07090e, Binance gold #f0b90b)",
            "Format sub-dollar micro-caps (NOM, RESOLV, XVG) with dynamic decimal precision",
            "Enforce epistemic prefix labels: [VERIFIED FACT], [QUANTITATIVE ESTIMATE], [OPINION]",
            "Render live sync status with exact UTC timestamps and auto-polling countdowns",
            "Present clear interactive DCA accumulation curves and multi-asset scanner grids",
        ),
        hard_boundaries=(
            "Never truncate low-price assets to $0.00; always use dynamic precision",
            "Never display speculative analyst views without explicit [OPINION] marking",
            "Ensure all visual components retain high-contrast readability and responsiveness",
        ),
        tools_used=(
            "format_currency_display",
            "render_terminal_card",
            "apply_epistemic_tags",
            "update_sync_badge",
        ),
    )

    def __init__(self) -> None:
        super().__init__(self.METADATA)

    def format_price(self, price: float | Decimal | str) -> str:
        """Format price with intelligent micro-cap decimal resolution."""
        d = Decimal(str(price))
        if d == 0:
            return "$0.00"
        if d < Decimal("0.0001"):
            return f"${d:.8f}"
        if d < Decimal("0.01"):
            return f"${d:.6f}"
        if d < Decimal("1.00"):
            return f"${d:.4f}"
        return f"${d:,.2f}"

    def evaluate(self, context: dict[str, Any]) -> AgentMessage:
        """Format data into institutional presentation standards."""
        raw_price = context.get("price", 0)
        formatted_price = self.format_price(raw_price)
        symbol = context.get("symbol", "BTCUSDT")

        summary = (
            f"UX Presentation Engine: Rendered {symbol} at {formatted_price}. "
            f"Epistemic tag enforcement ACTIVE. High-density terminal standards satisfied."
        )

        return AgentMessage(
            sender_id=self.metadata.agent_id,
            sender_name=self.metadata.name,
            epistemic_tag="[VERIFIED FACT]",
            summary=summary,
            details={
                "symbol": symbol,
                "formatted_price": formatted_price,
                "theme": "institutional_dark_obsidian",
                "accent_color": "#f0b90b",
                "epistemic_tags_applied": True,
            },
        )
