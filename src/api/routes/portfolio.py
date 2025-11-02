"""
포트폴리오 관련 API 엔드포인트 모음
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from src.agents.portfolio.nodes import rebalance_plan_node
from src.services import (
    KISAPIError,
    KISAuthError,
    PortfolioNotFoundError,
    portfolio_optimizer,
    portfolio_service,
)
from src.schemas.portfolio import PortfolioChartData, StockChartData

router = APIRouter()
logger = logging.getLogger(__name__)


class DecimalFriendlyModel(BaseModel):
    """Decimal 값을 JSON 직렬화 시 float로 변환하기 위한 베이스 모델."""

    model_config = ConfigDict(json_encoders={Decimal: float})


def _to_decimal(value: Optional[Any]) -> Optional[Decimal]:
    """Helper to convert floats/strings to Decimal safely."""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return None


class Position(DecimalFriendlyModel):
    """포트폴리오 보유 종목"""

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


class PortfolioSummary(DecimalFriendlyModel):
    """포트폴리오 요약"""

    portfolio_id: str
    total_value: Decimal
    cash_balance: Decimal
    invested_amount: Decimal
    total_return: Decimal
    positions: List[Position]
    risk_profile: Optional[str] = None
    last_updated: Optional[str] = None


class PortfolioSummarySection(BaseModel):
    """포트폴리오 전체 요약 정보"""

    total_value: float
    principal: float
    profit: float
    profit_rate: float
    cash: float
    cash_percentage: float
    updated_at: Optional[str] = None


class PortfolioHoldingItem(BaseModel):
    """보유 종목 세부 정보"""

    stock_code: str
    stock_name: str
    quantity: int
    avg_price: float
    current_price: float
    market_value: float
    profit: float
    profit_rate: float
    weight: float


class AllocationItem(BaseModel):
    """배분 정보 항목"""

    name: str
    value: float
    percentage: float


class PortfolioAllocation(BaseModel):
    """자산 및 섹터 배분 정보"""

    sectors: List[AllocationItem]
    asset_classes: List[AllocationItem]


class PortfolioOverview(BaseModel):
    """포트폴리오 오버뷰 응답 페이로드"""

    summary: PortfolioSummarySection
    holdings: List[PortfolioHoldingItem]
    allocation: PortfolioAllocation


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


def _float(value: Optional[Any], default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float):
            return value
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
    except (TypeError, ValueError):
        return default


def _percent(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return (numerator / denominator) * 100.0


@router.get("/", response_model=PortfolioOverview)
async def get_portfolio_overview():
    """대시보드와 포트폴리오 화면에 필요한 요약 데이터를 제공합니다."""
    snapshot = await portfolio_service.get_portfolio_snapshot()

    if snapshot is None or not (snapshot.portfolio_data or {}).get("holdings"):
        try:
            snapshot = await portfolio_service.sync_with_kis()
        except (KISAPIError, KISAuthError, PortfolioNotFoundError) as exc:
            logger.warning("KIS 동기화 실패 - 기본 스냅샷 사용: %s", exc)
        except Exception as exc:  # pragma: no cover - 방어
            logger.exception("KIS 동기화 중 예기치 못한 오류: %s", exc)

    if snapshot is None or snapshot.portfolio_data is None:
        empty_summary = PortfolioSummarySection(
            total_value=0.0,
            principal=0.0,
            profit=0.0,
            profit_rate=0.0,
            cash=0.0,
            cash_percentage=0.0,
            updated_at=None,
        )
        empty_allocation = PortfolioAllocation(sectors=[], asset_classes=[])
        return PortfolioOverview(summary=empty_summary, holdings=[], allocation=empty_allocation)

    portfolio_data = snapshot.portfolio_data or {}
    market_data = snapshot.market_data or {}

    total_value = _float(portfolio_data.get("total_value"))
    principal = _float(portfolio_data.get("invested_amount"))
    cash = _float(portfolio_data.get("cash_balance"))
    profit = total_value - principal
    profit_rate = _percent(profit, principal) if principal else 0.0
    cash_percentage = _percent(cash, total_value) if total_value else 0.0

    holdings_payload: List[PortfolioHoldingItem] = []
    stock_total = 0.0
    holdings_data: List[Dict[str, Any]] = portfolio_data.get("holdings") or []
    for holding in holdings_data:
        stock_code = holding.get("stock_code") or ""
        if stock_code.upper() == "CASH":
            continue

        quantity = int(holding.get("quantity") or 0)
        avg_price = _float(holding.get("average_price"))
        current_price = _float(holding.get("current_price"), avg_price)
        market_value = _float(holding.get("market_value"), current_price * quantity)
        cost_basis = avg_price * quantity
        profit_value = market_value - cost_basis
        profit_rate_value = _percent(profit_value, cost_basis) if cost_basis else 0.0
        weight_ratio = _float(holding.get("weight"))
        weight_percentage = weight_ratio * 100.0 if weight_ratio else _percent(market_value, total_value)

        stock_total += market_value

        holdings_payload.append(
            PortfolioHoldingItem(
                stock_code=stock_code,
                stock_name=str(holding.get("stock_name") or stock_code),
                quantity=quantity,
                avg_price=avg_price,
                current_price=current_price,
                market_value=market_value,
                profit=profit_value,
                profit_rate=profit_rate_value,
                weight=weight_percentage,
            )
        )

    sector_map = portfolio_data.get("sectors") or {}
    sectors: List[AllocationItem] = []
    for name, ratio in sector_map.items():
        ratio_value = _float(ratio)
        value = total_value * ratio_value if total_value else 0.0
        sectors.append(
            AllocationItem(
                name=name,
                value=value,
                percentage=ratio_value * 100.0,
            )
        )

    asset_classes: List[AllocationItem] = []
    if total_value:
        if stock_total:
            asset_classes.append(
                AllocationItem(
                    name="주식",
                    value=stock_total,
                    percentage=_percent(stock_total, total_value),
                )
            )
        if cash:
            asset_classes.append(
                AllocationItem(
                    name="현금",
                    value=cash,
                    percentage=_percent(cash, total_value),
                )
            )
    else:
        if stock_total:
            asset_classes.append(AllocationItem(name="주식", value=stock_total, percentage=0.0))
        if cash:
            asset_classes.append(AllocationItem(name="현금", value=cash, percentage=0.0))

    summary = PortfolioSummarySection(
        total_value=total_value,
        principal=principal,
        profit=profit,
        profit_rate=profit_rate,
        cash=cash,
        cash_percentage=cash_percentage,
        updated_at=market_data.get("last_updated"),
    )

    allocation = PortfolioAllocation(
        sectors=sectors,
        asset_classes=asset_classes,
    )

    return PortfolioOverview(
        summary=summary,
        holdings=holdings_payload,
        allocation=allocation,
    )


@router.get("/{portfolio_id}", response_model=PortfolioSummary)
async def get_portfolio(portfolio_id: str):
    """지정한 포트폴리오의 세부 정보를 조회합니다."""
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
    """지정한 포트폴리오의 성과 지표를 반환합니다."""
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

    beta_data = market_data.get("beta")
    portfolio_beta: Optional[float] = None
    if isinstance(beta_data, dict) and beta_data:
        holdings_data = snapshot.portfolio_data.get("holdings") or []
        weight_map: Dict[str, float] = {}
        for holding in holdings_data:
            code = holding.get("stock_code")
            if not code or code.upper() == "CASH":
                continue
            weight_value = _float(holding.get("weight"))
            if weight_value <= 0:
                continue
            weight_map[code] = weight_value

        if weight_map:
            portfolio_beta = sum(
                weight_map[code] * _float(beta_data.get(code), 0.0)
                for code in weight_map
            )
    elif isinstance(beta_data, (int, float)):
        portfolio_beta = float(beta_data)

    response = {
        "portfolio_id": str(snapshot.portfolio_data.get("portfolio_id") or portfolio_id),
        "total_return": total_return,
        "annual_return": annual_return,
        "sharpe_ratio": market_data.get("sharpe_ratio"),
        "max_drawdown": market_data.get("max_drawdown_estimate"),
        "volatility": market_data.get("portfolio_volatility"),
        "var_95": market_data.get("var_95"),
        "beta": portfolio_beta,
        "observations": market_data.get("observations"),
    }

    return response


@router.get("/chart-data", response_model=PortfolioChartData)
async def get_portfolio_chart_data():
    """
    포트폴리오 차트용 데이터

    Frontend Recharts 연동을 위한 단순화된 데이터 구조:
    - Treemap: 종목별 비중 (weight)
    - Pie Chart: 섹터별 비중 (sectors)
    - Bar Chart: 수익률 순위 (return_percent)
    """
    # 포트폴리오 스냅샷 조회
    snapshot = await portfolio_service.get_portfolio_snapshot()

    if snapshot is None or not (snapshot.portfolio_data or {}).get("holdings"):
        # KIS 동기화 시도
        try:
            snapshot = await portfolio_service.sync_with_kis()
        except (KISAPIError, KISAuthError, PortfolioNotFoundError) as exc:
            logger.warning("KIS 동기화 실패: %s", exc)
        except Exception as exc:
            logger.exception("KIS 동기화 중 예기치 못한 오류: %s", exc)

    # 빈 포트폴리오 반환
    if snapshot is None or snapshot.portfolio_data is None:
        return PortfolioChartData(
            stocks=[],
            total_value=0.0,
            total_return=0.0,
            total_return_percent=0.0,
            cash=0.0,
            sectors={"현금": 1.0}
        )

    portfolio_data = snapshot.portfolio_data or {}
    holdings_data: List[Dict[str, Any]] = portfolio_data.get("holdings") or []

    total_value = _float(portfolio_data.get("total_value"))
    invested_amount = _float(portfolio_data.get("invested_amount"))
    cash = _float(portfolio_data.get("cash_balance"))

    # 총 수익률 계산
    if invested_amount > 0:
        total_return = total_value - invested_amount
        total_return_percent = (total_return / invested_amount) * 100.0
    else:
        total_return = 0.0
        total_return_percent = 0.0

    # 차트 데이터 생성
    stocks_data: List[StockChartData] = []
    sector_weights: Dict[str, float] = {}

    for holding in holdings_data:
        stock_code = holding.get("stock_code") or ""

        # 현금 제외
        if stock_code.upper() == "CASH":
            continue

        quantity = int(holding.get("quantity") or 0)
        avg_price = _float(holding.get("average_price"))
        current_price = _float(holding.get("current_price"), avg_price)
        market_value = _float(holding.get("market_value"), current_price * quantity)

        # 비중 계산 (스냅샷에 저장된 weight가 있으면 우선 사용)
        weight = _float(
            holding.get("weight"),
            market_value / total_value if total_value > 0 else 0.0,
        )

        # 수익률 계산
        cost_basis = avg_price * quantity
        if cost_basis > 0:
            return_percent = ((market_value - cost_basis) / cost_basis) * 100.0
        else:
            return_percent = 0.0

        sector = holding.get("sector")
        sector_name = str(sector) if sector else "기타"

        stock_chart_data = StockChartData(
            stock_code=stock_code,
            stock_name=str(holding.get("stock_name") or stock_code),
            quantity=quantity,
            current_price=current_price,
            purchase_price=avg_price,
            weight=round(weight, 4),
            return_percent=round(return_percent, 2),
            sector=sector_name,
        )

        stocks_data.append(stock_chart_data)

        # 섹터별 비중 집계
        sector_weights[sector_name] = sector_weights.get(sector_name, 0.0) + weight

    # 현금 비중 추가
    if total_value > 0:
        cash_weight = cash / total_value
        sector_weights["현금"] = round(cash_weight, 4)

    # 섹터 비중 반올림
    sector_weights = {k: round(v, 4) for k, v in sector_weights.items()}

    return PortfolioChartData(
        stocks=stocks_data,
        total_value=total_value,
        total_return=total_return,
        total_return_percent=round(total_return_percent, 2),
        cash=cash,
        sectors=sector_weights
    )


@router.post("/{portfolio_id}/rebalance")
async def rebalance_portfolio(portfolio_id: str):
    """포트폴리오 리밸런싱 제안과 예상 지표를 생성합니다."""
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


@router.get("/chart-data")
async def get_portfolio_chart_data(portfolio_id: str):
    """
    포트폴리오 차트용 데이터 (Treemap, Pie Chart)

    **Frontend 연동:**
    - Treemap: 종목별 비중 + 수익률 색상
    - Pie Chart: 섹터별 비중

    **Response:**
    ```json
    {
        "stocks": [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "quantity": 10,
                "current_price": 76300,
                "purchase_price": 70000,
                "weight": 0.35,
                "return_percent": 9.0,
                "sector": "반도체",
                "color": "#10B981"
            }
        ],
        "total_value": 10000000,
        "total_return": 900000,
        "total_return_percent": 9.0,
        "cash": 1000000,
        "cash_weight": 0.1,
        "sectors": {
            "반도체": {
                "weight": 0.45,
                "value": 4500000,
                "color": "#8B5CF6"
            },
            "배터리": {
                "weight": 0.30,
                "value": 3000000,
                "color": "#F59E0B"
            },
            "현금": {
                "weight": 0.10,
                "value": 1000000,
                "color": "#6B7280"
            }
        }
    }
    ```
    """
    try:
        # 1. 포트폴리오 조회
        snapshot = await portfolio_service.get_snapshot(portfolio_id)

        if not snapshot:
            raise HTTPException(
                status_code=404,
                detail=f"Portfolio {portfolio_id} not found"
            )

        portfolio_data = snapshot.portfolio_data
        holdings = portfolio_data.get("holdings", [])
        cash_balance = _float(portfolio_data.get("cash_balance", 0))

        # 2. 실시간 주가 조회 (Redis 캐시 우선)
        stocks_data = []
        total_investment = 0.0
        total_market_value = 0.0
        sector_weights = {}

        for holding in holdings:
            stock_code = holding.get("stock_code")
            quantity = holding.get("quantity", 0)
            avg_price = _float(holding.get("average_price", 0))

            # 실시간 주가 조회 (Realtime Cache 활용)
            price_data = await stock_data_service.get_realtime_price(stock_code)

            if price_data:
                current_price = _float(price_data.get("price", 0))
            else:
                # Fallback: FinanceDataReader
                logger.warning(f"Realtime price not found for {stock_code}, using fallback")
                current_price = _float(holding.get("current_price", avg_price))

            # 계산
            market_value = quantity * current_price
            investment = quantity * avg_price
            return_percent = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0.0

            total_investment += investment
            total_market_value += market_value

            # 섹터 정보
            sector = get_sector(stock_code)

            stocks_data.append({
                "stock_code": stock_code,
                "stock_name": holding.get("stock_name", stock_code),
                "quantity": quantity,
                "current_price": current_price,
                "purchase_price": avg_price,
                "market_value": market_value,
                "return_percent": round(return_percent, 2),
                "sector": sector,
            })

            # 섹터별 비중 집계
            if sector not in sector_weights:
                sector_weights[sector] = {"value": 0.0, "weight": 0.0}
            sector_weights[sector]["value"] += market_value

        # 3. 총 평가금액
        total_value = total_market_value + cash_balance

        # 4. 주식별 비중 및 색상 추가
        for stock in stocks_data:
            stock["weight"] = round(stock["market_value"] / total_value, 4) if total_value > 0 else 0.0
            # 수익률에 따라 색상 결정
            if stock["return_percent"] > 10:
                stock["color"] = "#10B981"  # Green (높은 수익)
            elif stock["return_percent"] > 0:
                stock["color"] = "#34D399"  # Light Green (플러스)
            elif stock["return_percent"] > -10:
                stock["color"] = "#FBBF24"  # Yellow (작은 손실)
            else:
                stock["color"] = "#EF4444"  # Red (큰 손실)

        # 5. 섹터별 비중 및 색상 계산
        for sector in sector_weights:
            sector_weights[sector]["weight"] = round(
                sector_weights[sector]["value"] / total_value, 4
            ) if total_value > 0 else 0.0
            sector_weights[sector]["color"] = get_sector_color(sector)

        # 현금 추가
        cash_weight = round(cash_balance / total_value, 4) if total_value > 0 else 0.0
        sector_weights["현금"] = {
            "weight": cash_weight,
            "value": cash_balance,
            "color": get_sector_color("현금")
        }

        # 6. 총 수익률 계산
        total_return = total_market_value - total_investment
        total_return_percent = (
            (total_return / total_investment) * 100
            if total_investment > 0 else 0.0
        )

        return {
            "stocks": stocks_data,
            "total_value": total_value,
            "total_return": total_return,
            "total_return_percent": round(total_return_percent, 2),
            "cash": cash_balance,
            "cash_weight": cash_weight,
            "sectors": sector_weights,
            "updated_at": snapshot.timestamp.isoformat() if snapshot.timestamp else None
        }

    except PortfolioNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Portfolio {portfolio_id} not found"
        )
    except Exception as e:
        logger.error(f"Error getting portfolio chart data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get portfolio chart data: {str(e)}"
        )
