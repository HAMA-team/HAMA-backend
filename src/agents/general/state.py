"""
General Agent State 정의

일반 질의응답을 위한 State
"""
from typing import TypedDict, Optional, List


class GeneralState(TypedDict):
    """
    General Agent 서브그래프 State

    Flow:
    1. answer_question: LLM 기반 질문 응답
    """

    # 입력
    request_id: str
    """요청 ID"""

    query: str
    """사용자 질문"""

    # 출력
    answer: Optional[str]
    """응답 내용"""

    sources: Optional[List[str]]
    """참고 자료 (RAG 사용 시)"""

    # 메타데이터
    error: Optional[str]
    """에러 메시지"""
