"""Portfolio Agent State 정의."""
from __future__ import annotations

from typing import TypedDict, Optional, List, Literal, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class PortfolioHolding(TypedDict, total=False):
    """포트폴리오 내 단일 자산 정보"""

    stock_code: str
    stock_name: str
    weight: float
    value: float


class RebalanceInstruction(TypedDict, total=False):
    """리밸런싱 실행 지시"""

    action: Literal["BUY", "SELL"]
    stock_code: str
    stock_name: str
    amount: float
    weight_delta: float


class PortfolioState(TypedDict, total=False):
    """Portfolio Agent 서브그래프 State"""

    messages: Annotated[List[BaseMessage], add_messages]

    # 입력
    request_id: str
    user_id: Optional[str]
    automation_level: int
    risk_profile: Optional[str]
    horizon: Optional[str]
    preferences: Optional[dict]

    portfolio_profile: Optional[dict]
    """사용자 프로필 / 투자 성향 캡처"""

    # 현재 포트폴리오 스냅샷
    portfolio_id: Optional[str]
    total_value: Optional[float]
    current_holdings: Optional[List[PortfolioHolding]]

    # 추천 산출값
    proposed_allocation: Optional[List[PortfolioHolding]]
    expected_return: Optional[float]
    expected_volatility: Optional[float]
    sharpe_ratio: Optional[float]
    rationale: Optional[str]

    # 리밸런싱 정보
    rebalancing_needed: Optional[bool]
    trades_required: Optional[List[RebalanceInstruction]]
    hitl_required: bool

    # 포트폴리오 제약 조건
    max_slots: Optional[int]
    """최대 보유 종목 수 (기본 10개)"""

    max_sector_concentration: Optional[float]
    """섹터 집중도 제한 (기본 30%)"""

    max_same_industry_count: Optional[int]
    """동일 산업군 최대 종목 수 (기본 3개)"""

    market_condition: Optional[str]
    """시장 상황 (강세장/중립장/약세장)"""

    constraint_violations: Optional[List[dict]]
    """제약 조건 위반 내역"""

    # 최종 리포트
    summary: Optional[str]
    portfolio_report: Optional[dict]

    portfolio_snapshot: Optional[dict]
    """서비스에서 내려온 전체 스냅샷 (시장/프로필 포함)"""

    # 에러 처리
    error: Optional[str]
