"""
Research Agent 서브그래프

LangGraph 네이티브 구현
"""
from langgraph.graph import StateGraph, END
from .state import ResearchState
from .nodes import (
    collect_data_node,
    bull_analyst_node,
    bear_analyst_node,
    consensus_node
)
import logging

logger = logging.getLogger(__name__)


def build_research_subgraph():
    """
    Research Agent 서브그래프 생성

    Flow:
    collect_data → [bull_analysis, bear_analysis] → consensus → END
                        (병렬 실행)
    """
    workflow = StateGraph(ResearchState)

    # 노드 추가
    workflow.add_node("collect_data", collect_data_node)
    workflow.add_node("bull_analysis", bull_analyst_node)
    workflow.add_node("bear_analysis", bear_analyst_node)
    workflow.add_node("consensus", consensus_node)

    # 엣지 정의
    workflow.set_entry_point("collect_data")

    # 데이터 수집 후 병렬 분석
    workflow.add_edge("collect_data", "bull_analysis")
    workflow.add_edge("collect_data", "bear_analysis")

    # 병렬 분석 완료 후 합의
    workflow.add_edge("bull_analysis", "consensus")
    workflow.add_edge("bear_analysis", "consensus")

    # 종료
    workflow.add_edge("consensus", END)

    # 컴파일
    app = workflow.compile()

    logger.info("✅ [Research] 서브그래프 빌드 완료")

    return app


# Global compiled subgraph
research_subgraph = build_research_subgraph()
