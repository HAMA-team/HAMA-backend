"""
Portfolio API endpoints
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.agents.portfolio.nodes import rebalance_plan_node
from src.services import portfolio_optimizer, portfolio_service

router = APIRouter()


def _to_decimal(value: Optional[Any]) -> Optional[Decimal]:
    """Helper to convert floats/strings to Decimal safely."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return None


class Position(BaseModel):
    """Portfolio position"""

    stock_code: str
    stock_name: str
    quantity: Optional[int] = None
    average_price: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    unrealized_pnl_rate: Optional[Decimal] = None
    weight: Optional[Decimal] = None
    sector: Optional[str] = None


class PortfolioSummary(BaseModel):
    """Portfolio summary"""

    portfolio_id: str
    total_value: Decimal
    cash_balance: Decimal
    invested_amount: Decimal
    total_return: Decimal
    positions: List[Position]
    risk_profile: Optional[str] = None
    last_updated: Optional[str] = None


def _build_positions(holdings: List[Dict[str, Any]]) -> List[Position]:
    positions: List[Position] = []
    for holding in holdings:
        stock_code = holding.get("stock_code")
        if not stock_code:
            continue

        quantity = holding.get("quantity")
        quantity_value = int(quantity) if isinstance(quantity, (int, float)) else None

        positions.append(
            Position(
                stock_code=stock_code,
                stock_name=holding.get("stock_name") or stock_code,
                quantity=quantity_value,
                average_price=_to_decimal(holding.get("average_price")),
                current_price=_to_decimal(holding.get("current_price")),
                market_value=_to_decimal(holding.get("market_value")),
                unrealized_pnl=_to_decimal(holding.get("unrealized_pnl")),
                unrealized_pnl_rate=_to_decimal(holding.get("unrealized_pnl_rate")),
                weight=_to_decimal(holding.get("weight")),
                sector=holding.get("sector"),
            )
        )
    return positions


@router.get("/{portfolio_id}", response_model=PortfolioSummary)
async def get_portfolio(portfolio_id: str):
    """Get portfolio details"""
    snapshot = await portfolio_service.get_portfolio_snapshot(portfolio_id=portfolio_id)

    if snapshot is None or snapshot.portfolio_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )

    portfolio_data = snapshot.portfolio_data
    invested_amount = _to_decimal(portfolio_data.get("invested_amount")) or Decimal("0")
    total_value = _to_decimal(portfolio_data.get("total_value")) or Decimal("0")
    cash_balance = _to_decimal(portfolio_data.get("cash_balance")) or Decimal("0")

    if invested_amount and invested_amount != 0:
        total_return = (total_value - invested_amount) / invested_amount
    else:
        total_return = Decimal("0")

    positions = _build_positions(portfolio_data.get("holdings") or [])

    return PortfolioSummary(
        portfolio_id=str(portfolio_data.get("portfolio_id") or portfolio_id),
        total_value=total_value,
        cash_balance=cash_balance,
        invested_amount=invested_amount,
        total_return=total_return,
        positions=positions,
        risk_profile=(snapshot.profile or {}).get("risk_tolerance"),
        last_updated=(snapshot.market_data or {}).get("last_updated"),
    )


@router.get("/{portfolio_id}/performance")
async def get_portfolio_performance(portfolio_id: str):
    """Get portfolio performance metrics"""
    snapshot = await portfolio_service.get_portfolio_snapshot(portfolio_id=portfolio_id)

    if snapshot is None or snapshot.portfolio_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )

    market_data = snapshot.market_data or {}

    average_daily_return = market_data.get("average_daily_return")
    annual_return = (
        average_daily_return * 252 if isinstance(average_daily_return, (int, float)) else None
    )

    invested_amount = _to_decimal(snapshot.portfolio_data.get("invested_amount")) or Decimal("0")
    total_value = _to_decimal(snapshot.portfolio_data.get("total_value")) or Decimal("0")
    if invested_amount and invested_amount != 0:
        total_return = float((total_value - invested_amount) / invested_amount)
    else:
        total_return = 0.0

    response = {
        "portfolio_id": str(snapshot.portfolio_data.get("portfolio_id") or portfolio_id),
        "total_return": total_return,
        "annual_return": annual_return,
        "sharpe_ratio": market_data.get("sharpe_ratio"),
        "max_drawdown": market_data.get("max_drawdown_estimate"),
        "volatility": market_data.get("portfolio_volatility"),
        "var_95": market_data.get("var_95"),
        "beta": market_data.get("beta"),
        "observations": market_data.get("observations"),
    }

    return response


@router.post("/{portfolio_id}/rebalance")
async def rebalance_portfolio(portfolio_id: str):
    """Request portfolio rebalancing"""
    snapshot = await portfolio_service.get_portfolio_snapshot(portfolio_id=portfolio_id)
    if snapshot is None or snapshot.portfolio_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )

    current_holdings: List[Dict[str, Any]] = snapshot.portfolio_data.get("holdings") or []
    total_value = float(snapshot.portfolio_data.get("total_value") or 0.0)
    risk_profile = (
        (snapshot.profile or {}).get("risk_tolerance")
        or snapshot.portfolio_data.get("risk_profile")
        or "moderate"
    )

    proposed_allocation, metrics = await portfolio_optimizer.calculate_target_allocation(
        current_holdings=current_holdings,
        strategy_result=None,
        risk_profile=risk_profile,
        total_value=total_value,
    )

    state = await rebalance_plan_node(
        {
            "current_holdings": current_holdings,
            "proposed_allocation": proposed_allocation,
            "total_value": total_value,
            "automation_level": 2,
        }
    )

    trades = state.get("trades_required", [])

    return {
        "portfolio_id": str(snapshot.portfolio_data.get("portfolio_id") or portfolio_id),
        "rebalancing_needed": state.get("rebalancing_needed", False),
        "requires_approval": state.get("hitl_required", False),
        "expected_return": metrics.get("expected_return"),
        "expected_volatility": metrics.get("expected_volatility"),
        "sharpe_ratio": metrics.get("sharpe_ratio"),
        "proposed_allocation": proposed_allocation,
        "trades": trades,
        "message": "Generated rebalancing proposal",
    }
