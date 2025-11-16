"""
KIS (한국투자증권) API 도구 래핑

KIS 서비스의 주요 기능을 Supervisor가 직접 사용할 수 있도록 tool로 노출합니다.

주의: KIS-mcp 서버 도입 후 장기적으로 deprecated 예정
"""
import logging
from typing import Dict, Any

from langchain_core.tools import tool
from pydantic.v1 import BaseModel, Field

from src.services.kis_service import kis_service

logger = logging.getLogger(__name__)


# ==================== Input Schemas ====================

class StockPriceInput(BaseModel):
    """주식 현재가 조회 입력"""
    ticker: str = Field(
        description="6자리 종목 코드 (예: '005930'). 종목명이 주어진 경우 먼저 resolve_ticker를 사용하세요."
    )


class PlaceOrderInput(BaseModel):
    """매매 주문 실행 입력"""
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

@tool(args_schema=StockPriceInput)
async def get_current_price(ticker: str) -> Dict[str, Any]:
    """
    [언제] 사용자가 특정 종목의 **현재가만** 궁금할 때 사용합니다.
    [무엇] 실시간 주가 정보를 KIS API에서 조회합니다.
    [주의] 심층 분석(차트, 기술적 지표)이 필요하면 transfer_to_Quantitative_Analyst를 사용하세요.

    Returns:
        dict: {
            "price": 75000,           # 현재가
            "change": "+2.5%",        # 전일 대비 등락률
            "change_price": 1875,     # 전일 대비 등락가
            "volume": 1000000,        # 거래량
            "high": 76000,            # 고가
            "low": 74000,             # 저가
            "open": 74500             # 시가
        }

    예시:
    - 사용자: "삼성전자 현재가?" → resolve_ticker("삼성전자") → get_current_price("005930")
    """
    try:
        logger.info(f"📊 [KIS Tool] 현재가 조회: {ticker}")
        result = await kis_service.get_stock_price(ticker)
        return {
            "success": True,
            "ticker": ticker,
            "data": result
        }
    except Exception as e:
        logger.error(f"❌ [KIS Tool] 현재가 조회 실패: {ticker}, 에러: {e}")
        return {
            "success": False,
            "ticker": ticker,
            "error": str(e)
        }


@tool
async def get_account_balance() -> Dict[str, Any]:
    """
    [언제] 사용자가 계좌 잔고나 보유 현금을 확인하고 싶을 때 사용합니다.
    [무엇] 현재 계좌의 예수금, 총 평가액, 평가 손익 등을 조회합니다.
    [참고] 보유 종목 목록이 필요하면 get_portfolio_positions를 사용하세요.

    Returns:
        dict: {
            "deposit": 5000000,           # 예수금 (사용 가능 현금)
            "total_evaluation": 15000000,  # 총 평가액 (예수금 + 주식 평가액)
            "evaluation_profit": 2000000,  # 평가 손익
            "profit_rate": 15.38          # 수익률 (%)
        }

    예시:
    - 사용자: "내 계좌 잔고 얼마야?" → get_account_balance()
    """
    try:
        logger.info(f"💰 [KIS Tool] 계좌 잔고 조회")
        result = await kis_service.get_account_balance()
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"❌ [KIS Tool] 계좌 잔고 조회 실패: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool
async def get_portfolio_positions() -> Dict[str, Any]:
    """
    [언제] 사용자가 보유 종목 목록과 비중을 확인하고 싶을 때 사용합니다.
    [무엇] 현재 보유 중인 모든 종목의 수량, 평가액, 비중, 손익을 조회합니다.
    [필수] calculate_portfolio_risk나 execute_trade 호출 전에 먼저 사용하세요.

    Returns:
        dict: {
            "positions": [
                {
                    "ticker": "005930",
                    "name": "삼성전자",
                    "quantity": 10,
                    "avg_price": 70000,
                    "current_price": 75000,
                    "evaluation": 750000,
                    "profit": 50000,
                    "profit_rate": 7.14,
                    "weight": 0.30  # 포트폴리오 내 비중 (30%)
                },
                ...
            ],
            "total_evaluation": 2500000,
            "total_profit": 200000
        }

    예시:
    - 사용자: "내가 지금 뭐 갖고 있어?" → get_portfolio_positions()
    - 매매 전: get_portfolio_positions() → calculate_portfolio_risk() → execute_trade()
    """
    try:
        logger.info(f"📋 [KIS Tool] 보유 종목 조회")

        # KIS API로 계좌 정보 조회 (정규화된 구조)
        balance_data = await kis_service.get_account_balance()

        raw_positions = balance_data.get("stocks") or []

        # ↔️ 구버전 호환: 혹시 normalized 되지 않은 응답(output1)일 경우 처리
        if not raw_positions and "output1" in balance_data:
            raw_positions = balance_data["output1"]

        positions = []
        for item in raw_positions:
            ticker = item.get("stock_code") or item.get("pdno")
            if not ticker:
                continue

            avg_price = item.get("avg_price", item.get("pchs_avg_pric", 0))
            current_price = item.get("current_price", item.get("prpr", 0))
            evaluation = item.get("eval_amount", item.get("evlu_amt", 0))
            profit = item.get("profit_loss", item.get("evlu_pfls_amt", 0))
            profit_rate = item.get("profit_rate", item.get("evlu_pfls_rt", 0))

            positions.append({
                "ticker": ticker,
                "name": item.get("stock_name") or item.get("prdt_name"),
                "quantity": int(item.get("quantity", item.get("hldg_qty", 0)) or 0),
                "avg_price": float(avg_price or 0),
                "current_price": float(current_price or 0),
                "evaluation": float(evaluation or 0),
                "profit": float(profit or 0),
                "profit_rate": float(profit_rate or 0),
            })

        total_evaluation = sum(p["evaluation"] for p in positions)
        total_profit = sum(p["profit"] for p in positions)

        for position in positions:
            position["weight"] = position["evaluation"] / total_evaluation if total_evaluation > 0 else 0

        return {
            "success": True,
            "data": {
                "positions": positions,
                "total_evaluation": total_evaluation,
                "total_profit": total_profit,
                "cash_balance": balance_data.get("cash_balance"),
                "total_assets": balance_data.get("total_assets"),
            }
        }
    except Exception as e:
        logger.error(f"❌ [KIS Tool] 보유 종목 조회 실패: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool(args_schema=PlaceOrderInput)
async def execute_trade(
    ticker: str,
    action: str,
    quantity: int,
    price: int = 0
) -> Dict[str, Any]:
    """
    [언제] 사용자가 매매 주문 실행을 **명시적으로 승인**한 후에만 사용합니다.
    [무엇] KIS API를 통해 실제 매수/매도 주문을 실행합니다.
    [필수] 이 tool을 호출하기 전에 반드시:
        1. get_portfolio_positions() 호출
        2. calculate_portfolio_risk() 호출
        3. 리스크 변화를 사용자에게 명시적 보고
        4. 사용자의 "승인" 또는 "실행" 응답 대기

    ⚠️ 주의: 이 tool은 실제 돈이 오가는 거래를 실행합니다!

    Args:
        action: 'buy' (매수) 또는 'sell' (매도)
        price: 0이면 시장가, 양수면 지정가 주문

    Returns:
        dict: {
            "order_id": "20240112-00001",
            "status": "submitted",
            "ticker": "005930",
            "action": "buy",
            "quantity": 10,
            "price": 75000,
            "estimated_amount": 750000
        }

    예시:
    사용자: "삼성전자 10주 매수해줘"
    → get_portfolio_positions()
    → calculate_portfolio_risk(portfolio, proposed_trade)
    → [사용자에게 리스크 보고]
    → 사용자: "승인"
    → execute_trade(ticker="005930", action="buy", quantity=10)
    """
    try:
        logger.info(f"🔥 [KIS Tool] 매매 주문 실행: {action} {ticker} x{quantity}")

        # KIS API로 주문 실행
        result = await kis_service.place_order(
            stock_code=ticker,
            order_type=action,
            quantity=quantity,
            price=price
        )

        return {
            "success": True,
            "ticker": ticker,
            "action": action,
            "quantity": quantity,
            "price": price,
            "data": result
        }
    except Exception as e:
        logger.error(f"❌ [KIS Tool] 매매 주문 실행 실패: {ticker}, 에러: {e}")
        return {
            "success": False,
            "ticker": ticker,
            "action": action,
            "quantity": quantity,
            "error": str(e)
        }


# ==================== Tool 목록 ====================

def get_kis_tools():
    """KIS 도구 목록 반환"""
    return [
        get_current_price,
        get_account_balance,
        get_portfolio_positions,
        execute_trade,
    ]
