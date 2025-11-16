"""
Quantitative Agent Graph 정의

정량적 분석 → 전략 수립
"""
import logging

from langgraph.graph import StateGraph, END

from src.subgraphs.quantitative_subgraph.state import QuantitativeState
from src.subgraphs.quantitative_subgraph.nodes import (
    # 거시 분석
    market_cycle_node,
    sector_allocation_node,
    asset_allocation_node,
    # 데이터 수집 및 분석
    data_collector_node,
    fundamental_analyst_node,
    technical_analyst_node,
    # 전략 세분화
    buy_decision_node,
    sell_decision_node,
    risk_reward_node,
    strategy_synthesis_node,
    # Blueprint
    blueprint_creation_node,
)

logger = logging.getLogger(__name__)


def build_quantitative_subgraph() -> StateGraph:
    """
    Quantitative SubGraph 생성 (Enhanced)

    Flow:
    1. 거시 분석: market_cycle → sector_allocation → asset_allocation
    2. 데이터 수집 및 분석: data_collector → fundamental_analyst → technical_analyst
    3. 전략 세분화: buy_decision → sell_decision → risk_reward → strategy_synthesis
    4. Blueprint: blueprint_creation
    """
    workflow = StateGraph(QuantitativeState)

    # 노드 추가
    # 1. 거시 분석
    workflow.add_node("market_cycle", market_cycle_node)
    workflow.add_node("sector_allocation", sector_allocation_node)
    workflow.add_node("asset_allocation", asset_allocation_node)

    # 2. 데이터 수집 및 분석
    workflow.add_node("data_collector", data_collector_node)
    workflow.add_node("fundamental_analyst", fundamental_analyst_node)
    workflow.add_node("technical_analyst", technical_analyst_node)

    # 3. 전략 세분화
    workflow.add_node("buy_decision", buy_decision_node)
    workflow.add_node("sell_decision", sell_decision_node)
    workflow.add_node("risk_reward", risk_reward_node)
    workflow.add_node("strategy_synthesis", strategy_synthesis_node)

    # 4. Blueprint
    workflow.add_node("blueprint_creation", blueprint_creation_node)

    # 엣지 정의 (선형 플로우)
    workflow.set_entry_point("market_cycle")

    # 1. 거시 분석 체인
    workflow.add_edge("market_cycle", "sector_allocation")
    workflow.add_edge("sector_allocation", "asset_allocation")
    workflow.add_edge("asset_allocation", "data_collector")

    # 2. 데이터 수집 및 분석 체인
    workflow.add_edge("data_collector", "fundamental_analyst")
    workflow.add_edge("fundamental_analyst", "technical_analyst")

    # 3. 전략 세분화 체인
    workflow.add_edge("technical_analyst", "buy_decision")
    workflow.add_edge("buy_decision", "sell_decision")
    workflow.add_edge("sell_decision", "risk_reward")
    workflow.add_edge("risk_reward", "strategy_synthesis")

    # 4. Blueprint 생성
    workflow.add_edge("strategy_synthesis", "blueprint_creation")
    workflow.add_edge("blueprint_creation", END)

    logger.info("✅ [Quantitative] Enhanced SubGraph 생성 완료 (10개 노드)")

    return workflow


# Supervisor 패턴용 export (컴파일된 SubGraph)
# checkpointer는 Supervisor에서 자동 상속되므로 생략
quantitative_subgraph = build_quantitative_subgraph().compile(
    name="quantitative_agent"
)

# Alias for backward compatibility
quantitative_agent = quantitative_subgraph
