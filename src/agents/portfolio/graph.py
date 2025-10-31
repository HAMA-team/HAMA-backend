"""Portfolio Agent 서브그래프

포트폴리오 분석 및 리밸런싱 제안을 위한 Langgraph 그래프"""
from __future__ import annotations

from langgraph.graph import StateGraph, END
import logging

from .state import PortfolioState
from .nodes import (
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


def build_portfolio_subgraph():
    """
    Portfolio Agent 서브그래프 생성

    Flow:
    collect_portfolio → market_condition → optimize_allocation
    → validate_constraints → rebalance_plan → summary
    → approval_rebalance (HITL Interrupt) → execute_rebalance → END

    새로운 기능:
    - market_condition: 시장 상황 분석 및 최대 슬롯 조정
    - validate_constraints: 포트폴리오 제약 조건 검증
    - approval_rebalance: HITL 승인 노드 (interrupt_before)
    - execute_rebalance: 승인된 리밸런싱 실행
    """
    workflow = StateGraph(PortfolioState)

    # 노드 추가
    workflow.add_node("collect_portfolio", collect_portfolio_node)
    workflow.add_node("market_condition", market_condition_node)
    workflow.add_node("optimize_allocation", optimize_allocation_node)
    workflow.add_node("validate_constraints", validate_constraints_node)
    workflow.add_node("rebalance_plan", rebalance_plan_node)
    workflow.add_node("summary", summary_node)
    workflow.add_node("approval_rebalance", approval_rebalance_node)
    workflow.add_node("execute_rebalance", execute_rebalance_node)

    # 플로우 정의
    workflow.set_entry_point("collect_portfolio")
    workflow.add_edge("collect_portfolio", "market_condition")
    workflow.add_edge("market_condition", "optimize_allocation")
    workflow.add_edge("optimize_allocation", "validate_constraints")
    workflow.add_edge("validate_constraints", "rebalance_plan")
    workflow.add_edge("rebalance_plan", "summary")
    workflow.add_edge("summary", "approval_rebalance")  # HITL 노드로 연결
    workflow.add_edge("approval_rebalance", "execute_rebalance")
    workflow.add_edge("execute_rebalance", END)

    # HITL을 위해 여기서는 compile하지 않고 workflow만 반환
    # __init__.py에서 interrupt_before와 checkpointer 설정 후 compile
    logger.info("✅ [Portfolio] 서브그래프 빌드 완료 (HITL 포함)")

    return workflow
