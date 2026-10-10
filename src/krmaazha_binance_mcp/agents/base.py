"""Base agent abstractions for the Krmaazha Multi-Agent Architecture."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class AgentMetadata:
    """Metadata describing an agent's identity, role, and capabilities."""
    agent_id: str
    name: str
    icon: str
    role_description: str
    governing_skill: str
    responsibilities: tuple[str, ...]
    hard_boundaries: tuple[str, ...]
    tools_used: tuple[str, ...]


@dataclass
class AgentMessage:
    """A structured message emitted by an agent during deliberation."""
    sender_id: str
    sender_name: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    epistemic_tag: str = "[VERIFIED FACT]"  # [VERIFIED FACT], [QUANTITATIVE ESTIMATE], [ANALYST INTERPRETATION]
    summary: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base class for all specialized agents in the system."""

    def __init__(self, metadata: AgentMetadata) -> None:
        self.metadata = metadata

    @abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> AgentMessage:
        """Evaluate the provided context and produce an authoritative agent message."""
        pass
