"""Risk Agent State 정의."""
from typing import TypedDict, Optional, List, Annotated, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class RiskState(TypedDict):
    """Risk Agent 서브그래프 상태 (ReAct 패턴)"""

    messages: Annotated[List[BaseMessage], add_messages]

    request_id: str
    """요청 ID"""

    user_id: Optional[str]
    """사용자 ID (포트폴리오 조회용)"""

    portfolio_id: Optional[str]
    """포트폴리오 ID (직접 지정 시 사용)"""

    query: Optional[str]
    """사용자 쿼리"""

    # 입력 데이터
    portfolio_data: Optional[dict]
    """포트폴리오 데이터 (종목, 비중 등)"""

    market_data: Optional[dict]
    """시장 데이터 (변동성, 베타 등)"""

    portfolio_profile: Optional[dict]
    """사용자 프로필/투자 성향 정보"""

    # ReAct 제어 필드
    analysis_depth: Optional[Literal["quick", "standard", "comprehensive"]]
    """분석 깊이"""

    focus_areas: Optional[List[str]]
    """집중 영역 리스트 (concentration, market, scenario)"""

    depth_reason: Optional[str]
    """분석 깊이 결정 근거"""

    pending_tasks: Optional[List[dict]]
    """실행 대기 중인 작업 큐"""

    completed_tasks: Optional[List[dict]]
    """완료된 작업 리스트"""

    current_task: Optional[dict]
    """현재 실행 중인 작업"""

    task_notes: Optional[List[str]]
    """작업 진행 노트"""

    # 분석 결과
    concentration_risk: Optional[dict]
    """집중도 리스크 분석 결과"""

    market_risk: Optional[dict]
    """시장 리스크 분석 결과 (VaR, 변동성 등)"""

    risk_assessment: Optional[dict]
    """최종 리스크 평가"""

    # 에러
    error: Optional[str]
    """에러 메시지"""
