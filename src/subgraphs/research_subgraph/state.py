"""Research Agent State 정의."""
from typing import TypedDict, Optional, List, Annotated, Dict, Any
from operator import add

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ResearchState(TypedDict, total=False):
    """
    Research Agent 서브그래프 State

    Flow:
    1. planner: 조사 계획 수립
    2. worker loop: data → bull → bear → insight
    3. synthesis: 최종 의견 통합

    Note: total=False로 설정하여 partial update 지원 (Langgraph 패턴)
    """

    # Langgraph 메시지 스택
    messages: Annotated[List[BaseMessage], add_messages]

    # 입력
    stock_code: Optional[str]
    """종목 코드"""

    query: Optional[str]
    """사용자 질문(종목 코드 추출용)"""

    request_id: Optional[str]
    """요청 ID (Supervisor 호출 시 없을 수 있음)"""

    # UI 기반 분석 설정
    depth: Optional[str]
    """분석 깊이: "brief" | "detailed" | "comprehensive" """

    scope: Optional[str]
    """분석 범위: "key_points" | "balanced" | "wide_coverage" """

    perspectives: Optional[List[str]]
    """선택된 관점: ["macro", "fundamental", "technical", "flow", "strategy", "bull_case", "bear_case"]"""

    analysis_depth: Optional[str]
    """실제 데이터 수집에 사용되는 깊이: "brief" | "detailed" | "comprehensive" """

    method: Optional[str]
    """분석 방법: "qualitative" | "quantitative" | "both" (UI 표시용)"""

    # HITL 플래그
    analysis_plan_approved: Optional[bool]
    """사용자 승인 완료"""

    plan_approval_id: Optional[str]
    """승인 요청 ID"""

    intervention_required: Optional[bool]
    """분석/전략 단계부터 HITL 필요 여부 (False: 매매만 HITL, True: 모든 단계 HITL)"""

    user_profile: Optional[Dict[str, Any]]
    """사용자 프로파일 (preferred_depth, expertise_level 등)"""

    user_modifications: Optional[Dict[str, Any]]
    """사용자가 modify를 통해 수정한 설정
    - structured: {depth, scope, perspectives} 구조화된 수정
    - user_input: 자유 텍스트 (예: '반도체 사업부에 집중해주세요')
    """

    hitl_config: Optional[Dict[str, Any]]
    """HITL 설정 (phases.analysis, phases.data_collection 등)"""

    # 작업 추적
    plan: Optional[Dict[str, Any]]
    """LLM이 생성한 조사 계획"""

    pending_tasks: Optional[List[Dict[str, Any]]]
    """planner가 생성한 작업 목록 (병렬 실행용)"""

    completed_tasks: Annotated[Optional[List[Dict[str, Any]]], add]
    """완료된 작업 및 산출물 (병렬 실행 시 자동 병합)"""

    task_notes: Annotated[Optional[List[str]], add]
    """작업 중 생성된 요약/메모 (병렬 실행 시 자동 병합)"""

    # 데이터 수집 결과
    price_data: Optional[dict]
    """주가 데이터 (pykrx)"""

    financial_data: Optional[dict]
    """재무제표 데이터 (DART)"""

    company_data: Optional[dict]
    """기업 정보 (DART)"""

    market_index_data: Optional[dict]
    """시장 지수 데이터 (KOSPI, KOSDAQ) - Mock 데이터 포함"""

    # 펀더멘털 데이터 (신규)
    fundamental_data: Optional[dict]
    """펀더멘털 지표 (PER, PBR, EPS, DIV, DPS, BPS)"""

    market_cap_data: Optional[dict]
    """시가총액 및 거래 데이터 (시가총액, 거래량, 거래대금, 상장주식수)"""

    investor_trading_data: Optional[dict]
    """투자주체별 매매 동향 (외국인, 기관, 개인)"""

    news_data: Optional[List[dict]]
    """뉴스 데이터 (네이버 뉴스 API)"""

    # 기술적 지표
    technical_indicators: Optional[dict]
    """기술적 지표 계산 결과 (RSI, MACD, Bollinger Bands 등)"""

    # 분석 결과
    technical_analysis: Optional[dict]
    """기술적 분석 결과 (Technical Analyst - 이평선, 지지/저항선, 기술적 지표 해석)"""

    trading_flow_analysis: Optional[dict]
    """거래 동향 분석 결과 (Trading Flow Analyst - 기관/외국인/개인 순매수 분석)"""

    bull_analysis: Optional[dict]
    """강세 분석 (LLM)"""

    bear_analysis: Optional[dict]
    """약세 분석 (LLM)"""

    macro_analysis: Optional[dict]
    """거시경제 분석 (BOK API + LLM)"""

    consensus: Optional[dict]
    """최종 합의 의견"""

    information_analysis: Optional[dict]
    """정보/뉴스 분석 결과"""

    # 메타데이터
    error: Optional[str]
    """에러 메시지"""
