"""
Strategy Agent 관련 스키마 정의

Strategic Blueprint: 거시 대전략 출력물
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from decimal import Decimal


class MarketCycle(BaseModel):
    """시장 사이클 정보"""
    cycle: str = Field(..., description="시장 사이클 (early_bull, mid_bull, late_bull, bear, consolidation)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="신뢰도 (0-1)")
    summary: str = Field(..., description="시장 전망 요약")


class SectorWeight(BaseModel):
    """섹터별 비중"""
    sector: str = Field(..., description="섹터명 (IT, 반도체, 금융, 헬스케어, 에너지 등)")
    weight: Decimal = Field(..., ge=0, le=1, description="목표 비중 (0-1)")
    stance: str = Field(..., description="투자 스탠스 (overweight, neutral, underweight)")


class SectorStrategy(BaseModel):
    """섹터 전략"""
    sectors: List[SectorWeight] = Field(..., description="섹터별 비중")
    overweight: List[str] = Field(default_factory=list, description="비중 확대 섹터")
    underweight: List[str] = Field(default_factory=list, description="비중 축소 섹터")
    rationale: str = Field(..., description="섹터 전략 근거")


class AssetAllocation(BaseModel):
    """자산 배분"""
    stocks: Decimal = Field(..., ge=0, le=1, description="주식 비중 (0-1)")
    cash: Decimal = Field(..., ge=0, le=1, description="현금 비중 (0-1)")
    rationale: str = Field(..., description="자산 배분 근거")


class InvestmentStyle(BaseModel):
    """투자 스타일"""
    type: str = Field(..., description="투자 유형 (growth, value, dividend, balanced)")
    horizon: str = Field(..., description="투자 기간 (short_term, mid_term, long_term)")
    approach: str = Field(..., description="투자 방식 (lump_sum, dollar_cost_averaging)")
    size_preference: str = Field(default="large", description="시가총액 선호 (large, mid, small)")


class StrategicBlueprint(BaseModel):
    """
    Strategic Blueprint - 거시 대전략 청사진

    Strategy Agent의 출력물로, Portfolio Agent에게 전달됨
    """
    market_outlook: MarketCycle = Field(..., description="시장 전망")
    sector_strategy: SectorStrategy = Field(..., description="섹터 전략")
    asset_allocation: AssetAllocation = Field(..., description="자산 배분 목표")
    investment_style: InvestmentStyle = Field(..., description="투자 스타일")
    risk_tolerance: str = Field(..., description="리스크 허용도 (conservative, moderate, aggressive)")

    # 제약조건
    constraints: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="추가 제약조건 (max_per_stock, min_stocks 등)"
    )

    # 메타데이터
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="전체 신뢰도")
    key_assumptions: List[str] = Field(default_factory=list, description="핵심 가정")


class StrategyContext(BaseModel):
    """Strategy Agent 입력 컨텍스트"""
    user_preferences: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="사용자 선호 설정"
    )
    portfolio_balance: Optional[Decimal] = Field(
        None,
        description="투자 가능 금액"
    )
    existing_holdings: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="기존 보유 종목"
    )
