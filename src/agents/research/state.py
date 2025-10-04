"""
Research Agent State 정의

LangGraph 서브그래프를 위한 State
"""
from typing import TypedDict, Optional


class ResearchState(TypedDict):
    """
    Research Agent 서브그래프 State

    Flow:
    1. collect_data: 데이터 수집 (주가, 재무, 기업정보)
    2. bull_analysis + bear_analysis: 병렬 분석
    3. consensus: 최종 의견 통합
    """

    # 입력
    stock_code: str
    """종목 코드"""

    request_id: str
    """요청 ID"""

    # 데이터 수집 결과
    price_data: Optional[dict]
    """주가 데이터 (FinanceDataReader)"""

    financial_data: Optional[dict]
    """재무제표 데이터 (DART)"""

    company_data: Optional[dict]
    """기업 정보 (DART)"""

    # 분석 결과
    bull_analysis: Optional[dict]
    """강세 분석 (LLM)"""

    bear_analysis: Optional[dict]
    """약세 분석 (LLM)"""

    consensus: Optional[dict]
    """최종 합의 의견"""

    # 메타데이터
    error: Optional[str]
    """에러 메시지"""
