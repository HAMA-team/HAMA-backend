"""
Trading Agent 서브그래프

매매 실행을 위한 LangGraph 서브그래프
"""
from langgraph.graph import StateGraph, END
from .state import TradingState
from .nodes import (
    prepare_trade_node,
    approval_trade_node,
    execute_trade_node
)
import logging

logger = logging.getLogger(__name__)


def build_trading_subgraph():
    """
    Trading Agent 서브그래프 생성

    Flow:
    prepare_trade → approval_trade → execute_trade → END

    HITL:
    - approval_trade 노드에서 interrupt 발생 (automation_level >= 2)
    """
    workflow = StateGraph(TradingState)

    # 노드 추가
    workflow.add_node("prepare_trade", prepare_trade_node)
    workflow.add_node("approval_trade", approval_trade_node)
    workflow.add_node("execute_trade", execute_trade_node)

    # 엣지 정의
    workflow.set_entry_point("prepare_trade")

    # 순차 실행
    workflow.add_edge("prepare_trade", "approval_trade")
    workflow.add_edge("approval_trade", "execute_trade")

    # 종료
    workflow.add_edge("execute_trade", END)

    logger.info("✅ [Trading] 서브그래프 빌드 완료")

    return workflow
