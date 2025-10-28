"""
Agent-related Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


class AgentInput(BaseModel):
    """Base agent input schema"""
    request_id: str
    user_id: Optional[str] = None
    automation_level: int = Field(default=2, ge=1, le=3)
    context: Optional[Dict[str, Any]] = None


class AgentOutput(BaseModel):
    """Base agent output schema"""
    status: str  # success, failure, pending
    data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ResearchRequest(AgentInput):
    """Research agent request"""
    stock_code: str
    analysis_type: Optional[str] = "comprehensive"  # fundamental, technical, comprehensive


class FundamentalSummary(BaseModel):
    """펀더멘털 분석 요약"""
    PER: Optional[float] = Field(None, description="주가수익비율 (Price-to-Earnings Ratio)")
    PBR: Optional[float] = Field(None, description="주가순자산비율 (Price-to-Book Ratio)")
    EPS: Optional[int] = Field(None, description="주당순이익 (Earnings Per Share)")
    DIV: Optional[float] = Field(None, description="배당수익률 (%)")
    valuation: str = Field(default="적정", description="밸류에이션 상태: 저평가/적정/고평가")


class InvestorSummary(BaseModel):
    """투자주체별 매매 동향 요약"""
    foreign_trend: str = Field(default="보합", description="외국인 매매 동향: 매수/매도/보합")
    institution_trend: str = Field(default="보합", description="기관 매매 동향: 매수/매도/보합")
    foreign_net: Optional[int] = Field(None, description="외국인 순매수액 (원)")
    institution_net: Optional[int] = Field(None, description="기관 순매수액 (원)")
    sentiment: str = Field(default="중립", description="투자주체 종합 심리: 긍정/중립/부정")


class TechnicalSummary(BaseModel):
    """기술적 분석 요약"""
    trend: str = Field(default="중립", description="전체 추세: 강세/중립/약세")
    rsi: str = Field(default="중립", description="RSI 시그널: 과매수/중립/과매도")
    signals: List[str] = Field(default_factory=list, description="기술적 시그널 목록")


class ResearchResponse(AgentOutput):
    """
    Research agent response (확장된 구조)

    - 펀더멘털 분석 (PER/PBR/EPS/배당수익률)
    - 투자주체별 매매 동향 (외국인/기관)
    - 기술적 분석 (RSI/MACD/볼린저밴드)
    - Bull/Bear 케이스
    - 최종 추천 및 목표가
    """
    stock_code: str
    rating: Optional[int] = None
    recommendation: Optional[str] = Field(None, description="투자 의견: BUY/HOLD/SELL")
    target_price: Optional[int] = Field(None, description="목표가 (원)")
    current_price: Optional[int] = Field(None, description="현재가 (원)")
    upside_potential: Optional[str] = Field(None, description="상승 여력 (%)")
    confidence: Optional[int] = Field(None, description="신뢰도 (1-5)")

    # 확장된 분석 정보
    fundamental_summary: Optional[FundamentalSummary] = None
    investor_summary: Optional[InvestorSummary] = None
    technical_summary: Optional[TechnicalSummary] = None
    market_cap_trillion: Optional[float] = Field(None, description="시가총액 (조원)")

    # 기존 필드
    summary: Optional[str] = None
    bull_case: Optional[List[str]] = None
    bear_case: Optional[List[str]] = None


class StrategyRequest(AgentInput):
    """Strategy agent request"""
    query_type: str  # analyze, recommend, screen
    stock_codes: Optional[List[str]] = None
    criteria: Optional[Dict[str, Any]] = None


class StrategyResponse(AgentOutput):
    """Strategy agent response"""
    action: Optional[str] = None  # BUY, SELL, HOLD
    confidence: Optional[Decimal] = None
    reasoning: Optional[str] = None
    bull_confidence: Optional[Decimal] = None
    bear_confidence: Optional[Decimal] = None


class RiskRequest(AgentInput):
    """Risk agent request"""
    assessment_type: str  # portfolio, position, trade
    portfolio_id: Optional[str] = None
    proposed_action: Optional[Dict[str, Any]] = None


class RiskResponse(AgentOutput):
    """Risk agent response"""
    risk_level: str  # low, medium, high, critical
    risk_score: Optional[Decimal] = None
    warnings: List[str] = []
    recommendations: List[str] = []
    should_trigger_hitl: bool = False


class HITLRequest(BaseModel):
    """HITL approval request"""
    request_type: str
    title: str
    description: str
    proposed_actions: List[Dict[str, Any]]
    impact_analysis: Optional[Dict[str, Any]] = None
    risk_warnings: List[str] = []
    alternatives: Optional[List[Dict[str, Any]]] = None
    urgency: str = "medium"


class HITLResponse(BaseModel):
    """HITL approval response"""
    request_id: str
    decision: str  # approved, rejected, modified
    selected_option: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None
    user_notes: Optional[str] = None