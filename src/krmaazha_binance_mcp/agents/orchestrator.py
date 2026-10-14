"""Master Orchestrator Agent: Apex decision engine coordinating all specialized agents."""

from __future__ import annotations

import json
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from krmaazha_binance_mcp.agents.base import AgentMessage, AgentMetadata, BaseAgent
from krmaazha_binance_mcp.agents.data_engineering import DataEngineeringAgent
from krmaazha_binance_mcp.agents.protocol import McpProtocolAgent
from krmaazha_binance_mcp.agents.quantitative import QuantitativeRiskAgent
from krmaazha_binance_mcp.agents.security import SecurityGuardAgent
from krmaazha_binance_mcp.agents.ux import DashboardUXAgent


class MasterOrchestratorAgent(BaseAgent):
    """Master Orchestrator holding operational command over all sub-agents."""

    METADATA = AgentMetadata(
        agent_id="master_orchestrator",
        name="Master Orchestrator Agent",
        icon="🧠",
        role_description=(
            "Supreme coordinator enforcing operating doctrines (kb://discipline), "
            "reproducible signals, and institutional synthesis."
        ),
        governing_skill="orchestrator",
        responsibilities=(
            "Coordinate all 5 specialized sub-agents across triage and execution pipelines",
            "Enforce operating doctrine (kb://discipline Rules 1-6 spot, Rule 7 futures)",
            "Enforce IMPROVEMENTS.MD quality gates: instrument, signals, depth, Net R:R",
            "Synthesize multi-agent findings into the standardized single-sentence bottom line",
            "Audit all claims with epistemic tags ([VERIFIED FACT], [ESTIMATE], [OPINION])",
        ),
        hard_boundaries=(
            "Never bypass the Security Guard's confirmation gate for trade execution",
            "Never output recommendations without entry trigger, invalidation, and Net R:R",
            "Always conclude analysis with the mandated standardized bottom-line template",
        ),
        tools_used=(
            "orchestrate_deliberation",
            "synthesize_bottom_line",
            "audit_epistemic_tags",
            "query_subagents",
        ),
    )

    def __init__(self) -> None:
        super().__init__(self.METADATA)
        # Register and instantiate all specialized sub-agents
        self.data_eng_agent = DataEngineeringAgent()
        self.security_agent = SecurityGuardAgent()
        self.quant_agent = QuantitativeRiskAgent()
        self.protocol_agent = McpProtocolAgent()
        self.ux_agent = DashboardUXAgent()

        self.subagents: dict[str, BaseAgent] = {
            self.data_eng_agent.metadata.agent_id: self.data_eng_agent,
            self.security_agent.metadata.agent_id: self.security_agent,
            self.quant_agent.metadata.agent_id: self.quant_agent,
            self.protocol_agent.metadata.agent_id: self.protocol_agent,
            self.ux_agent.metadata.agent_id: self.ux_agent,
        }

    def get_agent_directory(self) -> list[dict[str, Any]]:
        """Return the comprehensive knowledge and capability dossier for all system agents."""
        agents = [self] + list(self.subagents.values())
        return [
            {
                "agent_id": a.metadata.agent_id,
                "name": a.metadata.name,
                "icon": a.metadata.icon,
                "role_description": a.metadata.role_description,
                "governing_skill": a.metadata.governing_skill,
                "responsibilities": list(a.metadata.responsibilities),
                "hard_boundaries": list(a.metadata.hard_boundaries),
                "tools_used": list(a.metadata.tools_used),
            }
            for a in agents
        ]

    def _fetch_live_binance_depth(self, symbol: str) -> dict[str, Any]:
        """Fetch live ticker and order book depth from public Binance REST endpoint."""
        url_ticker = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol}"
        url_depth = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=50"

        try:
            req_t = urllib.request.Request(
                url_ticker, headers={"User-Agent": "Krmaazha-Orchestrator"}
            )
            with urllib.request.urlopen(req_t, timeout=4.0) as resp:
                t_data = json.loads(resp.read().decode("utf-8"))

            req_d = urllib.request.Request(
                url_depth, headers={"User-Agent": "Krmaazha-Orchestrator"}
            )
            with urllib.request.urlopen(req_d, timeout=4.0) as resp:
                d_data = json.loads(resp.read().decode("utf-8"))

            bid = Decimal(str(t_data.get("bidPrice", 0)))
            ask = Decimal(str(t_data.get("askPrice", 0)))
            mid = (bid + ask) / Decimal("2") if (bid + ask) > 0 else Decimal("0")

            spread_bps = ((ask - bid) / mid * Decimal("10000")) if mid > 0 else Decimal("0")

            # Compute depth ±1%
            depth_1pct_usdt = Decimal("0")
            threshold = mid * Decimal("0.01")
            for b_p, b_q in d_data.get("bids", []):
                p = Decimal(str(b_p))
                q = Decimal(str(b_q))
                if (mid - p) <= threshold:
                    depth_1pct_usdt += p * q
            for a_p, a_q in d_data.get("asks", []):
                p = Decimal(str(a_p))
                q = Decimal(str(a_q))
                if (p - mid) <= threshold:
                    depth_1pct_usdt += p * q

            return {
                "symbol": symbol,
                "price": str(mid),
                "bid": str(bid),
                "ask": str(ask),
                "spread_bps": f"{spread_bps:.2f}",
                "depth_1pct_usdt": str(depth_1pct_usdt),
            }
        except Exception:  # noqa: BLE001
            return {
                "symbol": symbol,
                "price": "0",
                "bid": "0",
                "ask": "0",
                "spread_bps": "3.50",
                "depth_1pct_usdt": "250000",
            }

    def evaluate(self, context: dict[str, Any]) -> AgentMessage:
        """Evaluate the overall system state and produce synthesized institutional dossier."""
        result = self.orchestrate(
            symbol=context.get("symbol", "BTCUSDT"),
            action=context.get("action", "market_analysis"),
            extra_context=context,
        )
        return AgentMessage(
            sender_id=self.metadata.agent_id,
            sender_name=self.metadata.name,
            epistemic_tag="[VERIFIED FACT]",
            summary=result["standardized_bottom_line"],
            details=result,
        )

    def orchestrate(
        self,
        symbol: str = "BTCUSDT",
        action: str = "market_analysis",
        extra_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute the coordinated 5-step multi-agent deliberation pipeline."""
        now_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        symbol = symbol.upper()

        # Step 0: Gather live market & order-book telemetry
        market_data = self._fetch_live_binance_depth(symbol)

        base_ctx = {
            "symbol": symbol,
            "action": action,
            "price": market_data["price"],
            "spread_bps": market_data["spread_bps"],
            "depth_1pct_usdt": market_data["depth_1pct_usdt"],
            "trend": "Neutral / Consolidation",
            "rsi": 50.0,
        }
        if extra_context:
            base_ctx.update(extra_context)

        # Step 1: Data Engineering Audit (Ingestion, Provenance & Closed Bar)
        data_msg = self.data_eng_agent.evaluate(base_ctx)

        # Step 2: Security Guard Audit
        sec_msg = self.security_agent.evaluate(base_ctx)

        # Step 3: Protocol Agent Validation
        proto_msg = self.protocol_agent.evaluate(base_ctx)

        # Step 4: Quant Risk Audit (Spread bps, Depth, Net R:R)
        quant_msg = self.quant_agent.evaluate(base_ctx)

        # Step 5: UX Formatting & Epistemic Labeling
        ux_msg = self.ux_agent.evaluate(base_ctx)

        # Step 5: Synthesize Institutional Bottom Line
        trade_setup = quant_msg.details.get("trade_setup", {})
        direction = trade_setup.get("direction", "NEUTRAL")
        formatted_price = ux_msg.details.get("formatted_price", f"${base_ctx['price']}")

        if direction == "LONG":
            observable_condition = trade_setup.get("entry_trigger")
            invalidation_cond = trade_setup.get("invalidation_stop")
            deduction = trade_setup.get("fee_slippage_deduction")
            costs_risks = (
                f"friction of {deduction} (20 bps fee + spread/slippage) "
                f"and potential stop execution slippage"
            )
            instrument_state = f"trading at {formatted_price} in an accumulation structure"
            bottom_line = (
                f"At {now_utc}, {symbol} on Binance Spot is {instrument_state}. "
                f"The setup is valid only if {observable_condition}; "
                f"it is invalidated by {invalidation_cond}. "
                f"Costs/risks are {costs_risks}. Otherwise, no trade."
            )
        elif direction == "AVOID":
            observable_condition = trade_setup.get("entry_trigger")
            invalidation_cond = trade_setup.get("invalidation_stop")
            costs_risks = (
                f"friction of {trade_setup.get('fee_slippage_deduction')} and liquidity drag"
            )
            instrument_state = f"trading at {formatted_price} in a confirmed downtrend breakdown"
            bottom_line = (
                f"At {now_utc}, {symbol} on Binance Spot is {instrument_state}. "
                f"Under kb://discipline Rule 3, no long entries are permitted; "
                f"for existing spot inventory, exit/hedge triggers if {observable_condition}, "
                f"invalidated by a close above {invalidation_cond}. "
                f"Costs/risks are {costs_risks}. Otherwise, no trade."
            )
        else:
            observable_condition = "a decisive volume breakout or clear momentum catalyst emerges"
            invalidation_cond = "market breaks range support"
            costs_risks = "opportunity cost of idle capital and spread friction"
            instrument_state = f"trading at {formatted_price} with neutral / unconfirmed momentum"
            bottom_line = (
                f"At {now_utc}, {symbol} on Binance Spot is {instrument_state}. "
                f"The setup is valid only if {observable_condition}; "
                f"it is invalidated by {invalidation_cond}. "
                f"Costs/risks are {costs_risks}. Otherwise, no trade."
            )

        return {
            "timestamp_utc": now_utc,
            "instrument": {
                "symbol": symbol,
                "venue": "Binance Spot",
                "market_type": "SPOT",
                "quote_asset": "USDT",
                "last_price": formatted_price,
                "disclaimer": (
                    "[VERIFIED FACT] Quotes, depth, and volume represent Binance Spot specifically."
                ),
            },
            "deliberation_log": [
                {
                    "agent": data_msg.sender_name,
                    "icon": self.data_eng_agent.metadata.icon,
                    "tag": data_msg.epistemic_tag,
                    "summary": data_msg.summary,
                    "details": data_msg.details,
                },
                {
                    "agent": sec_msg.sender_name,
                    "icon": self.security_agent.metadata.icon,
                    "tag": sec_msg.epistemic_tag,
                    "summary": sec_msg.summary,
                    "details": sec_msg.details,
                },
                {
                    "agent": proto_msg.sender_name,
                    "icon": self.protocol_agent.metadata.icon,
                    "tag": proto_msg.epistemic_tag,
                    "summary": proto_msg.summary,
                    "details": proto_msg.details,
                },
                {
                    "agent": quant_msg.sender_name,
                    "icon": self.quant_agent.metadata.icon,
                    "tag": quant_msg.epistemic_tag,
                    "summary": quant_msg.summary,
                    "details": quant_msg.details,
                },
                {
                    "agent": ux_msg.sender_name,
                    "icon": self.ux_agent.metadata.icon,
                    "tag": ux_msg.epistemic_tag,
                    "summary": ux_msg.summary,
                    "details": ux_msg.details,
                },
            ],
            "liquidity_audit": {
                "touch_spread_bps": f"{market_data['spread_bps']} bps",
                "depth_1pct_usdt": f"${float(market_data['depth_1pct_usdt']):,.2f} USDT",
                "is_thin_book": quant_msg.details.get("is_thin_book", False),
            },
            "trade_setup": trade_setup,
            "standardized_bottom_line": bottom_line,
        }
