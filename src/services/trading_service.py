"""Trading service utilities bridging LangGraph nodes and the database."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.portfolio import Order, Transaction
from src.services.portfolio_service import (
    InsufficientHoldingsError,
    PortfolioNotFoundError,
    portfolio_service,
)
from src.services.stock_data_service import stock_data_service

logger = logging.getLogger(__name__)


class OrderNotFoundError(Exception):
    """Raised when an order could not be fetched from the database."""


class TradingService:
    """Service layer for order lifecycle management."""

    def __init__(self, session_factory=SessionLocal) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def create_pending_order(
        self,
        *,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        stock_code: str,
        order_type: str,
        quantity: int,
        order_price: Optional[float] = None,
        order_price_type: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_portfolio_id = await portfolio_service.resolve_portfolio_id(
            user_id=user_id,
            portfolio_id=portfolio_id,
        )
        if not resolved_portfolio_id:
            raise PortfolioNotFoundError("No portfolio is registered for trading")

        order_type = (order_type or "BUY").upper()
        price_type = (order_price_type or ("LIMIT" if order_price is not None else "MARKET")).upper()
        price_dec = self._decimal(order_price)

        def _create() -> Order:
            with self._session_factory() as session:
                order = Order(
                    portfolio_id=uuid.UUID(resolved_portfolio_id),
                    stock_code=stock_code,
                    order_type=order_type,
                    order_price_type=price_type,
                    order_price=price_dec,
                    order_quantity=quantity,
                    unfilled_quantity=quantity,
                    order_status="pending",
                    notes=notes,
                )
                session.add(order)
                session.commit()
                session.refresh(order)
                return order

        order = await asyncio.to_thread(_create)
        return self._serialize_order(order)

    async def mark_order_status(
        self,
        order_id: str,
        *,
        status: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        def _update() -> Order:
            with self._session_factory() as session:
                order = session.get(Order, uuid.UUID(order_id))
                if not order:
                    raise OrderNotFoundError(order_id)
                order.order_status = status
                if status == "rejected":
                    order.cancelled_at = datetime.utcnow()
                if notes:
                    existing = (order.notes or "").strip()
                    order.notes = f"{existing}\n{notes}".strip() if existing else notes
                session.commit()
                session.refresh(order)
                return order

        order = await asyncio.to_thread(_update)
        return self._serialize_order(order)

    async def execute_order(
        self,
        order_id: str,
        *,
        execution_price: Optional[float] = None,
        automation_level: int = 2,
    ) -> Dict[str, Any]:
        order_summary = await self._fetch_order(order_id)
        if not order_summary:
            raise OrderNotFoundError(order_id)

        if execution_price is None:
            execution_price = await self._fetch_market_price(order_summary["stock_code"]) or order_summary.get("order_price")
        if execution_price is None:
            execution_price = 0.0

        try:
            result = await self._simulate_execution(order_summary, execution_price)
        except InsufficientHoldingsError as exc:
            logger.warning("Execution failed due to insufficient holdings: %s", exc)
            await self.mark_order_status(order_id, status="rejected", notes=str(exc))
            return {"error": str(exc), "status": "rejected", "order_id": order_id}

        # Refresh portfolio snapshot after execution
        snapshot = await portfolio_service.get_portfolio_snapshot(portfolio_id=order_summary["portfolio_id"])
        if snapshot:
            result["portfolio_snapshot"] = {
                "portfolio_data": snapshot.portfolio_data,
                "market_data": snapshot.market_data,
                "profile": snapshot.profile,
            }
        result["automation_level"] = automation_level
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _simulate_execution(
        self,
        order_summary: Dict[str, Any],
        execution_price: float,
    ) -> Dict[str, Any]:
        """주문 실행 (KIS API 연동)"""
        order_id = order_summary["order_id"]
        stock_code = order_summary["stock_code"]
        order_type = order_summary["order_type"]
        quantity = order_summary["order_quantity"]

        # 1. KIS API로 실제 주문 실행 시도
        kis_order_no = None
        kis_executed = False

        try:
            from src.services import kis_service

            logger.info(f"💰 [Trading] KIS API 주문 실행: {order_type} {stock_code} {quantity}주")

            kis_result = await kis_service.place_order(
                stock_code=stock_code,
                order_type=order_type,
                quantity=quantity,
                price=execution_price,  # None이면 시장가
            )

            kis_order_no = kis_result.get("order_no")
            kis_executed = True

            logger.info(f"✅ [Trading] KIS 주문 성공: {kis_order_no}")

        except Exception as exc:
            # KIS API 실패 시 경고 로그만 남기고 DB 시뮬레이션 진행
            logger.warning(f"⚠️ [Trading] KIS API 실패, DB 시뮬레이션으로 진행: {exc}")
            kis_executed = False

        # 2. DB 업데이트 (KIS 성공 여부 무관하게 진행)
        execution_price_dec = self._decimal(execution_price, default=Decimal("0"))
        executed_at = datetime.now(timezone.utc)

        def _update() -> Order:
            with self._session_factory() as session:
                order = session.get(Order, uuid.UUID(order_id))
                if not order:
                    raise OrderNotFoundError(order_id)
                order.order_status = "filled"
                order.filled_quantity = order.order_quantity
                order.unfilled_quantity = 0
                order.filled_avg_price = execution_price_dec
                order.total_filled_amount = execution_price_dec * order.order_quantity
                order.filled_at = executed_at

                # KIS 주문번호 기록
                if kis_order_no:
                    notes = f"KIS 주문번호: {kis_order_no}"
                    if order.notes:
                        order.notes = f"{order.notes}\n{notes}"
                    else:
                        order.notes = notes

                session.commit()
                session.refresh(order)
                return order

        order = await asyncio.to_thread(_update)

        # 3. 포트폴리오 반영
        await portfolio_service.apply_trade(
            portfolio_id=order_summary["portfolio_id"],
            stock_code=order_summary["stock_code"],
            quantity=order_summary["order_quantity"],
            price=float(execution_price_dec),
            order_type=order_summary["order_type"],
            executed_at=executed_at.replace(tzinfo=None),
        )

        # 4. 트랜잭션 기록
        await asyncio.to_thread(
            self._record_transaction_sync,
            order,
            execution_price_dec,
            executed_at,
        )

        # 5. 결과 반환
        result = self._serialize_order(order)
        result.update(
            {
                "status": "executed",
                "price": float(execution_price_dec),
                "quantity": order.order_quantity,
                "total": float(execution_price_dec * order.order_quantity),
                "executed_at": executed_at.isoformat(),
                "kis_executed": kis_executed,
                "kis_order_no": kis_order_no,
            }
        )
        return result

    async def _fetch_market_price(self, stock_code: str) -> Optional[float]:
        try:
            df = await stock_data_service.get_stock_price(stock_code, days=1)
        except Exception:  # pragma: no cover - defensive fallback
            return None
        if df is None or df.empty:
            return None
        try:
            return float(df["Close"].iloc[-1])
        except Exception:  # pragma: no cover - defensive
            return None

    async def _fetch_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        def _fetch() -> Optional[Order]:
            with self._session_factory() as session:
                return session.get(Order, uuid.UUID(order_id))

        order = await asyncio.to_thread(_fetch)
        return self._serialize_order(order) if order else None

    def _record_transaction_sync(
        self,
        order: Order,
        execution_price: Decimal,
        executed_at: datetime,
    ) -> None:
        with self._session_factory() as session:
            transaction = Transaction(
                portfolio_id=order.portfolio_id,
                stock_code=order.stock_code,
                transaction_type=order.order_type,
                quantity=order.order_quantity,
                price=execution_price,
                total_amount=execution_price * order.order_quantity,
                order_id=order.order_id,
                executed_at=executed_at,
            )
            session.add(transaction)
            session.commit()

    def _serialize_order(self, order: Optional[Order]) -> Dict[str, Any]:
        if not order:
            return {}
        return {
            "order_id": str(order.order_id),
            "portfolio_id": str(order.portfolio_id),
            "stock_code": order.stock_code,
            "order_type": order.order_type,
            "order_price_type": order.order_price_type,
            "order_price": self._to_float(order.order_price),
            "order_quantity": order.order_quantity,
            "filled_quantity": order.filled_quantity,
            "unfilled_quantity": order.unfilled_quantity,
            "filled_avg_price": self._to_float(order.filled_avg_price),
            "total_filled_amount": self._to_float(order.total_filled_amount),
            "order_status": order.order_status,
            "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
            "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
            "notes": order.notes,
        }

    def _decimal(self, value: Optional[float], default: Optional[Decimal] = None) -> Optional[Decimal]:
        if value is None:
            return default
        try:
            return Decimal(str(value))
        except Exception:
            return default

    def _to_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


trading_service = TradingService()
