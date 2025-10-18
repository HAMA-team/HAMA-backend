"""
General Agent 서브그래프

일반 질의응답을 위한 Langgraph 서브그래프
"""
from langgraph.graph import StateGraph, END
from .state import GeneralState
from .nodes import answer_question_node
import logging

logger = logging.getLogger(__name__)


def build_general_subgraph():
    """
    General Agent 서브그래프 생성

    Flow:
    answer_question → END

    단순한 Q&A 에이전트 (HITL 없음)
    """
    workflow = StateGraph(GeneralState)

    # 노드 추가
    workflow.add_node("answer_question", answer_question_node)

    # 엣지 정의
    workflow.set_entry_point("answer_question")

    # 종료
    workflow.add_edge("answer_question", END)

    # 컴파일
    app = workflow.compile(name="general_agent")

    logger.info("✅ [General] 서브그래프 빌드 완료")

    return app


# Global compiled subgraph
general_subgraph = build_general_subgraph()
