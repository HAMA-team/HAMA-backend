"""
Trading SubGraph Nodes

trade_planner → portfolio_simulator → trade_hitl → execute_trade
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from src.services import trading_service
from src.services.stock_data_service import stock_data_service

from .state import TradingState

logger = logging.getLogger(__name__)


async def trade_planner_node(state: TradingState) -> TradingState:
    """
    매매 계획 노드 - 매매 제안 구조화

    request_trade tool의 결과를 trade_proposal로 구조화합니다.

    ⚠️ 중요: Tool에서 state를 직접 업데이트할 수 없으므로,
    messages에서 request_trade tool의 인자를 추출합니다.
    """
    from src.services.portfolio_service import (
        portfolio_service,
        calculate_market_risk_metrics,
        calculate_concentration_risk_metrics,
    )

    action = state.get("trade_action")
    stock_code = state.get("stock_code")
    quantity = state.get("trade_quantity")
    price = state.get("trade_price")
    order_type = state.get("trade_order_type", "limit")

    logger.info("🔍 [Trading/Planner] State 초기 값:")
    logger.info("  - stock_code: %s", stock_code)
    logger.info("  - action: %s", action)
    logger.info("  - quantity: %s", quantity)
    logger.info("  - price: %s", price)

    if not stock_code or not quantity:
        logger.info("🔍 [Trading/Planner] State에 매매 정보 없음, messages에서 추출 시도")
        from langchain_core.messages import AIMessage as _AIMessage, ToolMessage

        messages = state.get("messages", [])

        for msg in reversed(messages):
            if isinstance(msg, _AIMessage) and getattr(msg, "tool_calls", None):
                for tool_call in msg.tool_calls:
                    if tool_call.get("name") == "request_trade":
                        args = tool_call.get("args", {})
                        stock_code = args.get("ticker")
                        action = args.get("action", "buy")
                        quantity = args.get("quantity", 0)
                        price = args.get("price", 0)
                        order_type = "market" if price == 0 else "limit"

                        logger.info("✅ [Trading/Planner] messages에서 매매 정보 추출 성공:")
                        logger.info("  - ticker: %s", stock_code)
                        logger.info("  - action: %s", action)
                        logger.info("  - quantity: %s", quantity)
                        logger.info("  - price (추출됨): %s", price)
                        break
                if stock_code:
                    break

    if not stock_code or not quantity:
        logger.error("❌ [Trading/Planner] 매매 정보를 찾을 수 없습니다")
        raise ValueError("매매 정보를 찾을 수 없습니다: request_trade tool 호출 필요")

    if price is None:
        price = 0
    if price == 0:
        logger.info("📈 [Trading/Planner] 시장가 주문 → 현재가 조회 시도")
        try:
            price_info = await stock_data_service.fetch_realtime_price(stock_code)
            price = price_info.get("close", 0) or price_info.get("price", 0) or 0
            logger.info("✅ [Trading/Planner] 현재가 조회 성공: %s = %d", stock_code, price)
        except Exception as exc:
            logger.warning("⚠️ [Trading/Planner] 현재가 조회 실패: %s", exc)
            price = 0

    # 포트폴리오 정보 조회
    user_id = state.get("user_id")
    portfolio_before = None
    risk_before = None

    try:
        logger.info("📊 [Trading/Planner] 현재 포트폴리오 조회 시작")
        snapshot = await portfolio_service.get_portfolio_snapshot(user_id=user_id)

        if snapshot:
            portfolio_before = snapshot.portfolio_data
            market_data = snapshot.market_data
            holdings_before = portfolio_before.get("holdings", [])
            sectors_before = portfolio_before.get("sectors", {})

            # 리스크 계산
            concentration_risk = calculate_concentration_risk_metrics(
                holdings_before, sectors_before
            )
            market_risk = calculate_market_risk_metrics(portfolio_before, market_data)

            risk_before = {
                **concentration_risk,
                **market_risk,
            }

            logger.info("✅ [Trading/Planner] 포트폴리오 조회 완료")
            logger.info("  - holdings: %d개", len(holdings_before))
            logger.info("  - cash_balance: %s원", portfolio_before.get("cash_balance", 0))
        else:
            logger.warning("⚠️ [Trading/Planner] 포트폴리오를 찾을 수 없습니다")
            # 기본 빈 포트폴리오 생성
            portfolio_before = {
                "holdings": [],
                "cash_balance": 10_000_000,  # 기본 1000만원
                "total_value": 10_000_000,
                "sectors": {},
            }
            risk_before = {}

    except Exception as exc:
        logger.error("❌ [Trading/Planner] 포트폴리오 조회 실패: %s", exc)
        # 기본 빈 포트폴리오 생성
        portfolio_before = {
            "holdings": [],
            "cash_balance": 10_000_000,
            "total_value": 10_000_000,
            "sectors": {},
        }
        risk_before = {}

    total_amount = quantity * price
    trade_proposal = {
        "trade_id": str(uuid.uuid4()),
        "ticker": stock_code,
        "action": action,
        "quantity": quantity,
        "price": price,
        "order_type": order_type,
        "total_amount": total_amount,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "pending",
        "rationale": (
            f"{stock_code} 종목을 {action}하려는 주문입니다. "
            f"수량 {quantity}주, 가격 {price:,}원, 총액 {total_amount:,}원."
        ),
    }

    logger.info("🧾 [Trading/Planner] 매매 제안 생성 완료: %s", trade_proposal["trade_id"])

    return {
        "trade_action": action,
        "stock_code": stock_code,
        "trade_quantity": quantity,
        "trade_price": price,
        "trade_order_type": order_type,
        "trade_total_amount": total_amount,
        "trade_proposal": trade_proposal,
        "portfolio_before": portfolio_before,
        "risk_before": risk_before,
        "messages": [AIMessage(content="매매 제안을 준비했습니다.")],
    }


async def portfolio_simulator_node(state: TradingState) -> TradingState:
    """
    포트폴리오 시뮬레이터 노드

    매매 전/후 포트폴리오 및 리스크 지표를 계산합니다.
    """
    try:
        logger.info("📊 [Portfolio/Simulator] 시뮬레이션 시작")

        portfolio_before = state.get("portfolio_before")
        risk_before = state.get("risk_before")

        if not portfolio_before:
            logger.warning("⚠️ [Portfolio/Simulator] portfolio_before가 없습니다. 기본값 사용")
            portfolio_before = {
                "holdings": [],
                "cash_balance": 10_000_000,
                "total_value": 10_000_000,
                "sectors": {},
            }

        if not risk_before:
            logger.warning("⚠️ [Portfolio/Simulator] risk_before가 없습니다. 기본값 사용")
            risk_before = {}

        holdings = portfolio_before.get("holdings", [])
        holdings_after = [h.copy() for h in holdings]  # 깊은 복사

        action = state.get("trade_action", "buy")
        stock_code = state.get("stock_code")
        quantity = state.get("trade_quantity", 0)
        price = state.get("trade_price", 0)
        total_amount = quantity * price

        logger.info(
            "📦 [Portfolio/Simulator] 주문 정보: %s %s %d주 @ %d원 (총 %d원)",
            action,
            stock_code,
            quantity,
            price,
            total_amount,
        )

        target = None
        for holding in holdings_after:
            if holding.get("stock_code") == stock_code:
                target = holding
                break

        cash_before = portfolio_before.get("cash_balance", 0)

        if action == "buy":
            if total_amount > cash_before:
                raise ValueError(
                    f"잔액이 부족합니다. 필요 금액: {total_amount:,}원, 보유 잔액: {cash_before:,}원"
                )

            if target:
                # 기존 보유 종목의 평균 단가 계산
                existing_qty = target.get("quantity", 0)
                existing_avg = target.get("average_price", 0)
                new_avg = (existing_avg * existing_qty + price * quantity) / (
                    existing_qty + quantity
                )
                target["quantity"] = existing_qty + quantity
                target["average_price"] = new_avg
            else:
                holdings_after.append(
                    {
                        "stock_code": stock_code,
                        "stock_name": state.get("stock_name", stock_code),
                        "quantity": quantity,
                        "average_price": price,
                        "current_price": price,
                    }
                )
            cash_after = cash_before - total_amount
        else:  # sell
            if not target:
                raise ValueError(f"{stock_code} 종목을 보유하고 있지 않습니다.")

            holding_quantity = target.get("quantity", 0)
            if holding_quantity < quantity:
                raise ValueError(
                    f"보유 수량이 부족합니다. 매도 요청: {quantity}주, 보유: {holding_quantity}주"
                )

            target["quantity"] = holding_quantity - quantity
            cash_after = cash_before + total_amount

        # 수량이 0인 종목 제거
        holdings_after = [h for h in holdings_after if h.get("quantity", 0) > 0]

        portfolio_after = {
            "holdings": holdings_after,
            "cash_balance": cash_after,
            "total_value": portfolio_before.get("total_value", 0),
            "updated_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            "📈 [Portfolio/Simulator] 시뮬레이션 완료 - holdings %d → %d, cash %d → %d",
            len(holdings),
            len(holdings_after),
            cash_before,
            cash_after,
        )

        # 리스크 계산 (간단한 변동성 업데이트)
        risk_after = risk_before.copy() if isinstance(risk_before, dict) else {}
        # TODO: 실제 리스크 재계산 로직 추가 (portfolio_service 사용)
        risk_after.update({"volatility": (risk_after.get("volatility") or 0) + 0.01})

        return {
            "portfolio_after": portfolio_after,
            "risk_after": risk_after,
            "messages": [AIMessage(content="포트폴리오 시뮬레이션을 완료했습니다.")],
        }

    except Exception as exc:
        logger.error("❌ [Portfolio/Simulator] 시뮬레이션 실패: %s", exc, exc_info=True)
        # 시뮬레이션 실패 시 중단하지 않고 에러 정보를 전달
        return {
            "simulation_failed": True,
            "simulation_error": str(exc),
            "messages": [AIMessage(content=f"포트폴리오 시뮬레이션 실패: {exc}")],
        }


async def trade_hitl_node(state: TradingState) -> TradingState:
    """
    매매 HITL 노드 - 사용자 승인 요청

    경로 1: 첫 실행 → 전/후 비교 데이터와 함께 Interrupt 발생
    경로 2: 승인 후 재개 → 사용자 수정사항 반영 후 재시뮬레이션 또는 실행
    """
    # 시뮬레이션 실패 체크
    if state.get("simulation_failed"):
        error_msg = state.get("simulation_error", "알 수 없는 오류")
        logger.error("❌ [Trading/HITL] 포트폴리오 시뮬레이션 실패로 매매 중단: %s", error_msg)
        raise ValueError(f"포트폴리오 시뮬레이션 실패: {error_msg}")

    if state.get("trade_approved"):
        logger.info("✅ [Trading/HITL] 사용자 승인 완료")
        modifications = state.get("user_modifications")

        if modifications:
            logger.info("✏️ [Trading/HITL] 사용자 수정사항 반영: %s", modifications)

            quantity = modifications.get("quantity", state.get("trade_quantity"))
            price = modifications.get("price", state.get("trade_price"))
            action = modifications.get("action", state.get("trade_action"))
            total_amount = quantity * price

            logger.info(
                "🔄 [Trading/HITL] 수정된 주문: %s %d주 @ %d원 = %d원",
                action,
                quantity,
                price,
                total_amount,
            )
            logger.info("🔄 [Trading/HITL] 재시뮬레이션을 위해 portfolio_simulator로 이동")

            return {
                "trade_quantity": quantity,
                "trade_price": price,
                "trade_action": action,
                "trade_total_amount": total_amount,
                "trade_approved": False,
                "user_modifications": None,
                "simulation_failed": False,  # 재시뮬레이션을 위해 플래그 초기화
                "messages": [
                    AIMessage(
                        content=f"수정된 주문으로 재시뮬레이션을 시작합니다: {action} {quantity}주"
                    )
                ],
            }

        return {
            "trade_prepared": True,
            "messages": [AIMessage(content="매매 주문을 준비했습니다.")],
        }

    logger.info("🔍 [Trading/HITL] State 확인:")
    logger.info("  - trade_action: %s", state.get("trade_action"))
    logger.info("  - stock_code: %s", state.get("stock_code"))
    logger.info("  - trade_quantity: %s", state.get("trade_quantity"))
    logger.info("  - trade_price: %s", state.get("trade_price"))
    logger.info("  - trade_order_type: %s", state.get("trade_order_type"))

    action = state.get("trade_action", "buy")
    stock_code = state.get("stock_code", "")
    stock_name = state.get("stock_name", stock_code)
    quantity = state.get("trade_quantity", 0)
    price = state.get("trade_price", 0)
    total_amount = quantity * price

    portfolio_before = state.get("portfolio_before")
    portfolio_after = state.get("portfolio_after")
    risk_before = state.get("risk_before")
    risk_after = state.get("risk_after")

    if not portfolio_before or not portfolio_after:
        logger.error("❌ [Trading/HITL] 포트폴리오 시뮬레이션 결과가 없습니다.")
        raise ValueError("포트폴리오 시뮬레이션 결과가 없습니다.")

    holdings_before = portfolio_before.get("holdings", [])
    holdings_after = portfolio_after.get("holdings", [])

    logger.info("✅ [Trading/HITL] 전/후 비교 데이터 검증 완료:")
    logger.info("  - Before: %d개 holdings, cash=%s원", len(holdings_before), portfolio_before.get("cash_balance", 0))
    logger.info("  - After: %d개 holdings, cash=%s원", len(holdings_after), portfolio_after.get("cash_balance", 0))

    approval_id = str(uuid.uuid4())
    interrupt_payload = {
        "type": "trade_approval",
        "approval_id": approval_id,
        "action": action,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "quantity": quantity,
        "price": price,
        "total_amount": total_amount,
        "order_type": state.get("trade_order_type", "limit"),
        "modifiable_fields": ["quantity", "price", "action"],
        "message": f"{stock_name} {quantity}주를 {price:,}원에 {action}하시겠습니까?",
        "portfolio_before": portfolio_before,
        "portfolio_after": portfolio_after,
        "risk_before": risk_before,
        "risk_after": risk_after,
    }

    interrupt(interrupt_payload)

    return {
        "trade_approval_id": approval_id,
        "trade_total_amount": total_amount,
        "messages": [AIMessage(content="매매 승인을 기다립니다...")],
    }


async def execute_trade_node(state: TradingState) -> TradingState:
    """
    매매 실행 노드

    trading_service를 통해 실제 주문 실행 (현재는 시뮬레이션)
    """
    action = state.get("trade_action", "buy")
    stock_code = state.get("stock_code", "")
    quantity = state.get("trade_quantity", 0)
    price = state.get("trade_price", 0)

    logger.info(
        "💰 [Trading/Execute] 매매 실행: %s %s %d주 @ %d원",
        action,
        stock_code,
        quantity,
        price,
    )

    try:
        user_id = state.get("user_id", str(uuid.UUID(int=0)))
        order_result = await trading_service.execute_order(
            user_id=user_id,
            stock_code=stock_code,
            quantity=quantity,
            action=action,
            price=price,
        )

        logger.info("✅ [Trading/Execute] 매매 완료: %s", order_result.get("order_id"))

        return {
            "trade_order_id": order_result.get("order_id"),
            "trade_result": order_result,
            "trade_executed": True,
            "messages": [
                AIMessage(content=f"매매 실행 완료: 주문번호 {order_result.get('order_id')}")
            ],
        }

    except Exception as exc:
        logger.error("❌ [Trading/Execute] 매매 실패: %s", exc)
        return {
            "messages": [AIMessage(content=f"매매 실행 실패: {exc}")],
        }


__all__ = [
    "execute_trade_node",
    "portfolio_simulator_node",
    "trade_hitl_node",
    "trade_planner_node",
]
