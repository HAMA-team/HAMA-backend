"""
General Agent State 정의 (ReAct 래퍼용)
"""
from typing import TypedDict, Optional, Dict, Any, List, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GeneralState(TypedDict, total=False):
    """
    General Agent 서브그래프 State

    ReAct 에이전트 호출 전/후 메시지와 결과를 보관한다.
    """

    # LangGraph 표준 메시지 스택
    messages: Annotated[List[BaseMessage], add_messages]

    # 원본 사용자 질문 (Supervisor 초기 상태에서 전달)
    query: Optional[str]

    # 에이전트별 실행 결과 (GraphState.agent_results와 병합)
    agent_results: Dict[str, Any]

