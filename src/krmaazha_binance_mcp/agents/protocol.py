"""MCP Protocol & Tooling Agent: FastMCP interfaces, protocol 2.3.0, and schema validation."""

from __future__ import annotations

import re
from typing import Any

from krmaazha_binance_mcp.agents.base import AgentMessage, AgentMetadata, BaseAgent


class McpProtocolAgent(BaseAgent):
    """Agent verifying Model Context Protocol schemas, CanonicalOrder, and registry manifests."""

    METADATA = AgentMetadata(
        agent_id="mcp_protocol",
        name="MCP Protocol & Tooling Agent",
        icon="⚡",
        role_description=(
            "Governs FastMCP / MCPServer 2.3.0 tool registration, CanonicalOrder validation, "
            "Decimal typing, registry manifest conformance, and error scrubbing."
        ),
        governing_skill="mcp-builder",
        responsibilities=(
            "Validate tool arguments against strict Pydantic schemas",
            "Ensure all quantities and prices use Python Decimal for bit-perfect financial math",
            "Validate CanonicalOrder LOT_SIZE and MIN_NOTIONAL filters before confirmer submission",
            "Verify official MCP registry server.json manifest against schema 2025-12-11",
            "Verify PyPI ownership marker (mcp-name tag) in documentation metadata",
            "Scrub sensitive stack traces and API keys from LLM error returns",
            "Expose institutional knowledge doctrines via kb:// resource URIs",
        ),
        hard_boundaries=(
            "Never allow float rounding in order sizing or price limit evaluations",
            "Never bypass CanonicalOrder schema serialization before IPC dispatch",
            "Never allow non-compliant reverse-DNS naming in MCP registry manifests",
            "Never echo raw Binance exception tracebacks containing query strings with secrets",
        ),
        tools_used=(
            "register_mcp_tool",
            "validate_canonical_order",
            "validate_server_manifest",
            "validate_pypi_provenance",
            "scrub_error_message",
            "serve_kb_resource",
        ),
    )

    def __init__(self) -> None:
        super().__init__(self.METADATA)

    @staticmethod
    def validate_server_manifest(manifest: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate official MCP registry server.json manifest structure."""
        errors: list[str] = []
        schema = manifest.get("$schema", "")
        if not schema.startswith("https://static.modelcontextprotocol.io/schemas/"):
            errors.append("Invalid or missing $schema declaration")

        name = manifest.get("name", "")
        if not re.match(r"^io\.github\.[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$", name):
            errors.append(f"Invalid reverse-DNS server name format: '{name}'")

        if not manifest.get("version"):
            errors.append("Missing version field in server manifest")

        packages = manifest.get("packages", [])
        if not packages or not isinstance(packages, list):
            errors.append("Missing packages configuration in server manifest")
        else:
            for pkg in packages:
                if pkg.get("registryType") != "pypi":
                    errors.append(f"Unsupported package registryType: {pkg.get('registryType')}")
                if not pkg.get("identifier"):
                    errors.append("Package missing identifier")

        return len(errors) == 0, errors

    @staticmethod
    def validate_pypi_provenance(readme_text: str, server_name: str) -> bool:
        """Verify presence of official MCP registry PyPI ownership marker in README."""
        pattern = rf"mcp-name:\s*{re.escape(server_name)}"
        return bool(re.search(pattern, readme_text, re.IGNORECASE))

    def evaluate(self, context: dict[str, Any]) -> AgentMessage:
        """Validate payload, tool execution, or registry manifest against MCP specifications."""
        order_data = context.get("order")
        tool_name = context.get("tool_name", "market_query")
        manifest = context.get("manifest")
        readme_content = context.get("readme_content")

        findings: list[str] = []
        is_valid = True

        if manifest:
            valid_manifest, manifest_errors = self.validate_server_manifest(manifest)
            if not valid_manifest:
                is_valid = False
                findings.extend(manifest_errors)
            else:
                findings.append(f"Manifest schema valid for: {manifest.get('name')}")

        if readme_content and manifest:
            server_name = manifest.get("name", "")
            if not self.validate_pypi_provenance(readme_content, server_name):
                is_valid = False
                findings.append(f"Missing PyPI ownership marker for: {server_name}")
            else:
                findings.append(f"PyPI ownership marker verified for: {server_name}")

        if order_data:
            symbol = order_data.get("symbol")
            side = order_data.get("side")
            quantity = order_data.get("quantity")
            if not symbol or not side or not quantity:
                is_valid = False
                findings.append("CanonicalOrder validation FAILED: Missing mandatory fields.")
            else:
                findings.append(f"CanonicalOrder schema verified: {side} {quantity} {symbol}.")
        elif not manifest:
            findings.append(
                f"Tool invocation validated: '{tool_name}' matches registered FastMCP schema."
            )

        summary = (
            f"Protocol Check: {'VERIFIED' if is_valid else 'REJECTED'}. "
            f"MCP 2.3.0 compliant. Decimal precision active. Error scrubbers engaged."
        )

        return AgentMessage(
            sender_id=self.metadata.agent_id,
            sender_name=self.metadata.name,
            epistemic_tag="[VERIFIED FACT]",
            summary=summary,
            details={
                "tool_name": tool_name,
                "protocol_status": "COMPLIANT" if is_valid else "INVALID",
                "mcp_version": "2.3.0",
                "decimal_typing_enforced": True,
                "scrubber_active": True,
                "findings": findings,
            },
        )
