"""
Trading Agent 서브그래프 (PRISM-INSIGHT 패턴 적용)

매매 실행을 위한 Langgraph 서브그래프
"""
from langgraph.graph import StateGraph, END
from .state import TradingState
from .nodes import (
    prepare_trade_node,
    buy_specialist_node,
    sell_specialist_node,
    risk_reward_calculator_node,
    approval_trade_node,
    execute_trade_node,
)
import logging

logger = logging.getLogger(__name__)


def build_trading_subgraph():
    """
    Trading Agent 서브그래프 생성 (PRISM-INSIGHT 패턴)

    Flow:
    prepare_trade → [buy_specialist | sell_specialist] → risk_reward_calculator
    → approval_trade → execute_trade → END

    PRISM-INSIGHT 패턴:
    - buy_specialist: 매수 점수 산정 (1-10점), 매수 근거 생성
    - sell_specialist: 매도 결정 로직, 매도 근거 생성
    - risk_reward_calculator: 손절가/목표가 자동 계산

    HITL:
    - approval_trade 노드에서 interrupt 발생 (automation_level >= 2)
    """
    workflow = StateGraph(TradingState)

    # 노드 추가
    workflow.add_node("prepare_trade", prepare_trade_node)
    workflow.add_node("buy_specialist", buy_specialist_node)
    workflow.add_node("sell_specialist", sell_specialist_node)
    workflow.add_node("risk_reward_calculator", risk_reward_calculator_node)
    workflow.add_node("approval_trade", approval_trade_node)
    workflow.add_node("execute_trade", execute_trade_node)

    # 엣지 정의
    workflow.set_entry_point("prepare_trade")

    # 순차 실행:
    # Buy/Sell Specialist는 order_type에 따라 자동으로 skip됨
    workflow.add_edge("prepare_trade", "buy_specialist")
    workflow.add_edge("buy_specialist", "sell_specialist")
    workflow.add_edge("sell_specialist", "risk_reward_calculator")
    workflow.add_edge("risk_reward_calculator", "approval_trade")

    def should_execute_trade(state: TradingState) -> str:
        if state.get("skip_hitl"):
            return "execute_trade"
        if state.get("trade_approved"):
            return "execute_trade"
        return END

    workflow.add_conditional_edges(
        "approval_trade",
        should_execute_trade,
        {
            "execute_trade": "execute_trade",
            END: END,
        },
    )

    workflow.add_edge("execute_trade", END)

    logger.info("✅ [Trading] 서브그래프 빌드 완료 (PRISM-INSIGHT 패턴)")

    return workflow
