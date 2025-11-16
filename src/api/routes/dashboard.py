"""
대시보드 관련 API 엔드포인트 모음
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from src.models.database import SessionLocal
from src.models.portfolio import Transaction
from src.models.stock import Stock
from src.services.portfolio_service import portfolio_service

router = APIRouter()


class TotalAssets(BaseModel):
    """총자산 요약 정보"""

    value: float
    profit: float
    profit_rate: float
    change_24h: float
    change_24h_rate: float


class AccountConnection(BaseModel):
    """증권 계좌 연결 상태 정보"""

    broker: str
    account_number: str
    status: str
    last_synced_at: Optional[str] = None


class AutomationSettings(BaseModel):
    """자동화 설정 정보"""

    intervention_required: bool
    description: str
    enabled: bool


class ActivityItem(BaseModel):
    """최근 활동 이력"""

    id: str
    type: str
    icon: str
    title: str
    description: str
    timestamp: Optional[str] = None
    status: str
    amount: Optional[float] = None


class HoldingHighlight(BaseModel):
    """상위 보유 종목 요약"""

    stock_code: str
    stock_name: str
    quantity: int
    value: float
    profit_rate: float
    weight: float


class PerformancePeriod(BaseModel):
    """기간별 성과 지표"""

    profit: float
    profit_rate: float


class PerformanceSummary(BaseModel):
    """기간별 성과 요약"""

    today: PerformancePeriod
    week: PerformancePeriod
    month: PerformancePeriod
    year: PerformancePeriod


class DashboardPayload(BaseModel):
    """대시보드 API 응답 페이로드"""

    total_assets: TotalAssets
    account_connection: AccountConnection
    automation_settings: AutomationSettings
    recent_activities: List[ActivityItem]
    top_holdings: List[HoldingHighlight]
    performance_summary: PerformanceSummary


def _float(value: Optional[Any], default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float):
            return value
        return float(value)
    except (TypeError, ValueError):
        return default


def _percent(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return (numerator / denominator) * 100.0


def _intervention_description(intervention_required: bool) -> str:
    """intervention_required 설명 반환"""
    if intervention_required:
        return "모든 단계에서 승인 필요"
    else:
        return "매매 단계만 승인 필요"


async def _recent_transactions(limit: int = 5) -> List[ActivityItem]:
    def _fetch() -> List[ActivityItem]:
        with SessionLocal() as session:
            transactions: List[Transaction] = (
                session.query(Transaction)
                .order_by(Transaction.executed_at.desc().nullslast())
                .limit(limit)
                .all()
            )

            if not transactions:
                return []

            codes = {txn.stock_code for txn in transactions if txn.stock_code}
            stocks: Dict[str, Stock] = {}
            if codes:
                stock_rows = session.query(Stock).filter(Stock.stock_code.in_(codes)).all()
                stocks = {stock.stock_code: stock for stock in stock_rows}

            activities: List[ActivityItem] = []
            for txn in transactions:
                code = txn.stock_code or ""
                stock = stocks.get(code)
                is_buy = (txn.transaction_type or "").upper() == "BUY"
                activity_type = "trade_buy" if is_buy else "trade_sell"
                icon = "💰" if is_buy else "📉"
                title_action = "매수" if is_buy else "매도"
                stock_name = stock.stock_name if stock else code

                price = _float(txn.price)
                quantity = int(txn.quantity or 0)
                amount = _float(txn.total_amount, price * quantity)

                activities.append(
                    ActivityItem(
                        id=f"txn-{txn.transaction_id}",
                        type=activity_type,
                        icon=icon,
                        title=f"{stock_name} {quantity}주 {title_action}",
                        description=f"{price:,.0f}원 × {quantity}주",
                        timestamp=txn.executed_at.isoformat() if txn.executed_at else None,
                        status="completed",
                        amount=amount,
                    )
                )

            return activities

    return await asyncio.to_thread(_fetch)


@router.get("/", response_model=DashboardPayload)
async def get_dashboard():
    """대시보드 화면에 필요한 요약 정보를 제공합니다."""
    snapshot = await portfolio_service.get_portfolio_snapshot()

    portfolio_data = snapshot.portfolio_data if snapshot else {}
    market_data = snapshot.market_data if snapshot else {}
    profile = snapshot.profile if snapshot else {}

    total_value = _float(portfolio_data.get("total_value"))
    principal = _float(portfolio_data.get("invested_amount"))
    profit = total_value - principal
    profit_rate = _percent(profit, principal) if principal else 0.0

    cash = _float(portfolio_data.get("cash_balance"))
    total_assets = TotalAssets(
        value=total_value,
        profit=profit,
        profit_rate=profit_rate,
        change_24h=0.0,
        change_24h_rate=0.0,
    )

    account_connection = AccountConnection(
        broker="한국투자증권",
        account_number="1234-5678-****",
        status="connected" if total_value else "disconnected",
        last_synced_at=market_data.get("last_updated"),
    )

    intervention_required = bool(profile.get("intervention_required", False))
    automation_settings = AutomationSettings(
        intervention_required=intervention_required,
        description=_intervention_description(intervention_required),
        enabled=True,
    )

    holdings = portfolio_data.get("holdings") or []
    stock_holdings = [
        holding
        for holding in holdings
        if (holding.get("stock_code") or "").upper() != "CASH"
    ]

    sorted_holdings = sorted(
        stock_holdings,
        key=lambda h: _float(h.get("market_value")),
        reverse=True,
    )

    top_holdings: List[HoldingHighlight] = []
    for holding in sorted_holdings[:5]:
        stock_code = holding.get("stock_code") or ""
        quantity = int(holding.get("quantity") or 0)
        market_value = _float(holding.get("market_value"))
        cost_basis = _float(holding.get("average_price")) * quantity
        holding_profit = market_value - cost_basis
        holding_profit_rate = _percent(holding_profit, cost_basis) if cost_basis else 0.0
        weight_ratio = _float(holding.get("weight"))
        weight_percentage = weight_ratio * 100.0 if weight_ratio else _percent(market_value, total_value)

        top_holdings.append(
            HoldingHighlight(
                stock_code=stock_code,
                stock_name=str(holding.get("stock_name") or stock_code),
                quantity=quantity,
                value=market_value,
                profit_rate=holding_profit_rate,
                weight=weight_percentage,
            )
        )

    recent_activities = await _recent_transactions()

    performance_summary = PerformanceSummary(
        today=PerformancePeriod(profit=0.0, profit_rate=0.0),
        week=PerformancePeriod(profit=0.0, profit_rate=0.0),
        month=PerformancePeriod(profit=0.0, profit_rate=0.0),
        year=PerformancePeriod(profit=profit, profit_rate=profit_rate),
    )

    return DashboardPayload(
        total_assets=total_assets,
        account_connection=account_connection,
        automation_settings=automation_settings,
        recent_activities=recent_activities,
        top_holdings=top_holdings,
        performance_summary=performance_summary,
    )
