"""Portfolio Agent 서브그래프

포트폴리오 분석 및 리밸런싱 제안을 위한 Langgraph 그래프

ReAct 패턴: Intent Classifier → Planner → Task Router → Specialists → Summary
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END
import logging

from .state import PortfolioState
from .nodes import (
    query_intent_classifier_node,
    planner_node,
    task_router_node,
    analyze_query_node,
    collect_portfolio_node,
    market_condition_node,
    optimize_allocation_node,
    validate_constraints_node,
    rebalance_plan_node,
    summary_node,
    approval_rebalance_node,
    execute_rebalance_node,
)

logger = logging.getLogger(__name__)


def route_to_specialist(state: PortfolioState) -> str:
    """
    Task Router에서 다음 노드 결정

    current_task.specialist에 따라 적절한 specialist로 라우팅
    pending_tasks가 비었으면 summary로 이동
    """
    current_task = state.get("current_task")

    if current_task is None:
        # 모든 작업 완료, summary로 이동
        logger.info("🔀 [Portfolio/Router] 모든 작업 완료, summary로 이동")
        return "summary"

    specialist = current_task.get("specialist", "")

    logger.info("🔀 [Portfolio/Router] 다음 specialist: %s", specialist)

    # specialist 매핑
    specialist_map = {
        "collect_portfolio": "collect_portfolio",
        "market_condition_specialist": "market_condition",
        "optimization_specialist": "optimize_allocation",
        "constraint_validator": "validate_constraints",
        "rebalance_planner": "rebalance_plan",
        "summary_generator": "summary",
    }

    return specialist_map.get(specialist, "summary")


def should_rebalance(state: PortfolioState) -> str:
    """
    Summary 이후 리밸런싱 필요 여부 체크

    view_only=True면 END, rebalancing_needed=True면 approval로 이동
    """
    view_only = state.get("view_only", True)
    rebalancing_needed = state.get("rebalancing_needed", False)

    if view_only:
        logger.info("📋 [Portfolio] 조회 전용 모드 - END")
        return "end"

    if rebalancing_needed:
        logger.info("🔄 [Portfolio] 리밸런싱 필요 - 승인 단계로")
        return "approval"

    logger.info("✅ [Portfolio] 리밸런싱 불필요 - END")
    return "end"


def build_portfolio_subgraph():
    """
    Portfolio Agent 서브그래프 생성 (ReAct 패턴)

    Flow:
    START → query_intent_classifier → planner → task_router
          ↓
    task_router ⇄ specialists (동적 선택)
          ↓
    summary → [조건부] approval_rebalance → execute_rebalance → END

    Specialists:
    - collect_portfolio: 포트폴리오 데이터 수집
    - market_condition_specialist (market_condition_node): 시장 상황 분석
    - optimization_specialist (optimize_allocation_node): 포트폴리오 최적화
    - constraint_validator (validate_constraints_node): 제약 조건 검증
    - rebalance_planner (rebalance_plan_node): 리밸런싱 계획 수립
    - summary_generator (summary_node): 요약 생성
    """
    workflow = StateGraph(PortfolioState)

    # ReAct 패턴 노드 추가
    workflow.add_node("query_intent_classifier", query_intent_classifier_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("task_router", task_router_node)

    # Specialist 노드 추가
    workflow.add_node("analyze_query", analyze_query_node)  # 레거시 호환
    workflow.add_node("collect_portfolio", collect_portfolio_node)
    workflow.add_node("market_condition", market_condition_node)
    workflow.add_node("optimize_allocation", optimize_allocation_node)
    workflow.add_node("validate_constraints", validate_constraints_node)
    workflow.add_node("rebalance_plan", rebalance_plan_node)
    workflow.add_node("summary", summary_node)

    # HITL 노드
    workflow.add_node("approval_rebalance", approval_rebalance_node)
    workflow.add_node("execute_rebalance", execute_rebalance_node)

    # ReAct Flow 엣지 정의
    workflow.set_entry_point("query_intent_classifier")
    workflow.add_edge("query_intent_classifier", "planner")
    workflow.add_edge("planner", "analyze_query")  # 레거시 query 분석
    workflow.add_edge("analyze_query", "task_router")

    # Task Router → Specialist (조건부 라우팅)
    workflow.add_conditional_edges(
        "task_router",
        route_to_specialist,
        {
            "collect_portfolio": "collect_portfolio",
            "market_condition": "market_condition",
            "optimize_allocation": "optimize_allocation",
            "validate_constraints": "validate_constraints",
            "rebalance_plan": "rebalance_plan",
            "summary": "summary",
        },
    )

    # Specialist → Task Router (다음 작업 선택)
    workflow.add_edge("collect_portfolio", "task_router")
    workflow.add_edge("market_condition", "task_router")
    workflow.add_edge("optimize_allocation", "task_router")
    workflow.add_edge("validate_constraints", "task_router")
    workflow.add_edge("rebalance_plan", "task_router")

    # Summary 이후 조건부 분기
    workflow.add_conditional_edges(
        "summary",
        should_rebalance,
        {
            "end": END,  # 조회만 또는 리밸런싱 불필요
            "approval": "approval_rebalance",  # 리밸런싱 필요
        }
    )

    # 리밸런싱 HITL 플로우
    workflow.add_edge("approval_rebalance", "execute_rebalance")
    workflow.add_edge("execute_rebalance", END)

    logger.info("✅ [Portfolio] ReAct 패턴 서브그래프 빌드 완료")

    return workflow
