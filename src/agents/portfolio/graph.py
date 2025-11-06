"""Portfolio Agent 서브그래프

포트폴리오 분석 및 리밸런싱 제안을 위한 Langgraph 그래프"""
from __future__ import annotations

from langgraph.graph import StateGraph, END
import logging

from .state import PortfolioState
from .nodes import (
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


def should_rebalance(state: PortfolioState) -> str:
    """
    조회 전용 모드 체크

    view_only=True면 리밸런싱 노드 건너뛰고 바로 END
    """
    if state.get("view_only"):
        logger.info("📋 [Portfolio] 조회 전용 모드 - 리밸런싱 스킵")
        return "end"

    logger.info("🔄 [Portfolio] 리밸런싱 모드 진입")
    return "rebalance"


def build_portfolio_subgraph():
    """
    Portfolio Agent 서브그래프 생성

    Flow:
    analyze_query → collect_portfolio → market_condition → summary

    조건부 분기:
    - view_only=True: summary → END (조회만)
    - view_only=False: summary → optimize_allocation → rebalance_plan
                      → approval_rebalance → execute_rebalance → END

    새로운 기능:
    - analyze_query: query에서 특정 종목 조회 여부 판단 (ReAct 패턴)
    - view_only: 조회 전용 모드
    - market_condition: 시장 상황 분석
    - validate_constraints: 포트폴리오 제약 조건 검증
    - approval_rebalance: HITL 승인 노드
    - execute_rebalance: 승인된 리밸런싱 실행
    """
    workflow = StateGraph(PortfolioState)

    # 노드 추가
    workflow.add_node("analyze_query", analyze_query_node)
    workflow.add_node("collect_portfolio", collect_portfolio_node)
    workflow.add_node("market_condition", market_condition_node)
    workflow.add_node("summary", summary_node)
    workflow.add_node("optimize_allocation", optimize_allocation_node)
    workflow.add_node("validate_constraints", validate_constraints_node)
    workflow.add_node("rebalance_plan", rebalance_plan_node)
    workflow.add_node("approval_rebalance", approval_rebalance_node)
    workflow.add_node("execute_rebalance", execute_rebalance_node)

    # 플로우 정의
    workflow.set_entry_point("analyze_query")
    workflow.add_edge("analyze_query", "collect_portfolio")
    workflow.add_edge("collect_portfolio", "market_condition")
    workflow.add_edge("market_condition", "summary")

    # 조건부 라우팅: 조회만 vs 리밸런싱
    workflow.add_conditional_edges(
        "summary",
        should_rebalance,
        {
            "end": END,  # 조회 전용
            "rebalance": "optimize_allocation",  # 리밸런싱 진행
        }
    )

    # 리밸런싱 플로우
    workflow.add_edge("optimize_allocation", "validate_constraints")
    workflow.add_edge("validate_constraints", "rebalance_plan")
    workflow.add_edge("rebalance_plan", "approval_rebalance")
    workflow.add_edge("approval_rebalance", "execute_rebalance")
    workflow.add_edge("execute_rebalance", END)

    logger.info("✅ [Portfolio] 서브그래프 빌드 완료 (조회/리밸런싱 모드)")

    return workflow
