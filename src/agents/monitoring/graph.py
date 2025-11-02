"""
Monitoring Agent 서브그래프

포트폴리오 종목의 뉴스를 모니터링하고 중요한 뉴스에 대해 알림을 생성합니다.
"""
from langgraph.graph import StateGraph, END

from .state import MonitoringState
from .nodes import (
    fetch_portfolio_node,
    collect_news_node,
    analyze_news_node,
    generate_alerts_node,
    synthesis_node,
)


def build_monitoring_subgraph():
    """
    Monitoring Agent 서브그래프 생성

    Flow:
    1. fetch_portfolio: 포트폴리오 조회
    2. collect_news: 뉴스 수집
    3. analyze_news: 뉴스 분석 (LLM)
    4. generate_alerts: 알림 생성
    5. synthesis: 최종 메시지 작성
    """
    graph = StateGraph(MonitoringState)

    # 노드 추가
    graph.add_node("fetch_portfolio", fetch_portfolio_node)
    graph.add_node("collect_news", collect_news_node)
    graph.add_node("analyze_news", analyze_news_node)
    graph.add_node("generate_alerts", generate_alerts_node)
    graph.add_node("synthesis", synthesis_node)

    # 엔트리 포인트 설정
    graph.set_entry_point("fetch_portfolio")

    # 엣지 연결 (순차 실행)
    graph.add_edge("fetch_portfolio", "collect_news")
    graph.add_edge("collect_news", "analyze_news")
    graph.add_edge("analyze_news", "generate_alerts")
    graph.add_edge("generate_alerts", "synthesis")
    graph.add_edge("synthesis", END)

    return graph.compile(name="monitoring_agent")


monitoring_subgraph = build_monitoring_subgraph()

__all__ = ["monitoring_subgraph"]
