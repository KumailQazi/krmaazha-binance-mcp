"""Unit tests for the multi-agent system and Master Orchestrator Agent."""
from __future__ import annotations

from krmaazha_binance_mcp.agents import (
    DashboardUXAgent,
    DataEngineeringAgent,
    MasterOrchestratorAgent,
    McpProtocolAgent,
    QuantitativeRiskAgent,
    SecurityGuardAgent,
)


def test_agent_directory_contains_all_agents():
    orch = MasterOrchestratorAgent()
    directory = orch.get_agent_directory()
    assert len(directory) == 6
    agent_ids = {a["agent_id"] for a in directory}
    assert agent_ids == {
        "master_orchestrator",
        "data_engineering",
        "security_guard",
        "quant_risk",
        "mcp_protocol",
        "dashboard_ux",
    }


def test_data_engineering_agent_evaluation():
    agent = DataEngineeringAgent()
    msg = agent.evaluate({"symbol": "BTCUSDT", "interval": "1h"})
    assert msg.sender_id == "data_engineering"
    assert msg.epistemic_tag == "[VERIFIED FACT]"
    assert msg.details["closed_bar_windowing"] == "ENFORCED"
    assert "Data Engineering Audit: PASSED" in msg.summary


def test_security_guard_agent_evaluation():
    agent = SecurityGuardAgent()
    msg = agent.evaluate({"action": "market_analysis"})
    assert msg.sender_id == "security_guard"
    assert msg.epistemic_tag == "[VERIFIED FACT]"
    assert msg.details["confirmer_gate_required"] is False
    assert "Security Audit: PASSED" in msg.summary

    trade_msg = agent.evaluate({"action": "trade"})
    assert trade_msg.details["confirmer_gate_required"] is True


def test_quant_risk_agent_evaluation():
    agent = QuantitativeRiskAgent()
    context = {
        "symbol": "SOLUSDT",
        "price": 120.0,
        "spread_bps": 2.5,
        "depth_1pct_usdt": 2000000,
        "rsi": 55.0,
        "trend": "Bullish Consolidation",
    }
    msg = agent.evaluate(context)
    assert msg.sender_id == "quant_risk"
    assert msg.epistemic_tag == "[QUANTITATIVE ESTIMATE]"
    setup = msg.details["trade_setup"]
    assert setup["direction"] == "LONG"
    assert "net_rr" in setup
    assert "gross_rr" in setup


def test_mcp_protocol_agent_evaluation():
    agent = McpProtocolAgent()
    valid_context = {
        "order": {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "quantity": "0.01",
        }
    }
    msg = agent.evaluate(valid_context)
    assert msg.sender_id == "mcp_protocol"
    assert msg.details["protocol_status"] == "COMPLIANT"

    invalid_context = {
        "order": {
            "symbol": "BTCUSDT",
        }
    }
    invalid_msg = agent.evaluate(invalid_context)
    assert invalid_msg.details["protocol_status"] == "INVALID"


def test_dashboard_ux_agent_microcap_precision():
    agent = DashboardUXAgent()
    assert agent.format_price("0.00001234") == "$0.00001234"
    assert agent.format_price("0.002452") == "$0.002452"
    assert agent.format_price("0.152") == "$0.1520"
    assert agent.format_price("120.50") == "$120.50"
    assert agent.format_price("65000.00") == "$65,000.00"

    msg = agent.evaluate({"symbol": "NOMUSDT", "price": "0.002452"})
    assert msg.details["formatted_price"] == "$0.002452"


def test_master_orchestrator_synthesis(monkeypatch):
    orch = MasterOrchestratorAgent()

    # Mock _fetch_live_binance_depth to be deterministic without network calls
    def mock_fetch(symbol):
        return {
            "symbol": symbol,
            "price": "120.50",
            "bid": "120.48",
            "ask": "120.52",
            "spread_bps": "3.32",
            "depth_1pct_usdt": "2500000",
        }

    monkeypatch.setattr(orch, "_fetch_live_binance_depth", mock_fetch)

    result = orch.orchestrate("SOLUSDT")
    assert result["instrument"]["symbol"] == "SOLUSDT"
    assert len(result["deliberation_log"]) == 5
    assert result["deliberation_log"][0]["agent"] == "Data Systems & Pipeline Engineering Agent"
    assert "At" in result["standardized_bottom_line"]
    assert "Otherwise, no trade." in result["standardized_bottom_line"]

    # Test agent evaluate
    eval_msg = orch.evaluate({"symbol": "SOLUSDT"})
    assert eval_msg.sender_id == "master_orchestrator"
    assert "Otherwise, no trade." in eval_msg.summary
