"""Unit tests for the multi-agent system and Master Orchestrator Agent."""
from __future__ import annotations

from decimal import Decimal

from krmaazha_binance_mcp.agents import (
    ComplianceAuditAgent,
    DashboardUXAgent,
    DataEngineeringAgent,
    ExecutionAlgorithmAgent,
    MasterOrchestratorAgent,
    McpProtocolAgent,
    QuantitativeRiskAgent,
    RegistrySyndicationAgent,
    SecurityGuardAgent,
)


def test_agent_directory_contains_all_agents():
    orch = MasterOrchestratorAgent()
    directory = orch.get_agent_directory()
    assert len(directory) == 9
    agent_ids = {a["agent_id"] for a in directory}
    assert agent_ids == {
        "master_orchestrator",
        "data_engineering",
        "security_guard",
        "quant_risk",
        "mcp_protocol",
        "dashboard_ux",
        "registry_syndication",
        "compliance_audit",
        "execution_algorithms",
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
    msg = agent.evaluate({
        "action": "market_analysis",
        "privacy_content": "We maintain zero telemetry and user-owned key isolation.",
    })
    assert msg.sender_id == "security_guard"
    assert msg.epistemic_tag == "[VERIFIED FACT]"
    assert msg.details["confirmer_gate_required"] is False
    assert "Security Audit: PASSED" in msg.summary
    assert msg.details["m8ven_trust_verified"] is True

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

    # Test manifest validation
    manifest = {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
        "name": "io.github.KumailQazi/krmaazha-binance-mcp",
        "version": "1.2.2",
        "packages": [{"registryType": "pypi", "identifier": "krmaazha-binance-mcp"}],
    }
    manifest_msg = agent.evaluate({
        "manifest": manifest,
        "readme_content": "<sub>mcp-name: io.github.KumailQazi/krmaazha-binance-mcp</sub>",
    })
    assert manifest_msg.details["protocol_status"] == "COMPLIANT"

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


def test_registry_syndication_agent():
    agent = RegistrySyndicationAgent()
    assert agent.verify_version_lockstep("1.2.2", "1.2.2", "1.2.2") is True
    assert agent.verify_version_lockstep("1.2.2", "1.2.1", "1.2.2") is False

    files = agent.audit_syndication_files(
        has_server_json=True, has_smithery_yaml=True, has_glama_json=True
    )
    assert files["mcp_registry"] == "READY"
    assert files["smithery"] == "READY"
    assert files["glama"] == "READY"

    msg = agent.evaluate({
        "pyproject_version": "1.2.2",
        "server_version": "1.2.2",
        "changelog_version": "1.2.2",
    })
    assert msg.sender_id == "registry_syndication"
    assert msg.epistemic_tag == "[VERIFIED FACT]"
    assert msg.details["version_lockstep"] is True
    assert "VERIFIED" in msg.summary


def test_compliance_audit_agent():
    agent = ComplianceAuditAgent()
    compliant, msg_text = agent.audit_non_custodial_posture(
        has_ephemeral_dialog=True, server_holds_trade_key=False
    )
    assert compliant is True
    assert "COMPLIANT" in msg_text

    non_compliant, _ = agent.audit_non_custodial_posture(
        has_ephemeral_dialog=False, server_holds_trade_key=True
    )
    assert non_compliant is False

    msg = agent.evaluate({"has_ephemeral_dialog": True, "server_holds_trade_key": False})
    assert msg.sender_id == "compliance_audit"
    assert msg.details["compliance_status"] == "COMPLIANT"
    assert msg.details["fatf_travel_rule_exempt"] is True


def test_execution_algorithm_agent():
    agent = ExecutionAlgorithmAgent()
    # Test small order relative to depth
    small_plan = agent.plan_execution_trajectory(
        notional_usdt=Decimal("500"),
        depth_1pct_usdt=Decimal("500000"),
        spread_bps=Decimal("2.0"),
    )
    assert small_plan["algorithm"] == "DIRECT_LIMIT"
    assert small_plan["slices"] == 1
    assert small_plan["is_high_slippage_risk"] is False

    # Test institutional size requiring TWAP slicing
    twap_plan = agent.plan_execution_trajectory(
        notional_usdt=Decimal("100000"),
        depth_1pct_usdt=Decimal("500000"),
        spread_bps=Decimal("3.0"),
    )
    assert twap_plan["algorithm"] == "TWAP"
    assert twap_plan["slices"] >= 3
    assert twap_plan["is_high_slippage_risk"] is True

    msg = agent.evaluate({
        "symbol": "BTCUSDT",
        "notional_usdt": "25000",
        "depth_1pct_usdt": "1000000",
        "spread_bps": "1.5",
    })
    assert msg.sender_id == "execution_algorithms"
    assert msg.epistemic_tag == "[QUANTITATIVE ESTIMATE]"
    assert "execution_plan" in msg.details


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

    # Standard 5-subagent deliberation
    result = orch.orchestrate("SOLUSDT")
    assert result["instrument"]["symbol"] == "SOLUSDT"
    assert len(result["deliberation_log"]) == 5
    assert result["deliberation_log"][0]["agent"] == "Data Systems & Pipeline Engineering Agent"
    assert "At" in result["standardized_bottom_line"]
    assert "Otherwise, no trade." in result["standardized_bottom_line"]

    # Deep multi-agent deliberation including execution, compliance, and registry
    deep_result = orch.orchestrate("SOLUSDT", include_deep_subagents=True)
    assert len(deep_result["deliberation_log"]) == 8
    assert "execution_plan" in deep_result

    # Test agent evaluate
    eval_msg = orch.evaluate({"symbol": "SOLUSDT"})
    assert eval_msg.sender_id == "master_orchestrator"
    assert "Otherwise, no trade." in eval_msg.summary
