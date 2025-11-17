"""
Trading Tools - Trading SubGraph 전용 HITL 도구

request_trade tool을 통해 매매 정보를 수집한 뒤
transfer_to_trading_agent() 호출로 Trading SubGraph를 기동합니다.
"""
import logging

from langchain_core.tools import tool
from pydantic.v1 import BaseModel, Field

logger = logging.getLogger(__name__)


class RequestTradeInput(BaseModel):
    """매매 요청 입력"""

    ticker: str = Field(description="6자리 종목 코드 (예: '005930')")
    action: str = Field(description="매매 구분: 'buy' (매수) 또는 'sell' (매도)")
    quantity: int = Field(description="주문 수량 (1 이상)")
    price: int = Field(default=0, description="주문 가격 (0이면 시장가, 양수면 지정가)")


@tool(args_schema=RequestTradeInput)
async def request_trade(
    ticker: str,
    action: str,
    quantity: int,
    price: int = 0,
) -> str:
    """
    매매 요청 정보를 state에 저장하는 HITL tool.

    필수 선행 단계:
        1. resolve_ticker로 종목 코드 확인
        2. get_portfolio_positions() 호출
        3. calculate_portfolio_risk()로 리스크 변화 계산 및 보고

    ⚠️ 중요: request_trade 호출 후 **반드시 transfer_to_trading_agent를 호출**해야
    Trading SubGraph가 실행됩니다.
    """
    logger.info("🛒 [Trading Tool] 매매 정보 준비: %s %s x%d @ %d", action, ticker, quantity, price)

    order_type = "market" if price == 0 else "limit"

    return f"""매매 정보가 준비되었습니다:
- 종목 코드: {ticker}
- 매매 구분: {action}
- 수량: {quantity}주
- 가격: {price if price > 0 else '시장가'}원
- 주문 유형: {order_type}

다음으로 transfer_to_trading_agent()를 호출하여 매매를 진행하세요."""


def get_trading_tools():
    """Trading 도구 목록 반환"""
    return [request_trade]


__all__ = ["get_trading_tools", "request_trade"]
