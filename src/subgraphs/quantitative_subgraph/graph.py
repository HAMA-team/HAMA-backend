"""
Quantitative Agent Graph 정의

정량적 분석 → 전략 수립
"""
import logging

from langgraph.graph import StateGraph, END

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    from langgraph.checkpoints.memory import MemorySaver

from src.subgraphs.quantitative_subgraph.state import QuantitativeState
from src.subgraphs.quantitative_subgraph.nodes import (
    data_collector_node,
    fundamental_analyst_node,
    technical_analyst_node,
    strategy_synthesis_node,
)

logger = logging.getLogger(__name__)


def build_quantitative_subgraph() -> StateGraph:
    """
    Quantitative SubGraph 생성

    Flow: 데이터 수집 → 펀더멘털 분석 → 기술적 분석 → 전략 수립
    """
    workflow = StateGraph(QuantitativeState)

    # 노드 추가
    workflow.add_node("data_collector", data_collector_node)
    workflow.add_node("fundamental_analyst", fundamental_analyst_node)
    workflow.add_node("technical_analyst", technical_analyst_node)
    workflow.add_node("strategy_synthesis", strategy_synthesis_node)

    # 엣지 정의 (선형 플로우)
    workflow.set_entry_point("data_collector")
    workflow.add_edge("data_collector", "fundamental_analyst")
    workflow.add_edge("fundamental_analyst", "technical_analyst")
    workflow.add_edge("technical_analyst", "strategy_synthesis")
    workflow.add_edge("strategy_synthesis", END)

    logger.info("✅ [Quantitative] SubGraph 생성 완료")

    return workflow


# Supervisor 패턴용 export (컴파일된 SubGraph)
quantitative_subgraph = build_quantitative_subgraph().compile(
    name="quantitative_agent",
    checkpointer=MemorySaver()
)

# Alias for backward compatibility
quantitative_agent = quantitative_subgraph
