"""
Strategy Agent 서브그래프

Langgraph 네이티브 구현 - ReAct 패턴
"""
from langgraph.graph import StateGraph, END
from .state import StrategyState
from .nodes import (
    query_intent_classifier_node,
    planner_node,
    task_router_node,
    market_analysis_node,
    sector_rotation_node,
    asset_allocation_node,
    buy_specialist_node,
    sell_specialist_node,
    risk_reward_specialist_node,
    blueprint_creation_node,
)
import logging

logger = logging.getLogger(__name__)


def route_to_specialist(state: StrategyState) -> str:
    """
    Task Router에서 다음 노드 결정

    current_task.specialist에 따라 적절한 specialist로 라우팅
    pending_tasks가 비었으면 synthesis로 이동
    """
    current_task = state.get("current_task")

    if current_task is None:
        # 모든 작업 완료, synthesis로 이동
        logger.info("🔀 [Strategy/Router] 모든 작업 완료, synthesis로 이동")
        return "blueprint_creation"

    specialist = current_task.get("specialist", "")

    logger.info("🔀 [Strategy/Router] 다음 specialist: %s", specialist)

    # specialist 매핑
    specialist_map = {
        "market_specialist": "market_analysis",
        "sector_specialist": "sector_rotation",
        "asset_specialist": "asset_allocation",
        "buy_specialist": "buy_specialist",
        "sell_specialist": "sell_specialist",
        "risk_reward_specialist": "risk_reward_specialist",
    }

    return specialist_map.get(specialist, "blueprint_creation")


def build_strategy_subgraph():
    """
    Strategy Agent 서브그래프 생성 (ReAct 패턴)

    Flow:
    START → query_intent_classifier → planner → task_router
          ↓
    task_router ⇄ specialists (동적 선택)
          ↓
    blueprint_creation → END

    Specialists:
    - market_specialist (market_analysis_node)
    - sector_specialist (sector_rotation_node)
    - asset_specialist (asset_allocation_node)
    - buy_specialist (buy_specialist_node)
    - sell_specialist (sell_specialist_node)
    - risk_reward_specialist (risk_reward_specialist_node)
    """
    workflow = StateGraph(StrategyState)

    # ReAct 패턴 노드 추가
    workflow.add_node("query_intent_classifier", query_intent_classifier_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("task_router", task_router_node)

    # Specialist 노드 추가
    workflow.add_node("market_analysis", market_analysis_node)
    workflow.add_node("sector_rotation", sector_rotation_node)
    workflow.add_node("asset_allocation", asset_allocation_node)
    workflow.add_node("buy_specialist", buy_specialist_node)
    workflow.add_node("sell_specialist", sell_specialist_node)
    workflow.add_node("risk_reward_specialist", risk_reward_specialist_node)

    # Synthesis 노드
    workflow.add_node("blueprint_creation", blueprint_creation_node)

    # ReAct Flow 엣지 정의
    workflow.set_entry_point("query_intent_classifier")
    workflow.add_edge("query_intent_classifier", "planner")
    workflow.add_edge("planner", "task_router")

    # Task Router → Specialist (조건부 라우팅)
    workflow.add_conditional_edges(
        "task_router",
        route_to_specialist,
        {
            "market_analysis": "market_analysis",
            "sector_rotation": "sector_rotation",
            "asset_allocation": "asset_allocation",
            "buy_specialist": "buy_specialist",
            "sell_specialist": "sell_specialist",
            "risk_reward_specialist": "risk_reward_specialist",
            "blueprint_creation": "blueprint_creation",
        },
    )

    # Specialist → Task Router (다음 작업 선택)
    workflow.add_edge("market_analysis", "task_router")
    workflow.add_edge("sector_rotation", "task_router")
    workflow.add_edge("asset_allocation", "task_router")
    workflow.add_edge("buy_specialist", "task_router")
    workflow.add_edge("sell_specialist", "task_router")
    workflow.add_edge("risk_reward_specialist", "task_router")

    # Synthesis → END
    workflow.add_edge("blueprint_creation", END)

    # 컴파일
    app = workflow.compile(name="strategy_agent")

    logger.info("✅ [Strategy] ReAct 패턴 서브그래프 빌드 완료")

    return app


# Global compiled subgraph
strategy_subgraph = build_strategy_subgraph()
