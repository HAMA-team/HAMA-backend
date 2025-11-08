"""
Risk Agent 서브그래프

ReAct 패턴: Intent Classifier → Planner → Task Router → Specialists → Final Assessment
"""
from langgraph.graph import StateGraph, END
import logging

from src.agents.risk.state import RiskState
from src.agents.risk.nodes import (
    query_intent_classifier_node,
    planner_node,
    task_router_node,
    collect_portfolio_data_node,
    concentration_check_node,
    market_risk_node,
    final_assessment_node,
)

logger = logging.getLogger(__name__)


def route_to_specialist(state: RiskState) -> str:
    """
    Task Router에서 다음 노드 결정

    current_task.specialist에 따라 적절한 specialist로 라우팅
    pending_tasks가 비었으면 final_assessment로 이동
    """
    current_task = state.get("current_task")

    if current_task is None:
        # 모든 작업 완료, final_assessment로 이동
        logger.info("🔀 [Risk/Router] 모든 작업 완료, final_assessment로 이동")
        return "final_assessment"

    specialist = current_task.get("specialist", "")

    logger.info("🔀 [Risk/Router] 다음 specialist: %s", specialist)

    # specialist 매핑
    specialist_map = {
        "collect_data": "collect_data",
        "concentration_specialist": "concentration_check",
        "market_risk_specialist": "market_risk",
        "final_assessment": "final_assessment",
    }

    return specialist_map.get(specialist, "final_assessment")


def build_risk_subgraph():
    """
    Risk Agent 서브그래프 빌드 (ReAct 패턴)

    Flow:
    START → query_intent_classifier → planner → task_router
          ↓
    task_router ⇄ specialists (동적 선택)
          ↓
    final_assessment → END

    Specialists:
    - collect_data: 포트폴리오 데이터 수집
    - concentration_specialist (concentration_check_node): 집중도 리스크 분석
    - market_risk_specialist (market_risk_node): 시장 리스크 분석

    Returns:
        CompiledStateGraph
    """
    workflow = StateGraph(RiskState)

    # ReAct 패턴 노드 추가
    workflow.add_node("query_intent_classifier", query_intent_classifier_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("task_router", task_router_node)

    # Specialist 노드 추가
    workflow.add_node("collect_data", collect_portfolio_data_node)
    workflow.add_node("concentration_check", concentration_check_node)
    workflow.add_node("market_risk", market_risk_node)
    workflow.add_node("final_assessment", final_assessment_node)

    # ReAct Flow 엣지 정의
    workflow.set_entry_point("query_intent_classifier")
    workflow.add_edge("query_intent_classifier", "planner")
    workflow.add_edge("planner", "task_router")

    # Task Router → Specialist (조건부 라우팅)
    workflow.add_conditional_edges(
        "task_router",
        route_to_specialist,
        {
            "collect_data": "collect_data",
            "concentration_check": "concentration_check",
            "market_risk": "market_risk",
            "final_assessment": "final_assessment",
        },
    )

    # Specialist → Task Router (다음 작업 선택)
    workflow.add_edge("collect_data", "task_router")
    workflow.add_edge("concentration_check", "task_router")
    workflow.add_edge("market_risk", "task_router")

    # Final Assessment → END
    workflow.add_edge("final_assessment", END)

    logger.info("✅ [Risk] ReAct 패턴 서브그래프 빌드 완료")

    return workflow.compile(name="risk_agent")


# 서브그래프 인스턴스 export
risk_subgraph = build_risk_subgraph()
