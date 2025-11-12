"""Quantitative Agent State 정의."""
from typing import TypedDict, Optional, List, Annotated, Dict, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class QuantitativeState(TypedDict, total=False):
    """
    Quantitative Agent 서브그래프 State

    정량적 분석 및 전략 수립에 초점을 맞춘 SubGraph

    Flow:
    1. data_collector: 재무제표, 기술적 지표 수집
    2. analyst loop: fundamental → technical → strategy
    3. synthesis: 최종 전략 제안

    Note: total=False로 설정하여 partial update 지원 (Langgraph 패턴)
    """

    # Langgraph 메시지 스택
    messages: Annotated[List[BaseMessage], add_messages]

    # 입력
    stock_code: Optional[str]
    """종목 코드"""

    query: Optional[str]
    """사용자 질문"""

    request_id: Optional[str]
    """요청 ID"""

    # 분석 깊이 제어
    analysis_depth: Optional[str]
    """분석 깊이 레벨 ("quick" | "standard" | "comprehensive")"""

    focus_areas: Optional[List[str]]
    """집중 분석 영역 (예: ["valuation", "technical", "market_cycle"])"""

    depth_reason: Optional[str]
    """분석 깊이 선택 이유"""

    user_profile: Optional[Dict[str, Any]]
    """사용자 프로파일"""

    # Deep Agent 루프 제어
    plan: Optional[Dict[str, Any]]
    """분석 계획"""

    pending_tasks: Optional[List[Dict[str, Any]]]
    """남은 작업 목록"""

    completed_tasks: Optional[List[Dict[str, Any]]]
    """완료된 작업"""

    current_task: Optional[Dict[str, Any]]
    """현재 작업"""

    task_notes: Optional[List[str]]
    """작업 메모"""

    # 데이터 수집 결과
    financial_statements: Optional[dict]
    """재무제표 (DART API)"""

    valuation_metrics: Optional[dict]
    """밸류에이션 지표 (PER, PBR, PSR, EV/EBITDA)"""

    growth_metrics: Optional[dict]
    """성장성 지표 (매출/영업이익 성장률, ROE, ROA)"""

    technical_indicators: Optional[dict]
    """기술적 지표 (RSI, MACD, Bollinger Bands 등)"""

    market_data: Optional[dict]
    """시장 데이터 (거래량, 시가총액, 베타)"""

    sector_data: Optional[dict]
    """섹터 데이터 (섹터 평균 PER, 섹터 성과)"""

    # 분석 결과
    fundamental_analysis: Optional[dict]
    """펀더멘털 분석 결과 (재무건전성, 수익성, 성장성)"""

    valuation_analysis: Optional[dict]
    """밸류에이션 분석 (적정 주가, 할인/프리미엄)"""

    technical_analysis: Optional[dict]
    """기술적 분석 (추세, 모멘텀, 지지/저항)"""

    market_cycle_analysis: Optional[dict]
    """시장 사이클 분석 (Bull/Bear, 섹터 로테이션)"""

    risk_analysis: Optional[dict]
    """리스크 분석 (변동성, 하락 리스크)"""

    # 전략 결과
    strategy: Optional[dict]
    """
    최종 전략 제안
    {
        "action": "buy" | "hold" | "sell",
        "confidence": 0-100,
        "target_price": float,
        "stop_loss": float,
        "reasoning": str,
        "time_horizon": "단기" | "중기" | "장기"
    }
    """

    # 메타데이터
    error: Optional[str]
    """에러 메시지"""
