"""Portfolio service utilities for database-backed portfolio operations."""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.portfolio import Portfolio, Position
from src.models.stock import Stock
from src.models.user import User
from src.models.user_profile import UserProfile
from src.services.stock_data_service import stock_data_service

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252
DEFAULT_RISK_FREE_RATE = getattr(settings, "RISK_FREE_RATE", 0.035)


class PortfolioNotFoundError(Exception):
    """Raised when the requested portfolio is not found in the database."""


class InsufficientHoldingsError(Exception):
    """Raised when attempting to sell more shares than are available."""


@dataclass
class PortfolioSnapshot:
    """Normalized snapshot returned by `PortfolioService`."""

    portfolio_data: Dict[str, Any]
    market_data: Dict[str, Any]
    profile: Dict[str, Any]


class PortfolioService:
    """Service object for portfolio, position, and risk calculations."""

    def __init__(self, session_factory=SessionLocal) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def resolve_portfolio_id(
        self,
        *,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Optional[str]:
        """Resolve an incoming user/portfolio identifier to a portfolio UUID."""

        effective_user_id = user_id or settings.DEMO_USER_ID

        def _resolve() -> Optional[str]:
            with self._session_factory() as session:
                # Direct portfolio lookup first
                if portfolio_id:
                    try:
                        pid = uuid.UUID(str(portfolio_id))
                    except ValueError:
                        pid = None
                    if pid:
                        portfolio = session.query(Portfolio).filter(Portfolio.portfolio_id == pid).first()
                        if portfolio:
                            return str(portfolio.portfolio_id)

                candidate_user_ids: List[uuid.UUID] = []
                if effective_user_id:
                    try:
                        candidate_user_ids.append(uuid.UUID(str(effective_user_id)))
                    except ValueError:
                        # Try to resolve by username/email alias
                        user = (
                            session.query(User)
                            .filter((User.username == effective_user_id) | (User.email == effective_user_id))
                            .first()
                        )
                        if user:
                            candidate_user_ids.append(user.user_id)

                for uid in candidate_user_ids:
                    portfolio = (
                        session.query(Portfolio)
                        .filter(Portfolio.user_id == uid)
                        .order_by(Portfolio.created_at.asc() if hasattr(Portfolio, "created_at") else Portfolio.portfolio_id.asc())
                        .first()
                    )
                    if portfolio:
                        return str(portfolio.portfolio_id)

                portfolio = (
                    session.query(Portfolio)
                    .order_by(Portfolio.created_at.asc() if hasattr(Portfolio, "created_at") else Portfolio.portfolio_id.asc())
                    .first()
                )
                return str(portfolio.portfolio_id) if portfolio else None

        return await asyncio.to_thread(_resolve)

    async def get_portfolio_snapshot(
        self,
        *,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        lookback_days: int = 60,
    ) -> Optional[PortfolioSnapshot]:
        """Return a consolidated portfolio snapshot with risk metrics.

        Falls back to ``None`` when the portfolio cannot be resolved.
        """

        resolved_id = await self.resolve_portfolio_id(
            user_id=user_id or settings.DEMO_USER_ID,
            portfolio_id=portfolio_id,
        )
        if not resolved_id:
            logger.error("[PortfolioService] 포트폴리오를 찾을 수 없습니다")
            raise PortfolioNotFoundError(
                f"사용자 '{user_id}'의 포트폴리오를 찾을 수 없습니다. "
                "먼저 종목을 매수하여 포트폴리오를 만들어주세요."
            )

        base_snapshot = await asyncio.to_thread(self._load_snapshot_sync, resolved_id)
        if base_snapshot is None:
            logger.error("[PortfolioService] 포트폴리오 데이터를 로드할 수 없습니다")
            raise PortfolioNotFoundError(
                f"포트폴리오 ID '{resolved_id}'의 데이터를 찾을 수 없습니다. "
                "KIS API 동기화를 시도해주세요."
            )

        portfolio_data = base_snapshot["portfolio_data"]
        market_data = base_snapshot["market_data"]

        try:
            metrics = await self._compute_market_metrics(
                portfolio_data.get("holdings", []),
                lookback_days=lookback_days,
            )
            market_data.update(metrics)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Risk metric calculation failed: %s", exc)

        return PortfolioSnapshot(
            portfolio_data=portfolio_data,
            market_data=market_data,
            profile=base_snapshot.get("profile", {}),
        )

    async def sync_with_kis(
        self,
        *,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
    ) -> Optional[PortfolioSnapshot]:
        """KIS API를 통해 최신 계좌 잔고를 조회하고 DB와 동기화합니다."""
        try:
            from src.services.kis_service import kis_service  # pylint: disable=import-outside-toplevel
        except ImportError:
            logger.warning("[PortfolioService] KIS 서비스 모듈을 불러오지 못해 동기화를 건너뜁니다")
            return None

        resolved_id = await self.resolve_portfolio_id(
            user_id=user_id or settings.DEMO_USER_ID,
            portfolio_id=portfolio_id,
        )
        if not resolved_id:
            raise PortfolioNotFoundError("포트폴리오를 찾을 수 없어 KIS 동기화를 수행할 수 없습니다.")

        balance = await kis_service.get_account_balance()
        await asyncio.to_thread(self._sync_kis_balance_sync, resolved_id, balance)

        snapshot = await self.get_portfolio_snapshot(portfolio_id=resolved_id)
        if snapshot:
            snapshot.portfolio_data["data_source"] = "kis_api"
        return snapshot

    async def apply_trade(
        self,
        *,
        portfolio_id: str,
        stock_code: str,
        quantity: int,
        price: float,
        order_type: str,
        executed_at: Optional[datetime] = None,
    ) -> None:
        """Apply a filled order to portfolio holdings and cash balances."""

        await asyncio.to_thread(
            self._apply_trade_sync,
            portfolio_id,
            stock_code,
            quantity,
            price,
            order_type,
            executed_at,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_snapshot_sync(self, portfolio_id: str) -> Optional[Dict[str, Any]]:
        pid = uuid.UUID(str(portfolio_id))
        with self._session_factory() as session:
            portfolio = session.query(Portfolio).filter(Portfolio.portfolio_id == pid).first()
            if not portfolio:
                return None

            positions = (
                session.query(Position)
                .filter(Position.portfolio_id == pid)
                .order_by(Position.stock_code.asc())
                .all()
            )

            # 디버깅 로그
            logger.info(f"🔍 [PortfolioService] DB 조회:")
            logger.info(f"  - Portfolio ID: {pid}")
            logger.info(f"  - User ID: {portfolio.user_id if portfolio else 'N/A'}")
            logger.info(f"  - DB Positions Count: {len(positions)}개")

            stock_codes = [pos.stock_code for pos in positions if pos.stock_code and pos.stock_code.upper() != "CASH"]
            stocks: Dict[str, Stock] = {}
            if stock_codes:
                stocks = {
                    stock.stock_code: stock
                    for stock in session.query(Stock).filter(Stock.stock_code.in_(stock_codes))
                }

            profile: Dict[str, Any] = {}
            if portfolio.user_id:
                user_profile = (
                    session.query(UserProfile)
                    .filter(UserProfile.user_id == portfolio.user_id)
                    .first()
                )
                if user_profile:
                    profile = user_profile.to_dict()

                    # 레거시 호출부 호환용 필드 매핑
                    profile.setdefault("investment_goal", profile.get("investment_style"))
                    profile.setdefault("investment_horizon", profile.get("trading_style"))
                    profile.setdefault("automation_level", 2)

            holdings, sector_breakdown, cash_balance, total_market_value = self._build_holdings_snapshot(
                positions,
                stocks,
            )

            cash_balance_dec = cash_balance
            total_value_dec = self._decimal(portfolio.total_value)
            if total_value_dec is None or total_value_dec <= Decimal("0"):
                total_value_dec = total_market_value + cash_balance_dec

            if total_value_dec > 0:
                for holding in holdings:
                    if holding["stock_code"].upper() == "CASH":
                        holding["weight"] = float(cash_balance_dec / total_value_dec)
                    else:
                        mv = Decimal(str(holding.get("market_value", 0)))
                        holding["weight"] = float(mv / total_value_dec)

                # Normalize sector weights to sum <= 1
                for sector, weight in list(sector_breakdown.items()):
                    sector_breakdown[sector] = float(weight / total_value_dec)

            portfolio_data = {
                "portfolio_id": str(portfolio.portfolio_id),
                "user_id": str(portfolio.user_id) if portfolio.user_id else None,
                "total_value": self._to_float(total_value_dec),
                "cash_balance": self._to_float(cash_balance_dec),
                "invested_amount": self._to_float(portfolio.invested_amount),
                "holdings": holdings,
                "sectors": sector_breakdown,
                "currency": "KRW",
            }

            # 디버깅 로그 - 최종 결과
            logger.info(f"  - Total Value: {self._to_float(total_value_dec):,.0f}원")
            logger.info(f"  - Holdings Count: {len(holdings)}개")

            market_data: Dict[str, Any] = {
                "last_updated": datetime.utcnow().isoformat(),
            }

            if not profile.get("risk_tolerance") and holdings:
                profile["risk_tolerance"] = self._infer_risk_tolerance(holdings)

            return {
                "portfolio_data": portfolio_data,
                "market_data": market_data,
                "profile": profile,
            }

    def _build_holdings_snapshot(
        self,
        positions: Iterable[Position],
        stocks: Dict[str, Stock],
    ) -> tuple[List[Dict[str, Any]], Dict[str, float], Decimal, Decimal]:
        holdings: List[Dict[str, Any]] = []
        sector_totals: Dict[str, Decimal] = defaultdict(Decimal)
        cash_balance = Decimal("0")
        total_market_value = Decimal("0")

        for position in positions:
            quantity = position.quantity or 0
            avg_price = self._decimal(position.average_price, Decimal("0"))
            current_price = self._decimal(position.current_price, avg_price)
            market_value = self._decimal(position.market_value, current_price * quantity)

            stock_code = position.stock_code or "UNKNOWN"
            if stock_code.upper() == "CASH":
                cash_balance += market_value
            else:
                total_market_value += market_value

            stock = stocks.get(stock_code)
            stock_name = stock.stock_name if stock else stock_code
            sector = stock.sector if stock and stock.sector else ("현금" if stock_code.upper() == "CASH" else "기타")

            holding = {
                "position_id": str(position.position_id),
                "stock_code": stock_code,
                "stock_name": stock_name,
                "quantity": quantity,
                "average_price": self._to_float(avg_price),
                "current_price": self._to_float(current_price),
                "market_value": self._to_float(market_value),
                "unrealized_pnl": self._to_float(position.unrealized_pnl),
                "unrealized_pnl_rate": self._to_float(position.unrealized_pnl_rate),
                "sector": sector,
                "weight": self._to_float(position.weight),
            }
            holdings.append(holding)

            if stock_code.upper() != "CASH":
                sector_totals[sector] += market_value

        return holdings, sector_totals, cash_balance, total_market_value

    async def _compute_market_metrics(
        self,
        holdings: Iterable[Dict[str, Any]],
        *,
        lookback_days: int = 60,
    ) -> Dict[str, Any]:
        weights = {
            h["stock_code"]: h.get("weight", 0.0)
            for h in holdings
            if h.get("stock_code") and h.get("weight") and h["stock_code"].upper() != "CASH"
        }

        if not weights:
            return {}

        tasks = [stock_data_service.get_stock_price(code, days=lookback_days) for code in weights]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        frames: List[pd.Series] = []
        valid_codes: List[str] = []
        for code, df in zip(weights, results):
            if isinstance(df, Exception) or df is None:
                logger.debug("Skipping volatility calc for %s: data unavailable", code)
                continue
            try:
                series = df["Close"].rename(code)
            except Exception:  # pragma: no cover - defensive
                continue
            frames.append(series)
            valid_codes.append(code)

        if not frames:
            return {}

        price_df = pd.concat(frames, axis=1).dropna()
        returns_df = price_df.pct_change().dropna()
        if returns_df.empty:
            return {}

        weight_vector = [weights[code] for code in valid_codes]
        weighted_returns = returns_df[valid_codes].mul(weight_vector, axis=1).sum(axis=1)

        portfolio_volatility = float(weighted_returns.std())
        var_95 = portfolio_volatility * 1.65
        average_return = float(weighted_returns.mean())

        daily_risk_free_rate = DEFAULT_RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
        sharpe_ratio = None
        if portfolio_volatility > 0:
            excess_return = average_return - daily_risk_free_rate
            sharpe_ratio = excess_return / portfolio_volatility

        cumulative = (1 + weighted_returns).cumprod()
        if cumulative.empty:
            max_drawdown = None
        else:
            running_max = cumulative.cummax()
            drawdown = (running_max - cumulative) / running_max
            max_drawdown = float(drawdown.max()) if not drawdown.empty else None

        beta_map = await self._estimate_betas(returns_df, valid_codes)

        return {
            "portfolio_volatility": portfolio_volatility,
            "var_95": var_95,
            "average_daily_return": average_return,
            "sharpe_ratio": float(sharpe_ratio) if sharpe_ratio is not None else None,
            "max_drawdown_estimate": max_drawdown,
            "beta": beta_map,
            "observations": len(weighted_returns),
            "returns_window": weighted_returns.tolist(),
            "returns_dates": [idx.strftime("%Y-%m-%d") for idx in weighted_returns.index],
        }

    async def _estimate_betas(
        self,
        returns_df: pd.DataFrame,
        codes: List[str],
    ) -> Dict[str, float]:
        try:
            kospi = await stock_data_service.get_stock_price("KS11", days=len(returns_df) + 10)
        except Exception:
            kospi = None

        if kospi is None:
            return {code: 1.0 for code in codes}

        try:
            index_returns = kospi["Close"].pct_change().dropna()
        except Exception:  # pragma: no cover - defensive
            return {code: 1.0 for code in codes}

        index_returns = index_returns.loc[index_returns.index.intersection(returns_df.index)]
        if index_returns.empty or index_returns.var() == 0:
            return {code: 1.0 for code in codes}

        betas: Dict[str, float] = {}
        variance = index_returns.var()
        for code in codes:
            series = returns_df[code].loc[index_returns.index]
            covariance = series.cov(index_returns)
            beta = covariance / variance if variance else 1.0
            betas[code] = float(beta) if beta == beta else 1.0  # NaN check

        return betas or {code: 1.0 for code in codes}

    def _apply_trade_sync(
        self,
        portfolio_id: str,
        stock_code: str,
        quantity: int,
        price: float,
        order_type: str,
        executed_at: Optional[datetime] = None,
    ) -> None:
        pid = uuid.UUID(str(portfolio_id))
        qty = int(quantity)
        if qty <= 0:
            return

        order_type_upper = order_type.upper()
        price_dec = self._decimal(price, default=None)
        if price_dec is None:
            raise ValueError("Execution price is required to apply a trade")

        with self._session_factory() as session:
            portfolio = session.query(Portfolio).filter(Portfolio.portfolio_id == pid).with_for_update().first()
            if not portfolio:
                raise PortfolioNotFoundError(f"Portfolio {portfolio_id} not found")

            position = (
                session.query(Position)
                .filter(Position.portfolio_id == pid, Position.stock_code == stock_code)
                .with_for_update()
                .first()
            )

            total_amount = price_dec * qty
            cash_balance = self._decimal(portfolio.cash_balance, Decimal("0"))
            invested_amount = self._decimal(portfolio.invested_amount, Decimal("0"))

            if order_type_upper == "BUY":
                cash_balance -= total_amount
                invested_amount += total_amount
                if position:
                    current_qty = position.quantity or 0
                    current_avg = self._decimal(position.average_price, price_dec)
                    new_qty = current_qty + qty
                    total_cost = current_avg * current_qty + price_dec * qty
                    position.quantity = new_qty
                    position.average_price = total_cost / new_qty if new_qty else price_dec
                else:
                    position = Position(
                        portfolio_id=pid,
                        stock_code=stock_code,
                        quantity=qty,
                        average_price=price_dec,
                        current_price=price_dec,
                        market_value=price_dec * qty,
                    )
                    session.add(position)
            elif order_type_upper == "SELL":
                cash_balance += total_amount
                invested_amount -= total_amount
                if not position:
                    raise InsufficientHoldingsError(f"No holdings available for {stock_code}")
                current_qty = position.quantity or 0
                new_qty = current_qty - qty
                if new_qty < 0:
                    raise InsufficientHoldingsError(f"Sell quantity exceeds holdings for {stock_code}")
                if new_qty == 0:
                    session.delete(position)
                    position = None
                else:
                    position.quantity = new_qty
            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            if position:
                position.current_price = price_dec
                position.market_value = price_dec * position.quantity
                position.last_updated_at = executed_at or datetime.utcnow()

            portfolio.cash_balance = cash_balance
            portfolio.invested_amount = invested_amount

            # Recompute portfolio total and weights
            all_positions = session.query(Position).filter(Position.portfolio_id == pid).all()
            total_market = Decimal("0")
            for pos in all_positions:
                mv = self._decimal(pos.market_value, self._decimal(pos.current_price, Decimal("0")) * (pos.quantity or 0))
                pos.market_value = mv
                total_market += mv

            total_value = total_market + cash_balance
            portfolio.total_value = total_value

        if total_value > 0:
            for pos in all_positions:
                mv = self._decimal(pos.market_value, Decimal("0"))
                pos.weight = mv / total_value if total_value else None

            session.commit()

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _sync_kis_balance_sync(
        self,
        portfolio_id: str,
        balance: Dict[str, Any],
    ) -> None:
        pid = uuid.UUID(str(portfolio_id))
        with self._session_factory() as session:
            portfolio = session.query(Portfolio).filter(Portfolio.portfolio_id == pid).with_for_update().first()
            if not portfolio:
                raise PortfolioNotFoundError(f"Portfolio {portfolio_id} not found")

            stocks: List[Dict[str, Any]] = balance.get("stocks", []) or []
            cash_balance = self._decimal(balance.get("cash_balance"), Decimal("0"))
            total_assets = self._decimal(balance.get("total_assets"), Decimal("0"))

            existing_positions = {
                position.stock_code: position
                for position in session.query(Position).filter(Position.portfolio_id == pid)
            }
            seen_codes: set[str] = set()

            for stock in stocks:
                code = stock.get("stock_code")
                if not code:
                    continue

                quantity = int(stock.get("quantity") or 0)
                if quantity <= 0:
                    stale = existing_positions.get(code)
                    if stale:
                        session.delete(stale)
                    continue

                seen_codes.add(code)

                # Stock 테이블 upsert (KIS API에서 받은 종목명 저장)
                stock_name = stock.get("stock_name", "")
                if stock_name:
                    stock_record = session.query(Stock).filter(Stock.stock_code == code).first()
                    if not stock_record:
                        # 신규 종목 등록
                        stock_record = Stock(
                            stock_code=code,
                            stock_name=stock_name,
                            market="KOSPI"  # 기본값, 추후 KIS API에서 시장 정보 추가 가능
                        )
                        session.add(stock_record)
                        logger.debug(f"📝 [Portfolio] Stock 테이블에 종목 추가: {code} - {stock_name}")
                    else:
                        # 기존 종목명 업데이트 (변경된 경우만)
                        if stock_record.stock_name != stock_name:
                            stock_record.stock_name = stock_name
                            logger.debug(f"🔄 [Portfolio] Stock 종목명 업데이트: {code} - {stock_name}")

                avg_price = self._decimal(stock.get("avg_price"), Decimal("0"))
                current_price = self._decimal(stock.get("current_price"), avg_price)
                market_value = self._decimal(
                    stock.get("eval_amount"),
                    (current_price or Decimal("0")) * quantity,
                )
                profit_loss = self._decimal(stock.get("profit_loss"), Decimal("0"))
                profit_rate = self._decimal(stock.get("profit_rate"), Decimal("0"))

                position = existing_positions.get(code)
                if not position:
                    position = Position(portfolio_id=pid, stock_code=code)
                    session.add(position)

                position.quantity = quantity
                position.average_price = avg_price
                position.current_price = current_price
                position.market_value = market_value
                position.unrealized_pnl = profit_loss
                position.unrealized_pnl_rate = profit_rate
                position.last_updated_at = datetime.utcnow()

            for code, position in list(existing_positions.items()):
                if code not in seen_codes:
                    session.delete(position)

            session.flush()

            positions = session.query(Position).filter(Position.portfolio_id == pid).all()
            total_market_value = Decimal("0")
            for pos in positions:
                mv = self._decimal(pos.market_value, Decimal("0"))
                pos.market_value = mv
                total_market_value += mv

            total_value = total_assets if total_assets and total_assets > 0 else total_market_value + cash_balance
            invested_amount = total_value - cash_balance

            portfolio.cash_balance = cash_balance
            portfolio.total_value = total_value
            portfolio.invested_amount = invested_amount if invested_amount >= 0 else Decimal("0")

            if total_value > 0:
                for pos in positions:
                    mv = self._decimal(pos.market_value, Decimal("0"))
                    pos.weight = (mv / total_value) if mv is not None else None

            session.commit()

    def _decimal(self, value: Any, default: Optional[Decimal] = Decimal("0")) -> Optional[Decimal]:
        if value is None:
            return default
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except Exception:
            return default

    def _to_float(self, value: Any, default: Optional[float] = None) -> Optional[float]:
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _infer_risk_tolerance(self, holdings: Iterable[Dict[str, Any]]) -> str:
        growth_ratio = sum(h.get("weight", 0.0) for h in holdings if h.get("sector") in {"반도체", "IT서비스", "기술"})
        if growth_ratio >= 0.6:
            return "aggressive"
        if growth_ratio >= 0.4:
            return "moderate"
        return "conservative"

    def _default_snapshot(self) -> PortfolioSnapshot:
        holdings = [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "quantity": 50,
                "average_price": 60000.0,
                "current_price": 72000.0,
                "market_value": 3_600_000.0,
                "weight": 0.36,
                "sector": "반도체",
            },
            {
                "stock_code": "000660",
                "stock_name": "SK하이닉스",
                "quantity": 20,
                "average_price": 95000.0,
                "current_price": 120000.0,
                "market_value": 2_400_000.0,
                "weight": 0.24,
                "sector": "반도체",
            },
            {
                "stock_code": "005380",
                "stock_name": "현대차",
                "quantity": 10,
                "average_price": 200000.0,
                "current_price": 210000.0,
                "market_value": 2_100_000.0,
                "weight": 0.21,
                "sector": "자동차",
            },
            {
                "stock_code": "CASH",
                "stock_name": "현금",
                "quantity": 0,
                "average_price": 1.0,
                "current_price": 1.0,
                "market_value": 1_900_000.0,
                "weight": 0.19,
                "sector": "현금",
            },
        ]

        portfolio_data = {
            "portfolio_id": "portfolio_mock_fallback",
            "user_id": None,
            "total_value": 10_000_000.0,
            "cash_balance": 1_900_000.0,
            "invested_amount": 8_100_000.0,
            "holdings": holdings,
            "sectors": {
                "반도체": 0.60,
                "자동차": 0.21,
                "현금": 0.19,
            },
            "currency": "KRW",
        }

        market_data: Dict[str, Any] = {
            "portfolio_volatility": 0.08,
            "var_95": 0.132,
            "max_drawdown_estimate": 0.18,
            "beta": {"005930": 1.1, "000660": 1.3, "005380": 0.9},
            "last_updated": datetime.utcnow().isoformat(),
        }

        profile = {
            "risk_tolerance": "moderate",
            "investment_goal": "mid_long_term",
            "investment_horizon": "3_5y",
            "automation_level": 2,
        }

        return PortfolioSnapshot(
            portfolio_data=portfolio_data,
            market_data=market_data,
            profile=profile,
        )


portfolio_service = PortfolioService()
