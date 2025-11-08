"""
Report Generator Agent 서브그래프

Research + Strategy 결과를 통합하여 최종 Investment Dashboard 생성
"""
from langgraph.graph import StateGraph, END
import logging

from .state import ReportGeneratorState
from .nodes import generate_report_node

logger = logging.getLogger(__name__)


def build_report_generator_subgraph():
    """
    Report Generator Agent 서브그래프 생성

    Flow:
    START → generate_report → END

    단일 노드로 Research + Strategy 결과를 통합합니다.

    Returns:
        CompiledStateGraph
    """
    workflow = StateGraph(ReportGeneratorState)

    # 노드 추가
    workflow.add_node("generate_report", generate_report_node)

    # 플로우 정의
    workflow.set_entry_point("generate_report")
    workflow.add_edge("generate_report", END)

    logger.info("✅ [ReportGenerator] 서브그래프 빌드 완료")

    return workflow.compile(name="report_generator_agent")


# 서브그래프 인스턴스 export
report_generator_subgraph = build_report_generator_subgraph()
