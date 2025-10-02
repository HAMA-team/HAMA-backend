"""
LangGraph 기반 마스터 에이전트

StateGraph를 사용한 에이전트 오케스트레이션
"""
from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
import operator
import logging

from src.agents.research import research_agent
from src.agents.strategy import strategy_agent
from src.agents.risk import risk_agent
from src.agents.portfolio import portfolio_agent
from src.agents.monitoring import monitoring_agent
from src.agents.education import education_agent
from src.schemas.agent import AgentInput, AgentOutput

logger = logging.getLogger(__name__)


# ==================== State Definition ====================

class AgentState(TypedDict):
    """
    LangGraph State for HAMA

    Reducer 함수를 사용하여 상태를 누적합니다.
    """
    # 기본 정보
    query: str
    request_id: str
    automation_level: int

    # 의도 분석
    intent: Optional[str]

    # 에이전트 결과 (누적)
    agent_results: Annotated[Dict[str, Any], operator.or_]

    # 라우팅 정보
    agents_to_call: List[str]
    agents_called: Annotated[List[str], operator.add]

    # 리스크 및 HITL
    risk_level: Optional[str]
    hitl_required: bool

    # 최종 결과
    summary: Optional[str]
    final_response: Optional[Dict[str, Any]]


# ==================== Intent Categories ====================

class IntentCategory:
    """Intent categories"""
    STOCK_ANALYSIS = "stock_analysis"
    TRADE_EXECUTION = "trade_execution"
    PORTFOLIO_EVALUATION = "portfolio_evaluation"
    REBALANCING = "rebalancing"
    PERFORMANCE_CHECK = "performance_check"
    MARKET_STATUS = "market_status"
    GENERAL_QUESTION = "general_question"


# ==================== Node Functions ====================

def analyze_intent_node(state: AgentState) -> AgentState:
    """
    의도 분석 노드
    사용자 쿼리를 분석하여 의도를 파악
    """
    query = state["query"].lower()

    # 키워드 기반 의도 분석
    if any(word in query for word in ["분석", "어때", "평가"]):
        intent = IntentCategory.STOCK_ANALYSIS
    elif any(word in query for word in ["매수", "매도", "사", "팔"]):
        intent = IntentCategory.TRADE_EXECUTION
    elif any(word in query for word in ["포트폴리오", "자산배분"]):
        intent = IntentCategory.PORTFOLIO_EVALUATION
    elif "리밸런싱" in query:
        intent = IntentCategory.REBALANCING
    elif any(word in query for word in ["수익률", "현황", "상태"]):
        intent = IntentCategory.PERFORMANCE_CHECK
    elif "시장" in query:
        intent = IntentCategory.MARKET_STATUS
    else:
        intent = IntentCategory.GENERAL_QUESTION

    logger.info(f"Detected intent: {intent}")

    return {
        **state,
        "intent": intent,
    }


def determine_agents_node(state: AgentState) -> AgentState:
    """
    에이전트 결정 노드
    의도에 따라 호출할 에이전트 결정
    """
    intent = state["intent"]

    routing_map = {
        IntentCategory.STOCK_ANALYSIS: ["research_agent", "strategy_agent", "risk_agent"],
        IntentCategory.TRADE_EXECUTION: ["strategy_agent", "risk_agent"],
        IntentCategory.PORTFOLIO_EVALUATION: ["portfolio_agent", "risk_agent"],
        IntentCategory.REBALANCING: ["portfolio_agent", "strategy_agent"],
        IntentCategory.PERFORMANCE_CHECK: ["portfolio_agent"],
        IntentCategory.MARKET_STATUS: ["research_agent", "monitoring_agent"],
        IntentCategory.GENERAL_QUESTION: ["education_agent"],
    }

    agents = routing_map.get(intent, ["education_agent"])
    logger.info(f"Agents to call: {agents}")

    return {
        **state,
        "agents_to_call": agents,
    }


async def call_agents_node(state: AgentState) -> AgentState:
    """
    에이전트 호출 노드
    결정된 에이전트들을 병렬로 호출
    """
    agents_to_call = state["agents_to_call"]

    agent_registry = {
        "research_agent": research_agent,
        "strategy_agent": strategy_agent,
        "risk_agent": risk_agent,
        "portfolio_agent": portfolio_agent,
        "monitoring_agent": monitoring_agent,
        "education_agent": education_agent,
    }

    # AgentInput 생성
    agent_input = AgentInput(
        request_id=state["request_id"],
        automation_level=state["automation_level"],
        context={
            "query": state["query"],
            "intent": state["intent"],
        }
    )

    # 에이전트 호출
    results = {}
    for agent_id in agents_to_call:
        agent = agent_registry.get(agent_id)
        if agent:
            try:
                output = await agent.execute(agent_input)
                if output.status == "success":
                    results[agent_id] = output.data
            except Exception as e:
                logger.error(f"Agent {agent_id} failed: {str(e)}")

    logger.info(f"Called agents: {list(results.keys())}")

    return {
        **state,
        "agent_results": results,
        "agents_called": list(results.keys()),
    }


def check_risk_node(state: AgentState) -> AgentState:
    """
    리스크 체크 노드
    에이전트 결과에서 리스크 수준 추출
    """
    agent_results = state.get("agent_results", {})

    # risk_agent 결과에서 리스크 레벨 추출
    risk_level = None
    if "risk_agent" in agent_results:
        risk_data = agent_results["risk_agent"]
        risk_level = risk_data.get("risk_level")

    logger.info(f"Risk level: {risk_level}")

    return {
        **state,
        "risk_level": risk_level,
    }


def check_hitl_node(state: AgentState) -> AgentState:
    """
    HITL 트리거 체크 노드
    자동화 레벨과 리스크를 고려하여 HITL 필요 여부 판단
    """
    intent = state["intent"]
    automation_level = state["automation_level"]
    risk_level = state.get("risk_level")

    hitl_required = False

    # Trade execution always requires approval in Level 2+
    if intent == IntentCategory.TRADE_EXECUTION and automation_level >= 2:
        hitl_required = True

    # Rebalancing requires approval in Level 2+
    if intent == IntentCategory.REBALANCING and automation_level >= 2:
        hitl_required = True

    # High risk always triggers HITL
    if risk_level in ["high", "critical"]:
        hitl_required = True

    # Level 3 (Advisor) requires approval for most actions
    if automation_level == 3 and intent not in [
        IntentCategory.GENERAL_QUESTION,
        IntentCategory.PERFORMANCE_CHECK
    ]:
        hitl_required = True

    logger.info(f"HITL required: {hitl_required}")

    return {
        **state,
        "hitl_required": hitl_required,
    }


def aggregate_results_node(state: AgentState) -> AgentState:
    """
    결과 통합 노드
    모든 에이전트 결과를 통합하여 최종 응답 생성
    """
    agent_results = state.get("agent_results", {})

    # 요약 생성
    summary_parts = []

    if "research_agent" in agent_results:
        research = agent_results["research_agent"]
        stock_name = research.get("stock_name", "종목")
        rating = research.get("rating", "N/A")
        summary_parts.append(f"{stock_name} 분석 완료 (평가: {rating}/5)")

    if "strategy_agent" in agent_results:
        strategy = agent_results["strategy_agent"]
        action = strategy.get("action", "N/A")
        confidence = strategy.get("confidence", 0)
        summary_parts.append(f"매매 의견: {action} (신뢰도: {confidence})")

    if "risk_agent" in agent_results:
        risk = agent_results["risk_agent"]
        risk_level = risk.get("risk_level", "N/A")
        summary_parts.append(f"리스크 수준: {risk_level}")

    summary = " | ".join(summary_parts) if summary_parts else "분석 완료"

    # 최종 응답 구성
    final_response = {
        "summary": summary,
        "details": agent_results,
        "intent": state["intent"],
        "agents_called": state.get("agents_called", []),
        "hitl_required": state.get("hitl_required", False),
        "risk_level": state.get("risk_level"),
    }

    return {
        **state,
        "summary": summary,
        "final_response": final_response,
    }


# ==================== Router Functions ====================

def should_continue(state: AgentState) -> str:
    """
    다음 노드 결정
    """
    # 모든 처리가 완료되면 END
    return END


# ==================== Build Graph ====================

def build_graph() -> StateGraph:
    """
    LangGraph StateGraph 구성
    """
    # 그래프 생성
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("analyze_intent", analyze_intent_node)
    workflow.add_node("determine_agents", determine_agents_node)
    workflow.add_node("call_agents", call_agents_node)
    workflow.add_node("check_risk", check_risk_node)
    workflow.add_node("check_hitl", check_hitl_node)
    workflow.add_node("aggregate_results", aggregate_results_node)

    # 엣지 추가 (플로우 정의)
    workflow.set_entry_point("analyze_intent")
    workflow.add_edge("analyze_intent", "determine_agents")
    workflow.add_edge("determine_agents", "call_agents")
    workflow.add_edge("call_agents", "check_risk")
    workflow.add_edge("check_risk", "check_hitl")
    workflow.add_edge("check_hitl", "aggregate_results")
    workflow.add_edge("aggregate_results", END)

    # 그래프 컴파일
    app = workflow.compile()

    return app


# Global compiled graph
graph_app = build_graph()


# ==================== Main Interface ====================

async def run_graph(query: str, automation_level: int = 2, request_id: str = None) -> Dict[str, Any]:
    """
    그래프 실행 함수

    Args:
        query: 사용자 질의
        automation_level: 자동화 레벨 (1-3)
        request_id: 요청 ID

    Returns:
        최종 응답 딕셔너리
    """
    import uuid

    if not request_id:
        request_id = str(uuid.uuid4())

    # 초기 상태
    initial_state = {
        "query": query,
        "request_id": request_id,
        "automation_level": automation_level,
        "intent": None,
        "agent_results": {},
        "agents_to_call": [],
        "agents_called": [],
        "risk_level": None,
        "hitl_required": False,
        "summary": None,
        "final_response": None,
    }

    # 그래프 실행
    result = await graph_app.ainvoke(initial_state)

    return result.get("final_response", {})