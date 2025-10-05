"""
Risk Agent 서브그래프

순차 실행:
1. collect_portfolio_data → 포트폴리오 데이터 수집
2. concentration_check → 집중도 리스크 체크
3. market_risk → 시장 리스크 분석
4. final_assessment → 최종 평가
"""
from langgraph.graph import StateGraph, END
from src.agents.risk.state import RiskState
from src.agents.risk.nodes import (
    collect_portfolio_data_node,
    concentration_check_node,
    market_risk_node,
    final_assessment_node,
)


def build_risk_subgraph():
    """
    Risk Agent 서브그래프 빌드

    Returns:
        CompiledStateGraph
    """
    workflow = StateGraph(RiskState)

    # 노드 추가
    workflow.add_node("collect_data", collect_portfolio_data_node)
    workflow.add_node("concentration_check", concentration_check_node)
    workflow.add_node("market_risk", market_risk_node)
    workflow.add_node("final_assessment", final_assessment_node)

    # 순차 실행 플로우
    workflow.set_entry_point("collect_data")
    workflow.add_edge("collect_data", "concentration_check")
    workflow.add_edge("concentration_check", "market_risk")
    workflow.add_edge("market_risk", "final_assessment")
    workflow.add_edge("final_assessment", END)

    return workflow.compile(name="risk_agent")


# 서브그래프 인스턴스 export
risk_subgraph = build_risk_subgraph()
