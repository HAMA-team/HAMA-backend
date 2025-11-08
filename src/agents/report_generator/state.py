"""Report Generator Agent State 정의."""
from typing import TypedDict, Optional, List, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ReportGeneratorState(TypedDict):
    """
    Report Generator Agent 서브그래프 상태

    Research Agent와 Strategy Agent의 결과를 통합하여
    최종 Investment Dashboard를 생성합니다.
    """

    messages: Annotated[List[BaseMessage], add_messages]
    """메시지 스택 (Supervisor 패턴 필수)"""

    request_id: str
    """요청 ID"""

    query: Optional[str]
    """사용자 쿼리"""

    # 입력 데이터 (다른 Agent 결과)
    research_result: Optional[dict]
    """Research Agent의 분석 결과"""

    strategy_result: Optional[dict]
    """Strategy Agent의 Blueprint 결과"""

    agent_results: Optional[dict]
    """모든 Agent 결과 (MasterState 공유용)"""

    # 출력 데이터
    final_report: Optional[dict]
    """최종 통합 Investment Report"""

    dashboard_content: Optional[str]
    """최종 Dashboard 텍스트 (마크다운)"""

    # 에러
    error: Optional[str]
    """에러 메시지"""
