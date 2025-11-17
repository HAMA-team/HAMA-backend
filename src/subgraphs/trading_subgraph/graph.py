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
    trade_planner_node,
)
from .state import TradingState

logger = logging.getLogger(__name__)


def should_resimulate_trade(state: TradingState) -> str:
    """
    사용자 수정사항이 있어 재시뮬레이션이 필요한지 판단.
    """
    if not state.get("trade_approved", False):
        return "portfolio_simulator"
    if state.get("trade_prepared", False):
        return "execute_trade"
    return "execute_trade"


def build_trading_subgraph() -> StateGraph:
    """
    Trading SubGraph 생성.
    """
    workflow = StateGraph(TradingState)

    workflow.add_node("trade_planner", trade_planner_node)
    workflow.add_node("portfolio_simulator", portfolio_simulator_node)
    workflow.add_node("trade_hitl", trade_hitl_node)
    workflow.add_node("execute_trade", execute_trade_node)

    workflow.add_edge(START, "trade_planner")
    workflow.add_edge("trade_planner", "portfolio_simulator")
    workflow.add_edge("portfolio_simulator", "trade_hitl")

    workflow.add_conditional_edges(
        "trade_hitl",
        should_resimulate_trade,
        {
            "portfolio_simulator": "portfolio_simulator",
            "execute_trade": "execute_trade",
        },
    )

    workflow.add_edge("execute_trade", END)

    logger.info("✅ [Trading SubGraph] 생성 완료")

    return workflow


__all__ = ["build_trading_subgraph", "should_resimulate_trade"]
