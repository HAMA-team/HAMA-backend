"""
Trading Agent 서브그래프

매매 실행을 위한 Langgraph 서브그래프 (단순화된 3-노드 구조)
"""
from langgraph.graph import StateGraph, END
import logging

from .state import TradingState
from .nodes import (
    prepare_trade_node,
    approval_trade_node,
    execute_trade_node,
)

logger = logging.getLogger(__name__)


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
    Trading Agent 서브그래프 생성 (단순화된 구조)

    Flow:
    START → prepare_trade → approval_trade → execute_trade → END

    Nodes:
    - prepare_trade: LLM으로 query 분석 + 주문 생성
    - approval_trade: HITL 승인 대기 (interrupt)
    - execute_trade: 실제 주문 실행

    HITL:
    - automation_level 1 (Pilot): 자동 승인
    - automation_level 2+ (Copilot/Advisor): 사용자 승인 필요
    """
    workflow = StateGraph(TradingState)

    # 3개 노드만 추가
    workflow.add_node("prepare_trade", prepare_trade_node)
    workflow.add_node("approval_trade", approval_trade_node)
    workflow.add_node("execute_trade", execute_trade_node)

    # 단순 선형 플로우
    workflow.set_entry_point("prepare_trade")
    workflow.add_edge("prepare_trade", "approval_trade")

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

    logger.info("✅ [Trading] 단순화된 서브그래프 빌드 완료 (3 노드)")

    return workflow
