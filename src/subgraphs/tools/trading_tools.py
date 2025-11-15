"""
Trading Tools - HITL 패턴 기반 매매 도구

기존 execute_trade tool과 달리, HITL (Human-in-the-Loop) 패턴을 사용하여
사용자 승인 후 매매를 실행합니다.
"""
import logging
from typing import Dict, Any, Annotated

from langchain_core.tools import tool, InjectedState
from pydantic.v1 import BaseModel, Field
from langgraph_sdk.schema import Command

logger = logging.getLogger(__name__)


# ==================== Input Schemas ====================

class RequestTradeInput(BaseModel):
    """매매 요청 입력"""
    ticker: str = Field(
        description="6자리 종목 코드 (예: '005930')"
    )
    action: str = Field(
        description="매매 구분: 'buy' (매수) 또는 'sell' (매도)"
    )
    quantity: int = Field(
        description="주문 수량 (1 이상)"
    )
    price: int = Field(
        default=0,
        description="주문 가격 (0이면 시장가, 양수면 지정가)"
    )


# ==================== Tools ====================

@tool(args_schema=RequestTradeInput, return_direct=True)
async def request_trade(
    ticker: str,
    action: str,
    quantity: int,
    price: int = 0,
    state: Annotated[Dict, InjectedState] = None
) -> Command:
    """
    [언제] 사용자가 매매를 요청할 때 사용합니다. (HITL 패턴)
    [무엇] 매매 정보를 state에 저장하고, 사용자 승인을 기다립니다.
    [필수] 이 tool을 호출하기 전에 반드시:
        1. resolve_ticker로 종목 코드 확인
        2. get_portfolio_positions()로 현재 포트폴리오 조회
        3. calculate_portfolio_risk()로 리스크 변화 계산
        4. 리스크 변화를 사용자에게 명시적 보고

    이 tool을 호출하면:
    - State에 매매 정보가 저장됩니다
    - trade_planner 노드로 자동 이동합니다
    - 포트폴리오 시뮬레이션 후 HITL Interrupt가 발생합니다
    - 승인 후 자동으로 매매가 실행됩니다

    ⚠️ 주의:
    - 기존 execute_trade tool과 달리 사용자 승인 단계가 추가됩니다
    - automation_level=1 (Pilot)인 경우만 자동 승인됩니다

    Args:
        ticker: 종목 코드 (6자리, 예: '005930')
        action: 'buy' (매수) 또는 'sell' (매도)
        quantity: 주문 수량
        price: 주문 가격 (0=시장가, 양수=지정가)

    Returns:
        Command: trade_planner 노드로 이동하는 명령

    예시:
    사용자: "삼성전자 10주 매수해줘"
    → resolve_ticker("삼성전자") → ticker="005930"
    → get_portfolio_positions()
    → calculate_portfolio_risk(portfolio, proposed_trade)
    → [사용자에게 리스크 보고]
    → request_trade(ticker="005930", action="buy", quantity=10, price=75000)
    → [자동으로 trade_planner → portfolio_simulator → trade_hitl로 이동]
    → [HITL Interrupt 발생 - 승인 대기]
    → 사용자 승인 후 자동 실행
    """
    logger.info(f"🛒 [Trading Tool] 매매 요청: {action} {ticker} x{quantity} @ {price}")

    # 시장가 처리: price=0이면 현재가 조회 필요
    order_type = "market" if price == 0 else "limit"

    # State 업데이트 + trade_planner 노드로 이동
    return Command(
        update={
            "stock_code": ticker,
            "trade_action": action,
            "trade_quantity": quantity,
            "trade_price": price if price > 0 else 0,  # 시장가는 0으로 저장
            "trade_order_type": order_type,
            "trade_prepared": False,
            "trade_approved": False,
            "trade_executed": False,
        },
        goto="trade_planner"
    )


# ==================== Tool 목록 ====================

def get_trading_tools():
    """Trading 도구 목록 반환"""
    return [
        request_trade,
    ]
