"""Monitoring Agent State 정의"""
from typing import TypedDict, Optional, List, Annotated, Dict, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class MonitoringState(TypedDict, total=False):
    """
    Monitoring Agent 서브그래프 State

    Flow:
    1. fetch_portfolio: 사용자 포트폴리오 조회
    2. collect_news: 종목별 뉴스 수집
    3. analyze_news: LLM으로 뉴스 분석 (중요도, 긍정/부정 판단)
    4. generate_alerts: 중요 뉴스 알림 생성
    5. synthesis: 최종 메시지 생성

    Note: total=False로 설정하여 partial update 지원 (Langgraph 패턴)
    """

    # LangGraph 메시지 스택
    messages: Annotated[List[BaseMessage], add_messages]

    # 입력
    user_id: Optional[str]
    """사용자 ID (UUID)"""

    query: Optional[str]
    """사용자 질문 (선택적)"""

    request_id: Optional[str]
    """요청 ID (Supervisor 호출 시)"""

    # 포트폴리오 데이터
    portfolio_stocks: Optional[List[Dict[str, Any]]]
    """
    사용자 포트폴리오 종목 리스트
    [{"stock_code": "005930", "stock_name": "삼성전자", "quantity": 10, ...}, ...]
    """

    # 뉴스 데이터
    news_items: Optional[List[Dict[str, Any]]]
    """
    수집된 뉴스 리스트
    [{"stock_code": "005930", "title": "...", "url": "...", "published_at": "..."}, ...]
    """

    analyzed_news: Optional[List[Dict[str, Any]]]
    """
    분석된 뉴스 리스트
    [{"stock_code": "005930", "title": "...", "sentiment": "positive", "importance": "high", "summary": "..."}, ...]
    """

    # 알림
    alerts: Optional[List[Dict[str, Any]]]
    """
    생성된 알림 리스트
    [{"type": "news", "stock_code": "005930", "title": "...", "message": "...", "priority": "high"}, ...]
    """

    # 설정
    max_news_per_stock: Optional[int]
    """종목당 최대 뉴스 수집 개수 (기본값: 10)"""

    importance_threshold: Optional[str]
    """알림 생성 임계값 ("low" | "medium" | "high")"""

    # 메타데이터
    error: Optional[str]
    """에러 메시지"""
