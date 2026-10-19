"""Execution Algorithm & Smart Routing Agent: TWAP, VWAP, Iceberg, and micro-cap routing."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from krmaazha_binance_mcp.agents.base import AgentMessage, AgentMetadata, BaseAgent


class ExecutionAlgorithmAgent(BaseAgent):
    """Specialized agent designing execution trajectories, order slicing, and slippage controls."""

    METADATA = AgentMetadata(
        agent_id="execution_algorithms",
        name="Execution Algorithm & Smart Routing Agent",
        icon="🎯",
        role_description=(
            "Designs institutional execution trajectories (TWAP, VWAP, Iceberg), "
            "calculates liquidity band friction, and models sub-cent micro-cap precision routing."
        ),
        governing_skill="execution-algorithms",
        responsibilities=(
            "Formulate optimal execution schedules (TWAP, VWAP, Iceberg slicing) relative to depth",
            "Mitigate micro-cap thin-book slippage by auditing ±1% and ±2% liquidity bands",
            "Enforce bit-perfect sub-cent price alignment with LOT_SIZE and PRICE_FILTER",
            "Model comprehensive Net Friction (exchange fee + half spread + market impact)",
            "Generate structured execution plans for physical human verification before submission",
        ),
        hard_boundaries=(
            "Never execute orders directly without human physical approval at the confirmer gate",
            "Never permit an order slice to exceed 10% of ±1% depth without slippage warnings",
            "Never perform financial sizing or friction arithmetic using floating-point numbers",
        ),
        tools_used=(
            "compute_twap_schedule",
            "compute_vwap_weights",
            "slice_iceberg_order",
            "estimate_market_impact",
        ),
    )

    def __init__(self) -> None:
        super().__init__(self.METADATA)

    @staticmethod
    def plan_execution_trajectory(
        notional_usdt: Decimal,
        depth_1pct_usdt: Decimal,
        spread_bps: Decimal,
    ) -> dict[str, Any]:
        """Compute execution trajectory and slicing recommendations based on order book depth."""
        fee_bps = Decimal("20.0")  # 20 bps standard round-trip Binance spot fee
        half_spread_bps = spread_bps / Decimal("2")

        # Market impact model: Impact bps ≈ (Order Notional / Depth ±1%) * 100
        if depth_1pct_usdt > 0:
            participation_rate = (notional_usdt / depth_1pct_usdt) * Decimal("100")
            impact_bps = participation_rate * Decimal("0.8")
        else:
            participation_rate = Decimal("100")
            impact_bps = Decimal("250.0")  # Severely illiquid

        total_friction_bps = fee_bps + half_spread_bps + impact_bps

        # Slicing algorithm
        if participation_rate > Decimal("5.0") or notional_usdt > Decimal("50000"):
            algorithm = "TWAP"
            slices = max(3, min(12, int(participation_rate / Decimal("2"))))
            slice_size_usdt = notional_usdt / Decimal(str(slices))
        else:
            algorithm = "DIRECT_LIMIT"
            slices = 1
            slice_size_usdt = notional_usdt

        return {
            "algorithm": algorithm,
            "slices": slices,
            "slice_size_usdt": str(slice_size_usdt.quantize(Decimal("0.01"))),
            "participation_rate_pct": f"{participation_rate:.2f}%",
            "estimated_impact_bps": f"{impact_bps:.1f}",
            "total_friction_bps": f"{total_friction_bps:.1f}",
            "is_high_slippage_risk": bool(participation_rate > Decimal("10.0")),
        }

    def evaluate(self, context: dict[str, Any]) -> AgentMessage:
        """Evaluate order size, depth bands, and generate optimal execution trajectory."""
        symbol = context.get("symbol", "BTCUSDT")
        notional_raw = context.get("notional_usdt", "1000.0")
        depth_raw = context.get("depth_1pct_usdt", "500000.0")
        spread_raw = context.get("spread_bps", "2.5")

        notional = Decimal(str(notional_raw))
        depth = Decimal(str(depth_raw))
        spread = Decimal(str(spread_raw))

        plan = self.plan_execution_trajectory(notional, depth, spread)
        findings: list[str] = [
            f"Execution Trajectory for {symbol}: Strategy is {plan['algorithm']} "
            f"({plan['slices']} slices).",
            f"Slice size: ${plan['slice_size_usdt']} USDT "
            f"({plan['participation_rate_pct']} of ±1% book depth).",
            f"Estimated Net Friction: {plan['total_friction_bps']} bps "
            f"(Fee: 20 bps, Spread/Impact: {plan['estimated_impact_bps']} bps).",
        ]

        if plan["is_high_slippage_risk"]:
            findings.append("CAUTION: Thin liquidity book! High market impact anticipated.")

        summary = (
            f"Execution Strategy: {plan['algorithm']}. Slices: {plan['slices']} x "
            f"${plan['slice_size_usdt']}. Friction: {plan['total_friction_bps']} bps."
        )

        return AgentMessage(
            sender_id=self.metadata.agent_id,
            sender_name=self.metadata.name,
            epistemic_tag="[QUANTITATIVE ESTIMATE]",
            summary=summary,
            details={
                "symbol": symbol,
                "notional_usdt": str(notional),
                "execution_plan": plan,
                "findings": findings,
            },
        )
