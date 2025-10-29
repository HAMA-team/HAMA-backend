"""Trading Agent 노드 함수들 (실제 서비스 연동 버전)."""
from __future__ import annotations

import logging
from typing import Any, Dict

from langchain_core.messages import AIMessage
from langgraph_sdk.schema import Interrupt

from src.agents.trading.state import TradingState
from src.services import OrderNotFoundError, PortfolioNotFoundError, trading_service

logger = logging.getLogger(__name__)


async def prepare_trade_node(state: TradingState) -> dict:
    """1단계: 주문 생성 및 기본 정보 정리."""
    if state.get("trade_prepared"):
        logger.info("⏭️ [Trade] 이미 준비된 주문이 있어 재사용합니다")
        return {}

    stock_code = state.get("stock_code")
    quantity = state.get("quantity")
    messages = list(state.get("messages", []))

    if not stock_code or not quantity:
        error = "stock_code와 quantity가 필요합니다."
        logger.warning("⚠️ [Trade] %s", error)
        return {**state, "error": error, "messages": messages}

    order_type = (state.get("order_type") or "BUY").upper()
    try:
        order = await trading_service.create_pending_order(
            user_id=state.get("user_id"),
            portfolio_id=state.get("portfolio_id"),
            stock_code=stock_code,
            order_type=order_type,
            quantity=int(quantity),
            order_price=state.get("order_price"),
            order_price_type=state.get("order_price_type"),
            notes=state.get("order_note"),
        )
    except PortfolioNotFoundError as exc:
        logger.error("❌ [Trade] 포트폴리오가 존재하지 않습니다: %s", exc)
        return {**state, "error": str(exc), "messages": messages}
    except Exception as exc:  # pragma: no cover - 방어 로깅
        logger.exception("❌ [Trade] 주문 생성 실패: %s", exc)
        return {**state, "error": str(exc), "messages": messages}

    logger.info("✅ [Trade] 주문 생성 완료: %s", order["order_id"])

    return {
        "trade_prepared": True,
        "trade_order_id": order["order_id"],
        "trade_summary": order,
        "portfolio_id": order.get("portfolio_id") or state.get("portfolio_id"),
        "messages": messages,
    }


def approval_trade_node(state: TradingState) -> dict:
    """2단계: 사용자 승인 (interrupt)."""
    if state.get("trade_approved"):
        logger.info("⏭️ [Trade] 이미 승인된 주문입니다")
        return {}

    logger.info("🔔 [Trade] 사용자 승인을 요청합니다")

    summary = state.get("trade_summary") or {}
    interrupt_payload = {
        "type": "trade_approval",
        "order_id": state.get("trade_order_id", "UNKNOWN"),
        "query": state.get("query", ""),
        "stock_code": summary.get("stock_code") or state.get("stock_code"),
        "quantity": summary.get("order_quantity") or state.get("quantity"),
        "order_type": summary.get("order_type") or state.get("order_type"),
        "order_price": summary.get("order_price") or state.get("order_price"),
        "automation_level": state.get("automation_level", 2),
        "message": "매매 주문을 승인하시겠습니까?",
    }
    approval: Interrupt = {
        "id": f"trade-{interrupt_payload['order_id']}",
        "value": interrupt_payload,
    }

    logger.info("✅ [Trade] 승인 수락: %s", approval)

    messages = list(state.get("messages", []))
    return {"trade_approved": True, "messages": messages}


async def execute_trade_node(state: TradingState) -> dict:
    """3단계: 승인된 주문을 실제로 실행하고 결과를 반환."""
    if state.get("trade_executed"):
        logger.info("⏭️ [Trade] 이미 실행된 주문입니다")
        return {}

    if not state.get("trade_approved"):
        warning = "거래가 승인되지 않았습니다."
        logger.warning("⚠️ [Trade] %s", warning)
        return {"error": warning}

    order_id = state.get("trade_order_id")
    if not order_id:
        error = "주문 ID가 존재하지 않아 실행할 수 없습니다."
        logger.error("❌ [Trade] %s", error)
        return {"error": error}

    logger.info("💰 [Trade] 주문 실행 시작: %s", order_id)

    try:
        result = await trading_service.execute_order(
            order_id,
            execution_price=state.get("execution_price") or state.get("order_price"),
            automation_level=state.get("automation_level", 2),
        )
    except OrderNotFoundError as exc:
        logger.error("❌ [Trade] 주문을 찾을 수 없습니다: %s", exc)
        return {"error": str(exc)}
    except Exception as exc:  # pragma: no cover - 방어
        logger.exception("❌ [Trade] 주문 실행 실패: %s", exc)
        return {"error": str(exc)}

    if result.get("status") == "rejected":
        logger.warning("⚠️ [Trade] 주문이 거부되었습니다: %s", result.get("error"))
        return {"trade_result": result, "error": result.get("error")}

    messages = list(state.get("messages", []))
    summary = _format_trade_summary(result)
    messages.append(AIMessage(content=summary))

    # MasterState(GraphState)로 결과 전달
    return {
        "trade_executed": True,
        "trade_result": result,  # TradingState 내부용
        "portfolio_snapshot": result.get("portfolio_snapshot"),
        "agent_results": {  # MasterState 공유용
            "trading": result
        },
        "messages": messages,
    }


def _format_trade_summary(result: Dict[str, Any]) -> str:
    order_type = str(result.get("order_type", "BUY")).upper()
    quantity = int(result.get("quantity") or 0)
    price = float(result.get("price") or 0)
    total = float(result.get("total") or price * quantity)
    return f"{order_type} {quantity}주 @ {price:,.0f}원 (총 {total:,.0f}원)"
