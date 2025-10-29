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
    synthesis_node,
)

logger = logging.getLogger(__name__)


def _route_task(state: ResearchState) -> Literal["data", "macro", "bull", "bear", "insight", "done"]:
    task = state.get("current_task")
    if not task:
        return "done"
    worker = str(task.get("worker", "")).lower()
    if worker not in {"data", "macro", "bull", "bear", "insight"}:
        return "insight"
    return worker  # type: ignore[return-value]


def build_research_subgraph():
    """
    Research Agent 서브그래프 생성

    Flow:
    planner → task_router → (worker loop) → synthesis → END
    """
    workflow = StateGraph(ResearchState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("task_router", task_router_node)
    workflow.add_node("data_worker", data_worker_node)
    workflow.add_node("macro_worker", macro_worker_node)
    workflow.add_node("bull_worker", bull_worker_node)
    workflow.add_node("bear_worker", bear_worker_node)
    workflow.add_node("insight_worker", insight_worker_node)
    workflow.add_node("synthesis", synthesis_node)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "task_router")

    workflow.add_conditional_edges(
        "task_router",
        _route_task,
        {
            "data": "data_worker",
            "macro": "macro_worker",
            "bull": "bull_worker",
            "bear": "bear_worker",
            "insight": "insight_worker",
            "done": "synthesis",
        },
    )

    for worker in ("data_worker", "macro_worker", "bull_worker", "bear_worker", "insight_worker"):
        workflow.add_edge(worker, "task_router")

    workflow.add_edge("synthesis", END)

    app = workflow.compile(name="research_agent")

    logger.info("✅ [Research] 서브그래프 빌드 완료 (Deep Agent 플로우)")

    return app


research_subgraph = build_research_subgraph()
