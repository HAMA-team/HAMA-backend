"""Legacy agent base class retained for non-Langgraph agents.

This module exists to isolate the old BaseAgent pattern from the new
Langgraph-first architecture. All remaining subclasses should migrate to
Langgraph StateGraphs and drop LegacyAgent usage over time.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict
import time
import logging

from src.schemas.agent import AgentInput, AgentOutput

logger = logging.getLogger(__name__)


class LegacyAgent(ABC):
    """Legacy async agent abstraction.

    New work should prefer Langgraph StateGraph agents. This class remains only
    to support modules that have not yet been migrated.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.is_mock = True

    @abstractmethod
    async def process(self, input_data: AgentInput) -> AgentOutput:
        """Legacy entry point for agent logic."""
        raise NotImplementedError

    @abstractmethod
    def _get_mock_response(self, input_data: AgentInput) -> AgentOutput:
        """Return mock data for early stage implementations."""
        raise NotImplementedError

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """Execute the agent with basic logging and error handling."""
        start_time = time.time()

        try:
            logger.info(f"🤖 [{self.agent_id}] 실행 시작")
            logger.debug(f"📥 [{self.agent_id}] 입력: {input_data}")

            output = await self.process(input_data)

            execution_time = int((time.time() - start_time) * 1000)
            logger.info(f"✅ [{self.agent_id}] 완료 ({execution_time}ms)")

            if output.metadata is None:
                output.metadata = {}
            output.metadata["agent_id"] = self.agent_id
            output.metadata["execution_time_ms"] = execution_time
            output.metadata["is_mock"] = self.is_mock

            return output

        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.error(f"[{self.agent_id}] Error: {exc}")
            execution_time = int((time.time() - start_time) * 1000)

            return AgentOutput(
                status="failure",
                error=str(exc),
                metadata={
                    "agent_id": self.agent_id,
                    "execution_time_ms": execution_time,
                    "is_mock": self.is_mock,
                },
            )

    def log_execution(self, input_data: Dict[str, Any], output_data: Dict[str, Any], status: str) -> None:
        """Placeholder for legacy DB logging (kept for compatibility)."""
        del input_data, output_data, status  # noop placeholder


__all__ = ["LegacyAgent"]
