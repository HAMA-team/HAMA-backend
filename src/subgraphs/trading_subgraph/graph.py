"""
Trading SubGraph Graph 정의

trade_planner → portfolio_simulator → trade_hitl → execute_trade
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from .nodes import (
    execute_trade_node,
    portfolio_simulator_node,
    trade_hitl_node,
    trade_hitl_resume_node,
    trade_planner_node,
)
from .state import TradingState

logger = logging.getLogger(__name__)


def should_resimulate_trade(state: TradingState) -> str:
    """
    trade_hitl 노드 이후 다음 노드 결정
    """
    current_prepared = state.get("trade_prepared", False)
    current_approved = state.get("trade_approved")
    logger.info(
        f"🔍 [Trading/Graph] should_resimulate_trade 진입: prepared={current_prepared}, approved={current_approved}")

    # 1. 거부(Rejected)된 경우, 즉시 END로 종료
    if state.get("trade_approved") is False:
        logger.info("❌ [Trading/Graph] 사용자 거부 → END로 종료")
        return END  # LangGraph의 END 상수를 반환하여 그래프 종료

    # 2. 매매 준비 완료 (수정 없이 승인된 경우) → 실행
    if state.get("trade_prepared", False):
        logger.info("✅ [Trading/Graph] 매매 준비 완료 → execute_trade 실행")
        return "execute_trade"

    # 3. 수정되었거나 기타 이유로 재시뮬레이션이 필요한 경우
    # (trade_approved=True이지만 trade_prepared=False인 상태)
    logger.info("🔄 [Trading/Graph] 수정 또는 재검토 필요 → portfolio_simulator 실행")
    return "portfolio_simulator"


def build_trading_subgraph() -> StateGraph:
    """
    Trading SubGraph 생성.
    """
    workflow = StateGraph(TradingState)

    workflow.add_node("trade_planner", trade_planner_node)
    workflow.add_node("portfolio_simulator", portfolio_simulator_node)
    workflow.add_node("trade_hitl", trade_hitl_node)
    workflow.add_node("trade_hitl_resume", trade_hitl_resume_node)  # Resume 처리 노드
    workflow.add_node("execute_trade", execute_trade_node)

    workflow.add_edge(START, "trade_planner")
    workflow.add_edge("trade_planner", "portfolio_simulator")
    workflow.add_edge("portfolio_simulator", "trade_hitl")

    # trade_hitl에서 interrupt 후, user_decision이 들어오면 trade_hitl_resume으로 이동
    def should_process_user_decision(state: TradingState) -> str:
        """사용자 결정 대기 여부 판단"""
        user_decision = state.get("user_decision")
        if user_decision is not None:
            return "trade_hitl_resume"
        return END

    workflow.add_conditional_edges(
        "trade_hitl",
        should_process_user_decision,
        {
            "trade_hitl_resume": "trade_hitl_resume",
            END: END,
        },
    )

    # trade_hitl_resume 후 결정된 경로로 이동
    workflow.add_conditional_edges(
        "trade_hitl_resume",
        should_resimulate_trade,
        {
            "portfolio_simulator": "portfolio_simulator",
            "execute_trade": "execute_trade",
            END: END,
        },
    )

    workflow.add_edge("execute_trade", END)

    logger.info("✅ [Trading SubGraph] 생성 완료")

    return workflow


__all__ = ["build_trading_subgraph", "should_resimulate_trade"]
