"""
Base Agent class - All agents inherit from this
"""
from abc import ABC, abstractmethod
from typing import Any, Dict
from src.schemas.agent import AgentInput, AgentOutput
import time
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all agents in the system

    All agents must implement:
    - process(): Main processing logic
    - _get_mock_response(): Mock response for testing
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.is_mock = True  # Phase 1: All agents start as mock

    @abstractmethod
    async def process(self, input_data: AgentInput) -> AgentOutput:
        """
        Process the input and return output

        This is where the actual agent logic goes.
        In Phase 1, this will call _get_mock_response()
        """
        pass

    @abstractmethod
    def _get_mock_response(self, input_data: AgentInput) -> AgentOutput:
        """
        Generate mock response for testing

        This should return realistic mock data that matches
        the expected output format
        """
        pass

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        """
        Execute the agent with logging and error handling
        """
        start_time = time.time()

        try:
            logger.info(f"🤖 [{self.agent_id}] 실행 시작")
            logger.debug(f"📥 [{self.agent_id}] 입력: {input_data}")

            output = await self.process(input_data)

            execution_time = int((time.time() - start_time) * 1000)
            logger.info(f"✅ [{self.agent_id}] 완료 ({execution_time}ms)")

            # Add metadata
            if output.metadata is None:
                output.metadata = {}
            output.metadata["agent_id"] = self.agent_id
            output.metadata["execution_time_ms"] = execution_time
            output.metadata["is_mock"] = self.is_mock

            return output

        except Exception as e:
            logger.error(f"[{self.agent_id}] Error: {str(e)}")
            execution_time = int((time.time() - start_time) * 1000)

            return AgentOutput(
                status="failure",
                error=str(e),
                metadata={
                    "agent_id": self.agent_id,
                    "execution_time_ms": execution_time,
                    "is_mock": self.is_mock
                }
            )

    def log_execution(self, input_data: Dict[str, Any], output_data: Dict[str, Any], status: str):
        """
        Log agent execution to database
        TODO: Implement database logging
        """
        pass