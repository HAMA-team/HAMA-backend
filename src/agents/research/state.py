"""Research Agent State 정의."""
from typing import TypedDict, Optional, List, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ResearchState(TypedDict, total=False):
    """
    Research Agent 서브그래프 State

    Flow:
    1. collect_data: 데이터 수집 (주가, 재무, 기업정보)
    2. bull_analysis + bear_analysis: 병렬 분석
    3. consensus: 최종 의견 통합

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

    # 데이터 수집 결과
    price_data: Optional[dict]
    """주가 데이터 (pykrx)"""

    financial_data: Optional[dict]
    """재무제표 데이터 (DART)"""

    company_data: Optional[dict]
    """기업 정보 (DART)"""

    market_index_data: Optional[dict]
    """시장 지수 데이터 (KOSPI, KOSDAQ)"""

    # 기술적 지표
    technical_indicators: Optional[dict]
    """기술적 지표 계산 결과 (RSI, MACD, Bollinger Bands 등)"""

    # 분석 결과
    technical_analysis: Optional[dict]
    """기술적 분석 결과 (LLM이 지표를 해석)"""

    bull_analysis: Optional[dict]
    """강세 분석 (LLM)"""

    bear_analysis: Optional[dict]
    """약세 분석 (LLM)"""

    consensus: Optional[dict]
    """최종 합의 의견"""

    # 메타데이터
    error: Optional[str]
    """에러 메시지"""
