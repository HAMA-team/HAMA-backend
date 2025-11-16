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
            logger.error(f"  - user_id: {user_id}")
            logger.error(f"  - portfolio_id: {portfolio_id}")

            # 🔍 KIS API 동기화 시도 (fallback)
            logger.info("[PortfolioService] KIS API 동기화를 시도합니다...")
            try:
                synced_snapshot = await self.sync_with_kis(user_id=user_id)
                if synced_snapshot:
                    logger.info("✅ [PortfolioService] KIS API 동기화 성공")
                    return synced_snapshot
            except Exception as sync_exc:
                logger.error(f"❌ [PortfolioService] KIS 동기화도 실패: {sync_exc}", exc_info=True)

            raise PortfolioNotFoundError(
                f"사용자 '{user_id}'의 포트폴리오를 찾을 수 없습니다. "
                "KIS API 동기화도 실패했습니다. 먼저 종목을 매수하여 포트폴리오를 만들어주세요."
            )

        base_snapshot = await asyncio.to_thread(self._load_snapshot_sync, resolved_id)
        if base_snapshot is None:
            logger.error("[PortfolioService] 포트폴리오 데이터를 로드할 수 없습니다")
            logger.error(f"  - resolved_id: {resolved_id}")

            # 🔍 KIS API 동기화 시도 (fallback)
            logger.info("[PortfolioService] KIS API 동기화를 시도합니다...")
            try:
                synced_snapshot = await self.sync_with_kis(user_id=user_id, portfolio_id=resolved_id)
                if synced_snapshot:
                    logger.info("✅ [PortfolioService] KIS API 동기화 성공")
                    return synced_snapshot
            except Exception as sync_exc:
                logger.error(f"❌ [PortfolioService] KIS 동기화도 실패: {sync_exc}", exc_info=True)

            raise PortfolioNotFoundError(
                f"포트폴리오 ID '{resolved_id}'의 데이터를 찾을 수 없습니다. "
                "KIS API 동기화도 실패했습니다."
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

    async def simulate_trade(
        self,
        *,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        stock_code: str,
        action: str,
        quantity: int,
        price: float,
        lookback_days: int = 60,
    ) -> Dict[str, Any]:
        """
        매매 실행 전 포트폴리오 변화 시뮬레이션

        Args:
            user_id: 사용자 ID
            portfolio_id: 포트폴리오 ID
            stock_code: 종목 코드
            action: 매매 방향 ("buy" | "sell")
            quantity: 수량
            price: 가격
            lookback_days: 리스크 계산용 과거 데이터 기간

        Returns:
            {
                "portfolio_before": 매매 전 포트폴리오,
                "portfolio_after": 매매 후 포트폴리오,
                "risk_before": 매매 전 리스크,
                "risk_after": 매매 후 리스크,
            }
        """
        # 현재 포트폴리오 조회
        logger.info(f"📊 [Portfolio/Simulate] 포트폴리오 조회 시작:")
        logger.info(f"  - user_id: {user_id}")
        logger.info(f"  - portfolio_id: {portfolio_id}")
        logger.info(f"  - stock_code: {stock_code}, action: {action}, quantity: {quantity}, price: {price}")

        try:
            snapshot = await self.get_portfolio_snapshot(
                user_id=user_id,
                portfolio_id=portfolio_id,
                lookback_days=lookback_days,
            )
        except PortfolioNotFoundError as exc:
            logger.error(f"❌ [Portfolio/Simulate] 포트폴리오 조회 실패: {exc}")
            raise
        except Exception as exc:
            logger.error(f"❌ [Portfolio/Simulate] 예기치 않은 오류: {exc}", exc_info=True)
            raise

        if not snapshot:
            logger.error("❌ [Portfolio/Simulate] snapshot이 None입니다")
            raise PortfolioNotFoundError("포트폴리오를 찾을 수 없습니다")

        portfolio_before = snapshot.portfolio_data
        market_data = snapshot.market_data

        # 매매 전 리스크 추출
        risk_before = {
            "portfolio_volatility": market_data.get("portfolio_volatility"),
            "var_95": market_data.get("var_95"),
            "sharpe_ratio": market_data.get("sharpe_ratio"),
            "max_drawdown_estimate": market_data.get("max_drawdown_estimate"),
            "beta": market_data.get("beta", {}),
        }

        # 매매 시뮬레이션 (holdings 복사 후 적용)
        holdings_before = portfolio_before.get("holdings", [])
        total_value = Decimal(str(portfolio_before.get("total_value", 0)))
        cash_balance = Decimal(str(portfolio_before.get("cash_balance", 0)))

        # 새 holdings 계산
        holdings_after = self._simulate_holdings_change(
            holdings=holdings_before,
            stock_code=stock_code,
            action=action.upper(),
            quantity=quantity,
            price=Decimal(str(price)),
            cash_balance=cash_balance,
        )

        # 매매 후 총 자산 및 현금 계산
        total_amount = Decimal(str(price)) * quantity
        if action.upper() == "BUY":
            cash_after = cash_balance - total_amount
            total_value_after = total_value  # 현금 → 주식 이동 (총액은 동일)
        else:  # SELL
            cash_after = cash_balance + total_amount
            total_value_after = total_value

        # 비중 재계산
        if total_value_after > 0:
            for holding in holdings_after:
                if holding["stock_code"].upper() == "CASH":
                    holding["weight"] = float(cash_after / total_value_after)
                else:
                    mv = Decimal(str(holding.get("market_value", 0)))
                    holding["weight"] = float(mv / total_value_after)

        portfolio_after = {
            **portfolio_before,
            "holdings": holdings_after,
            "cash_balance": float(cash_after),
            "total_value": float(total_value_after),
        }

        # 매매 후 리스크 재계산
        try:
            risk_after_metrics = await self._compute_market_metrics(
                holdings_after,
                lookback_days=lookback_days,
            )
            risk_after = {
                "portfolio_volatility": risk_after_metrics.get("portfolio_volatility"),
                "var_95": risk_after_metrics.get("var_95"),
                "sharpe_ratio": risk_after_metrics.get("sharpe_ratio"),
                "max_drawdown_estimate": risk_after_metrics.get("max_drawdown_estimate"),
                "beta": risk_after_metrics.get("beta", {}),
            }
        except Exception as exc:  # pragma: no cover - 리스크 계산 실패 시 None
            logger.warning("매매 후 리스크 계산 실패: %s", exc)
            risk_after = {
                "portfolio_volatility": None,
                "var_95": None,
                "sharpe_ratio": None,
                "max_drawdown_estimate": None,
                "beta": {},
            }

        # 🔍 디버깅: 시뮬레이션 결과 확인
        logger.info("✅ [Portfolio/Simulate] 시뮬레이션 완료:")
        logger.info(f"  - portfolio_before holdings: {len(portfolio_before.get('holdings', []))}개")
        logger.info(f"  - portfolio_before cash: {portfolio_before.get('cash_balance', 0):,}원")
        logger.info(f"  - portfolio_after holdings: {len(portfolio_after.get('holdings', []))}개")
        logger.info(f"  - portfolio_after cash: {portfolio_after.get('cash_balance', 0):,}원")
        logger.info(f"  - risk_before: volatility={risk_before.get('portfolio_volatility')}, var_95={risk_before.get('var_95')}")
        logger.info(f"  - risk_after: volatility={risk_after.get('portfolio_volatility')}, var_95={risk_after.get('var_95')}")

        return {
            "portfolio_before": portfolio_before,
            "portfolio_after": portfolio_after,
            "risk_before": risk_before,
            "risk_after": risk_after,
        }

    def _simulate_holdings_change(
        self,
        *,
        holdings: List[Dict[str, Any]],
        stock_code: str,
        action: str,
        quantity: int,
        price: Decimal,
        cash_balance: Decimal,
    ) -> List[Dict[str, Any]]:
        """
        Holdings 리스트를 복사해서 매매 시뮬레이션 적용

        Args:
            holdings: 현재 holdings
            stock_code: 종목 코드
            action: "BUY" | "SELL"
            quantity: 수량
            price: 가격
            cash_balance: 현금 잔액

        Returns:
            새 holdings 리스트 (원본 수정 안 함)
        """
        import copy
        new_holdings = copy.deepcopy(holdings)

        # 해당 종목 찾기
        target_holding = None
        for holding in new_holdings:
            if holding.get("stock_code") == stock_code:
                target_holding = holding
                break

        if action == "BUY":
            if target_holding:
                # 기존 보유 종목 추가 매수
                current_qty = target_holding.get("quantity", 0)
                current_avg = Decimal(str(target_holding.get("average_price", 0)))
                new_qty = current_qty + quantity
                total_cost = current_avg * current_qty + price * quantity
                new_avg_price = total_cost / new_qty if new_qty > 0 else price

                target_holding["quantity"] = new_qty
                target_holding["average_price"] = float(new_avg_price)
                target_holding["current_price"] = float(price)
                target_holding["market_value"] = float(price * new_qty)
            else:
                # 신규 매수
                new_holdings.append({
                    "stock_code": stock_code,
                    "stock_name": stock_code,  # 이름은 나중에 조회 가능
                    "quantity": quantity,
                    "average_price": float(price),
                    "current_price": float(price),
                    "market_value": float(price * quantity),
                    "weight": 0.0,  # 나중에 재계산
                    "sector": "기타",
                    "unrealized_pnl": 0.0,
                    "unrealized_pnl_rate": 0.0,
                })

        elif action == "SELL":
            if not target_holding:
                raise InsufficientHoldingsError(f"보유하지 않은 종목입니다: {stock_code}")

            current_qty = target_holding.get("quantity", 0)
            new_qty = current_qty - quantity

            if new_qty < 0:
                raise InsufficientHoldingsError(
                    f"매도 수량이 보유 수량을 초과합니다: {stock_code} (보유: {current_qty}, 매도: {quantity})"
                )

            if new_qty == 0:
                # 전량 매도 - holdings에서 제거
                new_holdings.remove(target_holding)
            else:
                # 일부 매도
                target_holding["quantity"] = new_qty
                target_holding["current_price"] = float(price)
                target_holding["market_value"] = float(price * new_qty)

        return new_holdings

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

            holdings, sector_breakdown, cash_balance, total_market_value = self._build_holdings_snapshot(
                positions,
                stocks,
            )

            # portfolio.cash_balance를 우선 사용 (KIS 동기화는 CASH position을 만들지 않음)
            portfolio_cash = self._decimal(portfolio.cash_balance, Decimal("0"))
            cash_balance_dec = portfolio_cash if portfolio_cash > 0 else cash_balance
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
            # 지수 전용 메서드 사용 (get_stock_price는 종목용)
            kospi = await stock_data_service.get_market_index("KOSPI", days=len(returns_df) + 10)
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
        }

        return PortfolioSnapshot(
            portfolio_data=portfolio_data,
            market_data=market_data,
            profile=profile,
        )


# ==================== Risk Calculation Functions (from Risk Agent) ====================

def calculate_concentration_risk_metrics(
    holdings: List[Dict[str, Any]],
    sectors: Dict[str, float],
) -> Dict[str, Any]:
    """
    집중도 리스크 계산 (Risk Agent에서 이식)

    Args:
        holdings: 보유 종목 리스트 [{"stock_code": str, "weight": float, ...}, ...]
        sectors: 섹터별 비중 {"IT": 0.5, ...}

    Returns:
        집중도 리스크 분석 결과
    """
    # HHI (Herfindahl-Hirschman Index) 계산
    hhi = 0.0
    top_holding = ("N/A", 0.0)

    for holding in holdings:
        weight = float(holding.get("weight") or 0.0)
        hhi += weight ** 2
        if weight > top_holding[1]:
            stock_name = holding.get("stock_name") or holding.get("stock_code", "N/A")
            top_holding = (stock_name, weight)

    # 최대 섹터 비중
    top_sector = ("N/A", 0.0)
    for sector_name, sector_weight in sectors.items():
        weight_float = float(sector_weight)
        if weight_float > top_sector[1]:
            top_sector = (sector_name, weight_float)

    # 경고 메시지 생성
    warnings = []
    if top_holding[1] > 0.30:
        warnings.append(
            f"{top_holding[0]} 비중이 {top_holding[1]:.0%}로 높습니다 (권장: 25% 이하)"
        )
    if top_sector[1] > 0.50:
        warnings.append(
            f"{top_sector[0]} 섹터 비중이 {top_sector[1]:.0%}로 높습니다 (권장: 50% 이하)"
        )

    # 리스크 레벨 판단
    level = "high" if hhi > 0.25 else "medium" if hhi > 0.15 else "low"

    return {
        "hhi": float(hhi),
        "level": level,
        "warnings": warnings,
        "top_holding": {
            "name": top_holding[0],
            "weight": float(top_holding[1]),
        },
        "top_sector": {
            "name": top_sector[0],
            "weight": float(top_sector[1]),
        },
        "sector_breakdown": {k: float(v) for k, v in sectors.items()},
    }


def calculate_market_risk_metrics(
    portfolio_data: Dict[str, Any],
    market_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    시장 리스크 계산 (Risk Agent에서 이식)

    Args:
        portfolio_data: 포트폴리오 데이터
        market_data: 시장 데이터 (volatility, var_95, beta 등)

    Returns:
        시장 리스크 분석 결과
    """
    holdings = portfolio_data.get("holdings", [])

    # 시장 데이터에서 지표 추출
    volatility = market_data.get("portfolio_volatility")
    var_95 = market_data.get("var_95")
    max_drawdown = market_data.get("max_drawdown_estimate")
    beta_map = market_data.get("beta") or {}

    # Fallback: 시장 데이터가 없으면 재계산
    if volatility is None or var_95 is None:
        if not holdings:
            volatility, var_95, max_drawdown = 0.0, 0.0, None
        else:
            average_beta = sum(float(h.get("beta") or 1.0) for h in holdings) / len(holdings)
            average_weight = sum(float(h.get("weight") or 0.0) for h in holdings)
            volatility = max(0.05, average_beta * 0.15 * max(average_weight, 1.0))
            var_95 = volatility * 1.65
            max_drawdown = var_95 * 1.8

    # 포트폴리오 베타 계산
    portfolio_beta = sum(
        (h.get("weight") or 0.0) * beta_map.get(h.get("stock_code"), 1.0)
        for h in holdings
    ) or 1.0

    # 리스크 레벨 판단
    risk_level = "high" if (var_95 or 0) > 0.10 else "medium" if (var_95 or 0) > 0.05 else "low"

    return {
        "portfolio_volatility": volatility,
        "portfolio_beta": portfolio_beta,
        "var_95": var_95,
        "max_drawdown_estimate": max_drawdown,
        "risk_level": risk_level,
    }


async def calculate_comprehensive_portfolio_risk(
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    종합 포트폴리오 리스크 계산

    Risk Agent의 모든 Specialist 로직을 통합한 단일 함수

    Args:
        user_id: 사용자 ID
        portfolio_id: 포트폴리오 ID

    Returns:
        종합 리스크 분석 결과
        {
            "concentration_risk": {...},
            "market_risk": {...},
            "overall_assessment": {...}
        }
    """
    logger.info("🔍 [PortfolioService/Risk] 종합 리스크 분석 시작")

    try:
        # 1. 포트폴리오 스냅샷 조회
        snapshot = await portfolio_service.get_portfolio_snapshot(
            user_id=user_id,
            portfolio_id=portfolio_id
        )

        if not snapshot:
            raise PortfolioNotFoundError("포트폴리오를 찾을 수 없습니다")

        portfolio_data = snapshot.portfolio_data
        market_data = snapshot.market_data
        holdings = portfolio_data.get("holdings", [])
        sectors = portfolio_data.get("sectors", {})

        # 2. 집중도 리스크 계산
        concentration_risk = calculate_concentration_risk_metrics(holdings, sectors)

        # 3. 시장 리스크 계산
        market_risk = calculate_market_risk_metrics(portfolio_data, market_data)

        # 4. 종합 평가
        # 리스크 레벨 종합 (concentration과 market 중 더 높은 것)
        risk_levels = {"low": 1, "medium": 2, "high": 3}
        concentration_level = risk_levels.get(concentration_risk["level"], 2)
        market_level = risk_levels.get(market_risk["risk_level"], 2)
        overall_level_num = max(concentration_level, market_level)
        overall_level = {1: "low", 2: "medium", 3: "high"}[overall_level_num]

        # 종합 메시지
        summary_parts = []
        if concentration_risk["warnings"]:
            summary_parts.append(f"집중도: {', '.join(concentration_risk['warnings'][:2])}")
        if market_risk["var_95"]:
            summary_parts.append(f"VaR(95%): {market_risk['var_95']*100:.1f}%")

        overall_assessment = {
            "risk_level": overall_level,
            "summary": " | ".join(summary_parts) if summary_parts else "리스크 양호",
            "requires_attention": overall_level in ("medium", "high"),
            "key_recommendations": [],
        }

        # 권장사항 생성
        if concentration_risk["top_holding"]["weight"] > 0.30:
            overall_assessment["key_recommendations"].append(
                f"{concentration_risk['top_holding']['name']} 비중 축소 권장"
            )
        if concentration_risk["top_sector"]["weight"] > 0.50:
            overall_assessment["key_recommendations"].append(
                f"{concentration_risk['top_sector']['name']} 섹터 분산 권장"
            )
        if market_risk["var_95"] and market_risk["var_95"] > 0.10:
            overall_assessment["key_recommendations"].append(
                "변동성이 높습니다. 방어적 자산 편입 고려"
            )

        logger.info(
            "✅ [PortfolioService/Risk] 종합 리스크 분석 완료: %s",
            overall_level
        )

        return {
            "concentration_risk": concentration_risk,
            "market_risk": market_risk,
            "overall_assessment": overall_assessment,
        }

    except Exception as e:
        logger.error("❌ [PortfolioService/Risk] 리스크 분석 실패: %s", e, exc_info=True)
        raise



portfolio_service = PortfolioService()
