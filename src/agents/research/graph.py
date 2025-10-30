"""
Research Agent 서브그래프 (Deep Agent 플로우)
"""
import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from .state import ResearchState
from .nodes import (
    planner_node,
    task_router_node,
    data_worker_node,
    macro_worker_node,
    bull_worker_node,
    bear_worker_node,
    insight_worker_node,
    technical_analyst_worker_node,
    trading_flow_analyst_worker_node,
    information_analyst_worker_node,
    synthesis_node,
)

logger = logging.getLogger(__name__)


def _route_task(
    state: ResearchState,
) -> Literal["data", "macro", "bull", "bear", "insight", "technical", "trading_flow", "information", "done"]:
    task = state.get("current_task")
    if not task:
        return "done"
    worker = str(task.get("worker", "")).lower()
    if worker not in {"data", "macro", "bull", "bear", "insight", "technical", "trading_flow", "information"}:
        return "insight"
    return worker  # type: ignore[return-value]


def build_research_subgraph():
    """
    Research Agent 서브그래프 생성

    Flow:
    planner → task_router → (worker loop) → synthesis → END

    Workers (PRISM-INSIGHT 패턴 적용):
    - data_worker: 원시 데이터 수집
    - technical_analyst: 기술적 분석 (주가, 거래량, 지표)
    - trading_flow_analyst: 거래 동향 분석 (기관/외국인/개인)
    - information_analyst: 정보 분석 (뉴스, 센티먼트)
    - macro_worker: 거시경제 분석
    - bull_worker: 강세 시나리오
    - bear_worker: 약세 시나리오
    - insight_worker: 인사이트 정리
    """
    workflow = StateGraph(ResearchState)

    # 노드 추가
    workflow.add_node("planner", planner_node)
    workflow.add_node("task_router", task_router_node)
    workflow.add_node("data_worker", data_worker_node)
    workflow.add_node("technical_analyst", technical_analyst_worker_node)
    workflow.add_node("trading_flow_analyst", trading_flow_analyst_worker_node)
    workflow.add_node("information_analyst", information_analyst_worker_node)
    workflow.add_node("macro_worker", macro_worker_node)
    workflow.add_node("bull_worker", bull_worker_node)
    workflow.add_node("bear_worker", bear_worker_node)
    workflow.add_node("insight_worker", insight_worker_node)
    workflow.add_node("synthesis", synthesis_node)

    # 시작점
    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "task_router")

    # 조건부 라우팅
    workflow.add_conditional_edges(
        "task_router",
        _route_task,
        {
            "data": "data_worker",
            "technical": "technical_analyst",
            "trading_flow": "trading_flow_analyst",
            "information": "information_analyst",
            "macro": "macro_worker",
            "bull": "bull_worker",
            "bear": "bear_worker",
            "insight": "insight_worker",
            "done": "synthesis",
        },
    )

    # 모든 워커는 완료 후 task_router로 돌아감
    for worker in (
        "data_worker",
        "technical_analyst",
        "trading_flow_analyst",
        "information_analyst",
        "macro_worker",
        "bull_worker",
        "bear_worker",
        "insight_worker",
    ):
        workflow.add_edge(worker, "task_router")

    # 종료
    workflow.add_edge("synthesis", END)

    app = workflow.compile(name="research_agent")

    logger.info("✅ [Research] 서브그래프 빌드 완료 (Deep Agent + PRISM-INSIGHT 패턴)")

    return app


research_subgraph = build_research_subgraph()
