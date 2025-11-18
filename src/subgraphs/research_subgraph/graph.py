"""
Research Agent 서브그래프 (Deep Agent 플로우)
"""
import logging
from typing import Literal

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from .state import ResearchState
from .nodes import (
    planner_node,
    data_worker_node,
    macro_worker_node,
    bull_worker_node,
    bear_worker_node,
    technical_analyst_worker_node,
    trading_flow_analyst_worker_node,
    information_worker_node,
    synthesis_node,
)

logger = logging.getLogger(__name__)


def _route_workers(state: ResearchState) -> list[Send]:
    """
    planner가 생성한 pending_tasks를 기반으로 병렬 실행할 worker 목록 반환

    Returns:
        Send 객체 리스트 (LangGraph 병렬 실행용)
    """
    pending_tasks = state.get("pending_tasks") or []

    # Worker 이름 매핑
    worker_node_map = {
        "data": "data_worker",
        "technical": "technical_analyst",
        "trading_flow": "trading_flow_analyst",
        "macro": "macro_worker",
        "bull": "bull_worker",
        "bear": "bear_worker",
        "information": "information_analyst",
    }

    # pending_tasks에서 worker 추출 (중복 제거)
    workers_to_run = []
    for task in pending_tasks:
        worker = str(task.get("worker", "")).lower()
        if worker in worker_node_map:
            node_name = worker_node_map[worker]
            if node_name not in [w.node for w in workers_to_run]:
                # Send 객체 생성하여 각 worker에 상태 전달
                workers_to_run.append(Send(node_name, state))

    logger.info(f"🚀 [Research] 병렬 실행할 worker: {[w.node for w in workers_to_run]}")

    return workers_to_run


def build_research_subgraph():
    """
    Research Agent 서브그래프 생성 (HITL 패턴)

    Flow:
    planner (INTERRUPT for user approval) → (workers 병렬 실행) → synthesis → END

    HITL (Human-in-the-Loop) Pattern:
    - planner: 사용자 선호도 기반 분석 계획 수립 및 승인 요청 (INTERRUPT)
      - UI에서 Depth/Scope/Perspectives 선택
      - intervention_required=False이면 자동 승인 (매매만 HITL)
    - workers: 사용자가 선택한 worker들이 병렬로 실행 (데이터 수집 및 분석)
    - synthesis: 모든 worker 결과를 통합하여 최종 의견 생성

    Workers (병렬 실행):
    - data_worker: 원시 데이터 수집 (재무제표, 기업 정보)
    - technical_analyst: 기술적 분석 (주가, 거래량, 지표)
    - trading_flow_analyst: 거래 동향 분석 (기관/외국인/개인)
    - macro_worker: 거시경제 분석
    - bull_worker: 강세 시나리오
    - bear_worker: 약세 시나리오
    """
    workflow = StateGraph(ResearchState)

    # 노드 추가
    workflow.add_node("planner", planner_node)
    workflow.add_node("data_worker", data_worker_node)
    workflow.add_node("technical_analyst", technical_analyst_worker_node)
    workflow.add_node("trading_flow_analyst", trading_flow_analyst_worker_node)
    workflow.add_node("macro_worker", macro_worker_node)
    workflow.add_node("bull_worker", bull_worker_node)
    workflow.add_node("bear_worker", bear_worker_node)
    workflow.add_node("information_analyst", information_worker_node)
    workflow.add_node("synthesis", synthesis_node)

    # 시작점: planner에서 바로 시작 (HITL 패턴)
    workflow.set_entry_point("planner")

    # planner 이후 조건부 병렬 라우팅 (Send 객체를 사용하여 병렬 실행)
    workflow.add_conditional_edges(
        "planner",
        _route_workers,
    )

    # 모든 워커는 완료 후 synthesis로 직행
    for worker in (
        "data_worker",
        "technical_analyst",
        "trading_flow_analyst",
        "macro_worker",
        "bull_worker",
        "bear_worker",
        "information_analyst",
    ):
        workflow.add_edge(worker, "synthesis")

    # 종료
    workflow.add_edge("synthesis", END)

    app = workflow.compile(name="research_agent")

    logger.info("✅ [Research] 서브그래프 빌드 완료 (병렬 실행 구조)")

    return app


research_subgraph = build_research_subgraph()
