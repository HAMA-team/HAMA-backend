"""
Trading Agent 서브그래프

매매 실행을 위한 Langgraph 서브그래프 (ReAct 패턴)
"""
from langgraph.graph import StateGraph, END
import logging

from .state import TradingState
from .nodes import (
    query_intent_classifier_node,
    planner_node,
    task_router_node,
    prepare_trade_node,
    buy_specialist_node,
    sell_specialist_node,
    risk_reward_calculator_node,
    approval_trade_node,
    execute_trade_node,
)

logger = logging.getLogger(__name__)


def route_to_specialist(state: TradingState) -> str:
    """
    Task Router에서 다음 노드 결정

    current_task.specialist에 따라 적절한 specialist로 라우팅
    """
    current_task = state.get("current_task")

    if current_task is None:
        # 모든 작업 완료, END로 이동
        logger.info("🔀 [Trading/Router] 모든 작업 완료, END로 이동")
        return "end"

    specialist = current_task.get("specialist", "")

    logger.info("🔀 [Trading/Router] 다음 specialist: %s", specialist)

    # specialist 매핑
    specialist_map = {
        "prepare_trade": "prepare_trade",
        "buy_specialist": "buy_specialist",
        "sell_specialist": "sell_specialist",
        "risk_reward_specialist": "risk_reward_calculator",
        "approval_trade": "approval_trade",
        "execute_trade": "execute_trade",
    }

    return specialist_map.get(specialist, "end")


def should_execute_trade(state: TradingState) -> str:
    """
    Approval 이후 실행 여부 결정

    trade_approved=True면 execute로, 아니면 END
    """
    if state.get("skip_hitl"):
        return "execute"
    if state.get("trade_approved"):
        return "execute"
    return "end"


def build_trading_subgraph():
    """
    Trading Agent 서브그래프 생성 (ReAct 패턴)

    Flow:
    START → query_intent_classifier → planner → task_router
          ↓
    task_router ⇄ specialists (동적 선택)
          ↓
    approval_trade → execute_trade → END

    Specialists:
    - prepare_trade: 거래 준비 (정보 추출)
    - buy_specialist: 매수 점수 산정 (1-10점)
    - sell_specialist: 매도 결정 로직
    - risk_reward_specialist (risk_reward_calculator_node): 손절가/목표가 계산

    HITL:
    - approval_trade 노드에서 interrupt 발생 (automation_level >= 2)
    """
    workflow = StateGraph(TradingState)

    # ReAct 패턴 노드 추가
    workflow.add_node("query_intent_classifier", query_intent_classifier_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("task_router", task_router_node)

    # Specialist 노드 추가
    workflow.add_node("prepare_trade", prepare_trade_node)
    workflow.add_node("buy_specialist", buy_specialist_node)
    workflow.add_node("sell_specialist", sell_specialist_node)
    workflow.add_node("risk_reward_calculator", risk_reward_calculator_node)
    workflow.add_node("approval_trade", approval_trade_node)
    workflow.add_node("execute_trade", execute_trade_node)

    # ReAct Flow 엣지 정의
    workflow.set_entry_point("query_intent_classifier")
    workflow.add_edge("query_intent_classifier", "planner")
    workflow.add_edge("planner", "task_router")

    # Task Router → Specialist (조건부 라우팅)
    workflow.add_conditional_edges(
        "task_router",
        route_to_specialist,
        {
            "prepare_trade": "prepare_trade",
            "buy_specialist": "buy_specialist",
            "sell_specialist": "sell_specialist",
            "risk_reward_calculator": "risk_reward_calculator",
            "approval_trade": "approval_trade",
            "execute_trade": "execute_trade",
            "end": END,
        },
    )

    # Specialist → Task Router (다음 작업 선택)
    workflow.add_edge("prepare_trade", "task_router")
    workflow.add_edge("buy_specialist", "task_router")
    workflow.add_edge("sell_specialist", "task_router")
    workflow.add_edge("risk_reward_calculator", "task_router")

    # Approval 이후 조건부 분기
    workflow.add_conditional_edges(
        "approval_trade",
        should_execute_trade,
        {
            "execute": "execute_trade",
            "end": END,
        },
    )

    # Execute → END
    workflow.add_edge("execute_trade", END)

    logger.info("✅ [Trading] ReAct 패턴 서브그래프 빌드 완료")

    return workflow
