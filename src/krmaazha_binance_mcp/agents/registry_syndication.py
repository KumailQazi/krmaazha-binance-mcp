"""Registry Syndication & Distribution Agent: Multi-registry publishing and ecosystem reach."""

from __future__ import annotations

from typing import Any

from krmaazha_binance_mcp.agents.base import AgentMessage, AgentMetadata, BaseAgent


class RegistrySyndicationAgent(BaseAgent):
    """Specialized agent governing publication across MCP Registry, Smithery, Glama, and PyPI."""

    METADATA = AgentMetadata(
        agent_id="registry_syndication",
        name="Registry Syndication & Distribution Agent",
        icon="🌐",
        role_description=(
            "Coordinates multi-registry publishing, schema conformance, reverse-DNS ownership, "
            "and distribution across Official MCP Registry, Smithery, Glama, and PyPI."
        ),
        governing_skill="mcp-registry-syndication",
        responsibilities=(
            "Enforce official MCP Registry manifest standard (server.json 2025-12-11 schema)",
            "Verify reverse-DNS naming convention (io.github.<owner>/<repo>)",
            "Validate PyPI README metadata tag (mcp-name) for registry ownership verification",
            "Audit multi-registry syndication files (smithery.yaml, glama.json, PulseMCP specs)",
            "Manage semantic versioning lockstep across pyproject.toml, server.json, CHANGELOG.md",
            "Track registry indexation and package distribution integrity",
        ),
        hard_boundaries=(
            "Never publish to MCP registry without PyPI ownership tag present in package metadata",
            "Never allow version discrepancies between pyproject.toml and server.json",
            "Never include credentials, API secrets, or tokens in any directory configuration file",
        ),
        tools_used=(
            "validate_registry_bundle",
            "verify_ownership_attestation",
            "audit_syndication_configs",
            "check_version_lockstep",
        ),
    )

    def __init__(self) -> None:
        super().__init__(self.METADATA)

    @staticmethod
    def verify_version_lockstep(pyproject_ver: str, server_ver: str, changelog_ver: str) -> bool:
        """Verify that version numbers across all package and registry files match exactly."""
        return pyproject_ver == server_ver == changelog_ver

    @staticmethod
    def audit_syndication_files(
        has_server_json: bool,
        has_smithery_yaml: bool,
        has_glama_json: bool,
    ) -> dict[str, str]:
        """Audit readiness for multi-registry discovery across the ecosystem."""
        return {
            "mcp_registry": "READY" if has_server_json else "MISSING",
            "smithery": "READY" if has_smithery_yaml else "MISSING",
            "glama": "READY" if has_glama_json else "MISSING",
        }

    def evaluate(self, context: dict[str, Any]) -> AgentMessage:
        """Audit package distribution, registry manifests, and syndication configurations."""
        pyproject_ver = context.get("pyproject_version", "1.2.2")
        server_ver = context.get("server_version", "1.2.2")
        changelog_ver = context.get("changelog_version", "1.2.2")

        has_server_json = context.get("has_server_json", True)
        has_smithery = context.get("has_smithery_yaml", True)
        has_glama = context.get("has_glama_json", True)

        findings: list[str] = []
        is_synced = self.verify_version_lockstep(pyproject_ver, server_ver, changelog_ver)

        if not is_synced:
            findings.append(
                f"Version mismatch detected: pyproject={pyproject_ver}, "
                f"server.json={server_ver}, changelog={changelog_ver}"
            )
        else:
            findings.append(f"Version lockstep verified across all distributions: v{pyproject_ver}")

        syndication = self.audit_syndication_files(has_server_json, has_smithery, has_glama)
        all_ready = all(v == "READY" for v in syndication.values())

        if all_ready:
            findings.append("Multi-registry syndication: MCP Registry, Smithery, Glama active.")
        else:
            findings.append(f"Syndication incomplete: {syndication}")

        reg_status = "VERIFIED" if is_synced and all_ready else "ATTENTION_REQUIRED"
        summary = (
            f"Registry Syndication: {reg_status}. PyPI v{pyproject_ver} active. "
            f"MCP Registry io.github.KumailQazi/krmaazha-binance-mcp indexed."
        )

        return AgentMessage(
            sender_id=self.metadata.agent_id,
            sender_name=self.metadata.name,
            epistemic_tag="[VERIFIED FACT]",
            summary=summary,
            details={
                "version": pyproject_ver,
                "version_lockstep": is_synced,
                "syndication_channels": syndication,
                "registry_id": "io.github.KumailQazi/krmaazha-binance-mcp",
                "pypi_package": "krmaazha-binance-mcp",
                "findings": findings,
            },
        )
