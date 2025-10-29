"""
General Agent 서브그래프 (Deep Agent 플로우)
"""
import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from .state import GeneralState
from .nodes import (
    planner_node,
    task_router_node,
    search_worker_node,
    analysis_worker_node,
    insight_worker_node,
    synthesis_node,
)

logger = logging.getLogger(__name__)


def _route_task(state: GeneralState) -> Literal["search", "analysis", "insight", "done"]:
    task = state.get("current_task")
    if not task:
        return "done"
    worker = str(task.get("worker", "")).lower()
    if worker not in {"search", "analysis", "insight"}:
        return "insight"
    return worker  # type: ignore[return-value]


def build_general_subgraph():
    """
    General Agent 서브그래프 생성

    Flow:
    planner → task_router → (worker loop) → synthesis → END
    """
    workflow = StateGraph(GeneralState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("task_router", task_router_node)
    workflow.add_node("search_worker", search_worker_node)
    workflow.add_node("analysis_worker", analysis_worker_node)
    workflow.add_node("insight_worker", insight_worker_node)
    workflow.add_node("synthesis", synthesis_node)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "task_router")

    workflow.add_conditional_edges(
        "task_router",
        _route_task,
        {
            "search": "search_worker",
            "analysis": "analysis_worker",
            "insight": "insight_worker",
            "done": "synthesis",
        },
    )

    for worker in ("search_worker", "analysis_worker", "insight_worker"):
        workflow.add_edge(worker, "task_router")

    workflow.add_edge("synthesis", END)

    app = workflow.compile(name="general_agent")

    logger.info("✅ [General] 서브그래프 빌드 완료 (Deep Agent 플로우)")

    return app


general_subgraph = build_general_subgraph()
