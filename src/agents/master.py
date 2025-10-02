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
import asyncio

logger = logging.getLogger(__name__)

# Import sub-agents
from src.agents.research import research_agent
from src.agents.strategy import strategy_agent
from src.agents.risk import risk_agent
from src.agents.portfolio import portfolio_agent
from src.agents.monitoring import monitoring_agent
from src.agents.education import education_agent


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

    Phase 1: Basic routing implementation with mock agents
    """

    def __init__(self):
        super().__init__("master_agent")
        # Agent registry
        self.agent_registry = {
            "research_agent": research_agent,
            "strategy_agent": strategy_agent,
            "risk_agent": risk_agent,
            "portfolio_agent": portfolio_agent,
            "monitoring_agent": monitoring_agent,
            "education_agent": education_agent,
        }

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """
        Main processing logic:
        1. Analyze intent
        2. Route to sub-agents
        3. Aggregate results
        4. Check HITL trigger
        """
        try:
            # Extract query from context
            query = input_data.context.get("query", "") if input_data.context else ""
            automation_level = input_data.automation_level

            logger.info(f"Processing query: {query}")

            # Step 1: Analyze intent
            intent = self.analyze_intent(query)
            logger.info(f"Detected intent: {intent}")

            # Step 2: Determine which agents to call
            agent_ids = self.route_to_agents(intent)
            logger.info(f"Routing to agents: {agent_ids}")

            # Step 3: Call agents in parallel
            agent_results = await self._call_agents(agent_ids, input_data)

            # Step 4: Check for risk level from results
            risk_level = self._extract_risk_level(agent_results)

            # Step 5: Check HITL trigger
            hitl_required = self.should_trigger_hitl(intent, automation_level, risk_level)

            # Step 6: Aggregate results
            aggregated = await self.aggregate_results(agent_results)

            return AgentOutput(
                status="success",
                data={
                    "intent": intent,
                    "query": query,
                    "agents_called": agent_ids,
                    "results": aggregated,
                    "hitl_required": hitl_required,
                    "risk_level": risk_level,
                },
                metadata={
                    "automation_level": automation_level,
                    "agent_count": len(agent_ids),
                }
            )

        except Exception as e:
            logger.error(f"Error in master agent: {str(e)}")
            return AgentOutput(
                status="failure",
                error=str(e),
                metadata={"intent": "unknown"}
            )

    async def _call_agents(
        self,
        agent_ids: List[str],
        input_data: AgentInput
    ) -> Dict[str, AgentOutput]:
        """
        Call multiple agents in parallel

        Returns dict of agent_id -> AgentOutput
        """
        tasks = []
        for agent_id in agent_ids:
            agent = self.agent_registry.get(agent_id)
            if agent:
                tasks.append(agent.execute(input_data))
            else:
                logger.warning(f"Agent not found: {agent_id}")

        # Execute all agents in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dictionary
        agent_results = {}
        for agent_id, result in zip(agent_ids, results):
            if isinstance(result, Exception):
                logger.error(f"Agent {agent_id} failed: {str(result)}")
                agent_results[agent_id] = AgentOutput(
                    status="failure",
                    error=str(result)
                )
            else:
                agent_results[agent_id] = result

        return agent_results

    def _extract_risk_level(self, agent_results: Dict[str, AgentOutput]) -> Optional[str]:
        """Extract risk level from agent results"""
        # Check if risk_agent was called
        if "risk_agent" in agent_results:
            risk_output = agent_results["risk_agent"]
            if risk_output.status == "success" and risk_output.data:
                return risk_output.data.get("risk_level")
        return None

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

        Phase 1: Simple aggregation
        Phase 2: LLM-based intelligent summarization
        """
        aggregated = {}

        # Extract data from each agent
        for agent_id, output in agent_results.items():
            if output.status == "success" and output.data:
                # Remove 'agent' suffix for cleaner keys
                key = agent_id.replace("_agent", "")
                aggregated[key] = output.data

        # Generate a simple summary based on available data
        summary_parts = []

        if "research" in aggregated:
            research_data = aggregated["research"]
            stock_name = research_data.get("stock_name", "종목")
            rating = research_data.get("rating", "N/A")
            summary_parts.append(f"{stock_name} 분석 완료 (평가: {rating}/5)")

        if "strategy" in aggregated:
            strategy_data = aggregated["strategy"]
            action = strategy_data.get("action", "N/A")
            confidence = strategy_data.get("confidence", 0)
            summary_parts.append(f"매매 의견: {action} (신뢰도: {confidence})")

        if "risk" in aggregated:
            risk_data = aggregated["risk"]
            risk_level = risk_data.get("risk_level", "N/A")
            summary_parts.append(f"리스크 수준: {risk_level}")

        if "portfolio" in aggregated:
            portfolio_data = aggregated["portfolio"]
            rebalancing_needed = portfolio_data.get("rebalancing_needed", False)
            if rebalancing_needed:
                summary_parts.append("리밸런싱 필요")

        summary = " | ".join(summary_parts) if summary_parts else "분석 완료"

        return {
            "summary": summary,
            "details": aggregated,
            "agent_count": len(agent_results),
            "success_count": sum(1 for o in agent_results.values() if o.status == "success"),
        }


# Global instance
master_agent = MasterAgent()