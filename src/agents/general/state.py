"""
General Agent State 정의
"""
from typing import TypedDict, Optional, List, Annotated, Dict, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GeneralState(TypedDict, total=False):
    """
    General Agent 서브그래프 State

    Flow:
    1. planner: 조사 계획 수립
    2. worker loop: search → analysis → insight
    3. synthesis: 최종 답변 생성
    """

    # Supervisor 패턴 호환성
    messages: Annotated[List[BaseMessage], add_messages]
    """메시지 스택 (Supervisor 패턴 필수)"""

    # 입력
    request_id: Optional[str]
    """요청 ID"""

    query: Optional[str]
    """사용자 질문"""

    # Deep Agent 루프 제어
    plan: Optional[Dict[str, Any]]
    """LLM이 생성한 조사 계획"""

    pending_tasks: Optional[List[Dict[str, Any]]]
    """대기 중인 작업"""

    completed_tasks: Optional[List[Dict[str, Any]]]
    """완료된 작업"""

    current_task: Optional[Dict[str, Any]]
    """현재 실행 중인 작업"""

    task_notes: Optional[List[str]]
    """작업 메모"""

    # 검색 및 분석 결과
    search_results: Optional[List[Dict[str, Any]]]
    """웹 검색 결과"""

    analysis: Optional[Dict[str, Any]]
    """검색 결과 기반 요약"""

    insight_summary: Optional[Dict[str, Any]]
    """추가 인사이트 및 후속 질문"""

    # 출력
    answer: Optional[str]
    """응답 내용"""

    sources: Optional[List[Dict[str, Any]]]
    """참고 자료 (RAG 사용 시)"""

    # 메타데이터
    error: Optional[str]
    """에러 메시지"""
