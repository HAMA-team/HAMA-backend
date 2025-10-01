"""
Master Agent - Router and Orchestrator

Responsibilities:
1. Analyze user intent
2. Route to appropriate sub-agents
3. Aggregate results
4. Trigger HITL when needed
"""
from typing import List, Dict, Any, Optional
from src.agents.base import BaseAgent
from src.schemas.agent import AgentInput, AgentOutput
import logging

logger = logging.getLogger(__name__)


class IntentCategory:
    """Intent categories for user queries"""
    STOCK_ANALYSIS = "stock_analysis"
    TRADE_EXECUTION = "trade_execution"
    PORTFOLIO_EVALUATION = "portfolio_evaluation"
    REBALANCING = "rebalancing"
    PERFORMANCE_CHECK = "performance_check"
    MARKET_STATUS = "market_status"
    GENERAL_QUESTION = "general_question"


class MasterAgent(BaseAgent):
    """
    Master Agent - Orchestrates all other agents

    Phase 1: Mock implementation with basic routing logic
    """

    def __init__(self):
        super().__init__("master_agent")

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """
        Main processing logic:
        1. Analyze intent
        2. Route to sub-agents
        3. Aggregate results
        4. Check HITL trigger
        """
        # TODO: Implement actual intent analysis using LLM
        # TODO: Implement actual sub-agent routing
        # TODO: Implement actual result aggregation

        # Phase 1: Return mock response
        return self._get_mock_response(input_data)

    def _get_mock_response(self, input_data: AgentInput) -> AgentOutput:
        """Generate mock response"""
        return AgentOutput(
            status="success",
            data={
                "intent": "stock_analysis",
                "response": "Mock response from Master Agent",
                "agents_called": ["research_agent", "strategy_agent"],
                "hitl_triggered": False,
            },
            metadata={
                "mock": True,
                "note": "Master Agent mock implementation - Phase 1"
            }
        )

    def analyze_intent(self, query: str) -> str:
        """
        Analyze user query and determine intent

        TODO: Implement with LLM
        For now, use simple keyword matching
        """
        query_lower = query.lower()

        if any(word in query_lower for word in ["분석", "어때", "평가"]):
            return IntentCategory.STOCK_ANALYSIS
        elif any(word in query_lower for word in ["매수", "매도", "사", "팔"]):
            return IntentCategory.TRADE_EXECUTION
        elif any(word in query_lower for word in ["포트폴리오", "자산배분"]):
            return IntentCategory.PORTFOLIO_EVALUATION
        elif "리밸런싱" in query_lower:
            return IntentCategory.REBALANCING
        elif any(word in query_lower for word in ["수익률", "현황", "상태"]):
            return IntentCategory.PERFORMANCE_CHECK
        elif "시장" in query_lower:
            return IntentCategory.MARKET_STATUS
        else:
            return IntentCategory.GENERAL_QUESTION

    def route_to_agents(self, intent: str) -> List[str]:
        """
        Determine which agents to call based on intent

        Returns list of agent IDs to call
        """
        routing_map = {
            IntentCategory.STOCK_ANALYSIS: ["research_agent", "strategy_agent", "risk_agent"],
            IntentCategory.TRADE_EXECUTION: ["strategy_agent", "risk_agent"],
            IntentCategory.PORTFOLIO_EVALUATION: ["portfolio_agent", "risk_agent"],
            IntentCategory.REBALANCING: ["portfolio_agent", "strategy_agent"],
            IntentCategory.PERFORMANCE_CHECK: ["portfolio_agent"],
            IntentCategory.MARKET_STATUS: ["research_agent", "monitoring_agent"],
            IntentCategory.GENERAL_QUESTION: ["education_agent"],
        }

        return routing_map.get(intent, ["education_agent"])

    def should_trigger_hitl(
        self,
        intent: str,
        automation_level: int,
        risk_level: Optional[str] = None
    ) -> bool:
        """
        Determine if HITL approval is needed

        Rules:
        - Level 1 (Pilot): Only major decisions
        - Level 2 (Copilot): All trade executions and rebalancing
        - Level 3 (Advisor): All actions require approval
        """
        # Trade execution always requires approval in Level 2+
        if intent == IntentCategory.TRADE_EXECUTION and automation_level >= 2:
            return True

        # Rebalancing requires approval in Level 2+
        if intent == IntentCategory.REBALANCING and automation_level >= 2:
            return True

        # High risk always triggers HITL
        if risk_level in ["high", "critical"]:
            return True

        # Level 3 (Advisor) requires approval for most actions
        if automation_level == 3 and intent not in [
            IntentCategory.GENERAL_QUESTION,
            IntentCategory.PERFORMANCE_CHECK
        ]:
            return True

        return False

    async def aggregate_results(self, agent_results: Dict[str, AgentOutput]) -> Dict[str, Any]:
        """
        Aggregate results from multiple agents into cohesive response

        TODO: Implement actual aggregation logic with LLM
        """
        return {
            "summary": "Aggregated results from multiple agents",
            "details": agent_results,
        }


# Global instance
master_agent = MasterAgent()