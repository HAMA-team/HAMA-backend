"""
Risk Agent State 정의

리스크 평가 서브그래프의 상태 관리
"""
from typing import TypedDict, Optional


class RiskState(TypedDict):
    """Risk Agent 서브그래프 상태"""

    request_id: str
    """요청 ID"""

    # 입력 데이터
    portfolio_data: Optional[dict]
    """포트폴리오 데이터 (종목, 비중 등)"""

    market_data: Optional[dict]
    """시장 데이터 (변동성, 베타 등)"""

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
