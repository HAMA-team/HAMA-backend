"""
Strategy Agent 서브그래프

LangGraph 네이티브 구현
"""
from langgraph.graph import StateGraph, END
from .state import StrategyState
from .nodes import (
    market_analysis_node,
    sector_rotation_node,
    asset_allocation_node,
    blueprint_creation_node
)
import logging

logger = logging.getLogger(__name__)


def build_strategy_subgraph():
    """
    Strategy Agent 서브그래프 생성

    Flow:
    market_analysis → sector_rotation → asset_allocation → blueprint_creation → END
    """
    workflow = StateGraph(StrategyState)

    # 노드 추가
    workflow.add_node("market_analysis", market_analysis_node)
    workflow.add_node("sector_rotation", sector_rotation_node)
    workflow.add_node("asset_allocation", asset_allocation_node)
    workflow.add_node("blueprint_creation", blueprint_creation_node)

    # 엣지 정의 (순차 실행)
    workflow.set_entry_point("market_analysis")
    workflow.add_edge("market_analysis", "sector_rotation")
    workflow.add_edge("sector_rotation", "asset_allocation")
    workflow.add_edge("asset_allocation", "blueprint_creation")
    workflow.add_edge("blueprint_creation", END)

    # 컴파일
    app = workflow.compile()

    logger.info("✅ [Strategy] 서브그래프 빌드 완료")

    return app


# Global compiled subgraph
strategy_subgraph = build_strategy_subgraph()
