"""Portfolio Agent 서브그래프

포트폴리오 분석 및 리밸런싱 제안을 위한 Langgraph 그래프"""
from __future__ import annotations

from langgraph.graph import StateGraph, END
import logging

from .state import PortfolioState
from .nodes import (
    collect_portfolio_node,
    optimize_allocation_node,
    rebalance_plan_node,
    summary_node,
)

logger = logging.getLogger(__name__)


def build_portfolio_subgraph():
    """Portfolio Agent 서브그래프 생성"""
    workflow = StateGraph(PortfolioState)

    workflow.add_node("collect_portfolio", collect_portfolio_node)
    workflow.add_node("optimize_allocation", optimize_allocation_node)
    workflow.add_node("rebalance_plan", rebalance_plan_node)
    workflow.add_node("summary", summary_node)

    workflow.set_entry_point("collect_portfolio")
    workflow.add_edge("collect_portfolio", "optimize_allocation")
    workflow.add_edge("optimize_allocation", "rebalance_plan")
    workflow.add_edge("rebalance_plan", "summary")
    workflow.add_edge("summary", END)

    app = workflow.compile(name="portfolio_agent")

    logger.info("✅ [Portfolio] 서브그래프 빌드 완료")

    return app


portfolio_subgraph = build_portfolio_subgraph()
