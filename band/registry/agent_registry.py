"""
Band Agent Registry – tracks all registered agents and their status.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentInfo:
    name: str
    description: str
    subscribes_to: list[str]
    publishes: list[str]
    status: str = "idle"  # idle | running | error
    last_active: str | None = None
    message_count: int = 0
    error_count: int = 0
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "subscribes_to": self.subscribes_to,
            "publishes": self.publishes,
            "status": self.status,
            "last_active": self.last_active,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "capabilities": self.capabilities,
        }


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentInfo] = {}

    def register(self, info: AgentInfo) -> None:
        self._agents[info.name] = info
        logger.info("Registered agent: %s", info.name)

    def mark_active(self, name: str, status: str = "running") -> None:
        if name in self._agents:
            self._agents[name].status = status
            self._agents[name].last_active = datetime.now(timezone.utc).isoformat()
            self._agents[name].message_count += 1

    def mark_error(self, name: str) -> None:
        if name in self._agents:
            self._agents[name].status = "error"
            self._agents[name].error_count += 1

    def mark_idle(self, name: str) -> None:
        if name in self._agents:
            self._agents[name].status = "idle"

    def get_all(self) -> list[dict[str, Any]]:
        return [a.to_dict() for a in self._agents.values()]

    def get(self, name: str) -> AgentInfo | None:
        return self._agents.get(name)


agent_registry = AgentRegistry()
