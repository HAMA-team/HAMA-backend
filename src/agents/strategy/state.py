"""
Strategy Agent State 정의

Langgraph 서브그래프를 위한 State
"""
from typing import TypedDict, Optional, List, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class StrategyState(TypedDict):
    """
    Strategy Agent 서브그래프 State

    Flow:
    1. market_analysis: 시장 사이클 분석
    2. sector_rotation: 섹터 전략 수립
    3. asset_allocation: 자산 배분 결정
    4. blueprint_creation: Strategic Blueprint 생성
    """

    # Supervisor 패턴 호환성
    messages: Annotated[List[BaseMessage], add_messages]
    """메시지 스택 (Supervisor 패턴 필수)"""

    # 입력
    request_id: str
    """요청 ID"""

    user_preferences: Optional[dict]
    """사용자 선호도"""

    risk_tolerance: str
    """리스크 허용도 (conservative, moderate, aggressive)"""

    # 분석 결과
    market_outlook: Optional[dict]
    """시장 전망 (시장 사이클, 신뢰도 등)"""

    sector_strategy: Optional[dict]
    """섹터 전략 (overweight, underweight 섹터)"""

    asset_allocation: Optional[dict]
    """자산 배분 (주식, 현금 비율)"""

    blueprint: Optional[dict]
    """최종 Strategic Blueprint"""

    # 메타데이터
    error: Optional[str]
    """에러 메시지"""
