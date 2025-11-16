"""Portfolio Optimizer - 동적 포트폴리오 비중 계산

Strategy Agent 결과를 기반으로 실제 포트폴리오 목표 비중을 계산합니다.
Mock 데이터 없이 실제 데이터와 전략 결과만 사용합니다.
"""

import logging
from typing import Dict, List, Optional
from decimal import Decimal

from src.schemas.portfolio import PortfolioHolding
from src.services.stock_data_service import stock_data_service

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """
    포트폴리오 최적화기

    Strategy Agent 결과를 활용하여 목표 비중을 동적으로 계산합니다.
    """

    def __init__(self):
        pass

    async def calculate_target_allocation(
        self,
        current_holdings: List[PortfolioHolding],
        strategy_result: Optional[Dict] = None,
        risk_profile: str = "moderate",
        total_value: float = 0.0
    ) -> tuple[List[PortfolioHolding], Dict[str, float]]:
        """
        목표 비중 계산

        Args:
            current_holdings: 현재 보유 종목
            strategy_result: Strategy Agent 결과 (섹터 로테이션, 자산 배분)
            risk_profile: 위험 성향
            total_value: 총 자산 가치

        Returns:
            tuple: (목표 비중 리스트, 성과 지표)
        """
        logger.info(f"🧮 [Optimizer] 목표 비중 계산 시작 (risk={risk_profile})")

        # 1. Strategy 결과에서 자산 배분 비율 추출
        asset_allocation = self._extract_asset_allocation(strategy_result, risk_profile)
        equity_ratio = asset_allocation["equity"]
        cash_ratio = asset_allocation["cash"]

        logger.info(f"📊 [Optimizer] 자산 배분: 주식 {equity_ratio:.0%}, 현금 {cash_ratio:.0%}")

        # 2. 섹터 선호도 추출 (Strategy 결과)
        sector_preferences = self._extract_sector_preferences(strategy_result)

        # 3. 현재 보유 종목 기반 목표 비중 계산
        proposed_holdings = await self._calculate_stock_weights(
            current_holdings=current_holdings,
            equity_ratio=equity_ratio,
            sector_preferences=sector_preferences,
            total_value=total_value
        )

        # 4. 현금 추가
        if cash_ratio > 0:
            proposed_holdings.append({
                "stock_code": "CASH",
                "stock_name": "예수금",
                "weight": round(cash_ratio, 4),
                "value": round(total_value * cash_ratio, -3) if total_value else 0.0,
            })

        # 5. 성과 지표 계산
        metrics = await self._calculate_portfolio_metrics(
            proposed_holdings=proposed_holdings,
            risk_profile=risk_profile
        )

        logger.info(f"✅ [Optimizer] 목표 비중 계산 완료: {len(proposed_holdings)}개 자산")

        return proposed_holdings, metrics

    def _extract_asset_allocation(
        self,
        strategy_result: Optional[Dict],
        risk_profile: str
    ) -> Dict[str, float]:
        """
        Strategy 결과에서 자산 배분 비율 추출

        Returns:
            {"equity": 0.7, "cash": 0.3}
        """
        # Strategy Agent 결과 우선 반영
        if strategy_result and "asset_allocation" in strategy_result:
            allocation = strategy_result["asset_allocation"]
            return {
                "equity": float(allocation.get("stocks", 0.70)),
                "cash": float(allocation.get("cash", 0.30))
            }

        # Fallback: 위험 성향별 기본 비율
        default_allocations = {
            "conservative": {"equity": 0.50, "cash": 0.50},
            "moderate": {"equity": 0.70, "cash": 0.30},
            "aggressive": {"equity": 0.85, "cash": 0.15},
        }

        return default_allocations.get(risk_profile, default_allocations["moderate"])

    def _extract_sector_preferences(
        self,
        strategy_result: Optional[Dict]
    ) -> Dict[str, str]:
        """
        Strategy 결과에서 섹터 선호도 추출

        Returns:
            {"IT/전기전자": "overweight", "반도체": "overweight", ...}
        """
        preferences = {}

        if not strategy_result or "sector_strategy" not in strategy_result:
            return preferences

        sector_strategy = strategy_result["sector_strategy"]

        # Overweight 섹터
        for sector in sector_strategy.get("overweight", []):
            preferences[sector] = "overweight"

        # Underweight 섹터
        for sector in sector_strategy.get("underweight", []):
            preferences[sector] = "underweight"

        logger.info(f"🎯 [Optimizer] 섹터 선호도: {preferences}")

        return preferences

    async def _calculate_stock_weights(
        self,
        current_holdings: List[PortfolioHolding],
        equity_ratio: float,
        sector_preferences: Dict[str, str],
        total_value: float
    ) -> List[PortfolioHolding]:
        """
        개별 종목 목표 비중 계산

        전략:
        1. 현재 보유 종목 유지 (급격한 변화 방지)
        2. Overweight 섹터 → 비중 증가 (+10~20%p)
        3. Underweight 섹터 → 비중 감소 (-10~20%p)
        4. 제약 조건 검증 및 적용
        """
        # CASH 제외
        stock_holdings = [h for h in current_holdings if h.get("stock_code") != "CASH"]

        if not stock_holdings:
            logger.warning("⚠️ [Optimizer] 보유 종목 없음, 빈 리스트 반환")
            return []

        # 현재 주식 총 비중
        current_equity_weight = sum(h.get("weight", 0) for h in stock_holdings)

        if current_equity_weight == 0:
            # 보유 종목이 있지만 비중이 0 → 균등 배분
            equal_weight = equity_ratio / len(stock_holdings)
            proposed = []
            for holding in stock_holdings:
                proposed.append({
                    "stock_code": holding["stock_code"],
                    "stock_name": holding["stock_name"],
                    "weight": round(equal_weight, 4),
                    "value": round(total_value * equal_weight, -3) if total_value else 0.0,
                    "sector": holding.get("sector", "기타"),
                })
            return proposed

        # 1. 실제 섹터 정보 수집
        holdings_with_sectors = []
        for holding in stock_holdings:
            stock_code = holding["stock_code"]

            # 섹터 정보 조회 (stock_data_service 활용)
            sector = await self._get_stock_sector(stock_code)

            holdings_with_sectors.append({
                **holding,
                "sector": sector,
            })

        # 2. 비중 조정 (기본 스케일링)
        scale_factor = equity_ratio / current_equity_weight

        proposed = []
        for holding in holdings_with_sectors:
            current_weight = holding.get("weight", 0)
            new_weight = current_weight * scale_factor
            sector = holding.get("sector", "기타")

            # 3. 섹터 선호도 반영
            if sector_preferences:
                preference = sector_preferences.get(sector)

                if preference == "overweight":
                    # Overweight → 비중 15% 증가
                    new_weight *= 1.15
                    logger.info(f"  - {holding['stock_name']} ({sector}): overweight → 비중 +15%")
                elif preference == "underweight":
                    # Underweight → 비중 15% 감소
                    new_weight *= 0.85
                    logger.info(f"  - {holding['stock_name']} ({sector}): underweight → 비중 -15%")

            proposed.append({
                "stock_code": holding["stock_code"],
                "stock_name": holding["stock_name"],
                "weight": new_weight,
                "value": round(total_value * new_weight, -3) if total_value else 0.0,
                "sector": sector,
            })

        # 4. 제약 조건 검증 및 정규화
        proposed = self._apply_constraints(proposed, equity_ratio)

        return proposed

    async def _get_stock_sector(self, stock_code: str) -> str:
        """
        종목의 섹터 정보 조회

        Args:
            stock_code: 종목 코드

        Returns:
            섹터명 (예: "IT/전기전자", "자동차", "기타")
        """
        try:
            # stock_data_service를 통해 종목 정보 조회
            stock_info = await stock_data_service.get_stock_info(stock_code)

            if stock_info and "sector" in stock_info:
                return stock_info["sector"]

            # Fallback: 기본값
            logger.warning(f"⚠️ [Optimizer] {stock_code} 섹터 정보 없음, '기타'로 분류")
            return "기타"

        except Exception as e:
            logger.warning(f"⚠️ [Optimizer] {stock_code} 섹터 조회 실패: {e}")
            return "기타"

    def _apply_constraints(
        self,
        proposed_holdings: List[Dict],
        target_equity_ratio: float
    ) -> List[Dict]:
        """
        포트폴리오 제약 조건 적용

        제약:
        1. 단일 종목 최대 비중: 30%
        2. 단일 섹터 최대 비중: 50%
        3. 총 비중: target_equity_ratio

        Args:
            proposed_holdings: 제안된 보유 종목 (제약 적용 전)
            target_equity_ratio: 목표 주식 비중

        Returns:
            제약 조건을 만족하는 보유 종목
        """
        # 1. 단일 종목 최대 비중 제한 (30%)
        max_stock_weight = 0.30
        capped_holdings = []

        for h in proposed_holdings:
            weight = h["weight"]

            if weight > max_stock_weight:
                logger.warning(
                    f"⚠️ [Optimizer/Constraint] {h['stock_name']} 비중 {weight:.1%} → {max_stock_weight:.1%} (최대 비중 초과)"
                )
                weight = max_stock_weight

            capped_holdings.append({**h, "weight": weight})

        # 2. 섹터별 비중 계산 및 제한 (50%)
        max_sector_weight = 0.50
        sector_totals = {}

        for h in capped_holdings:
            sector = h.get("sector", "기타")
            sector_totals[sector] = sector_totals.get(sector, 0) + h["weight"]

        # 섹터 비중 초과 확인
        sector_adjustments = {}
        for sector, total_weight in sector_totals.items():
            if total_weight > max_sector_weight:
                # 비율로 감소
                adjustment_factor = max_sector_weight / total_weight
                sector_adjustments[sector] = adjustment_factor

                logger.warning(
                    f"⚠️ [Optimizer/Constraint] {sector} 섹터 비중 {total_weight:.1%} → {max_sector_weight:.1%}"
                )

        # 섹터 조정 적용
        adjusted_holdings = []
        for h in capped_holdings:
            sector = h.get("sector", "기타")
            weight = h["weight"]

            if sector in sector_adjustments:
                weight *= sector_adjustments[sector]

            adjusted_holdings.append({**h, "weight": weight})

        # 3. 총 비중 정규화 (target_equity_ratio 맞추기)
        total_weight = sum(h["weight"] for h in adjusted_holdings)

        if total_weight == 0:
            logger.warning("⚠️ [Optimizer/Constraint] 총 비중이 0, 제약 적용 실패")
            return proposed_holdings

        normalization_factor = target_equity_ratio / total_weight

        normalized_holdings = []
        for h in adjusted_holdings:
            final_weight = h["weight"] * normalization_factor

            normalized_holdings.append({
                "stock_code": h["stock_code"],
                "stock_name": h["stock_name"],
                "weight": round(final_weight, 4),
                "value": h["value"],
                "sector": h.get("sector", "기타"),
            })

        logger.info(
            f"✅ [Optimizer/Constraint] 제약 조건 적용 완료: "
            f"총 비중 {sum(h['weight'] for h in normalized_holdings):.1%}"
        )

        return normalized_holdings

    async def _calculate_portfolio_metrics(
        self,
        proposed_holdings: List[PortfolioHolding],
        risk_profile: str
    ) -> Dict[str, float]:
        """
        포트폴리오 성과 지표 계산

        Returns:
            {
                "expected_return": 0.12,
                "expected_volatility": 0.18,
                "sharpe_ratio": 0.75,
                "rationale": "..."
            }
        """
        # 보유 종목 (CASH 제외)
        stock_holdings = [h for h in proposed_holdings if h.get("stock_code") != "CASH"]

        if not stock_holdings:
            return self._get_default_metrics(risk_profile)

        try:
            # 실제 데이터 기반 계산 시도
            stock_codes = [h["stock_code"] for h in stock_holdings]
            weights = [h["weight"] for h in stock_holdings]

            # 종목별 기대 수익률 및 변동성 계산
            returns_list = []
            volatility_list = []

            for stock_code in stock_codes:
                df = await stock_data_service.get_stock_price(stock_code, days=120)

                if df is not None and len(df) > 20:
                    # 일일 수익률
                    daily_returns = df["Close"].pct_change().dropna()

                    # 기대 수익률 (연환산)
                    mean_return = daily_returns.mean() * 252
                    returns_list.append(float(mean_return))

                    # 변동성 (연환산)
                    volatility = daily_returns.std() * (252 ** 0.5)
                    volatility_list.append(float(volatility))
                else:
                    # 데이터 없으면 기본값
                    returns_list.append(0.10)  # 10%
                    volatility_list.append(0.20)  # 20%

            # 포트폴리오 기대 수익률 (가중 평균)
            portfolio_return = sum(w * r for w, r in zip(weights, returns_list))

            # 포트폴리오 변동성 (단순화: 가중 평균)
            portfolio_volatility = sum(w * v for w, v in zip(weights, volatility_list))

            # 샤프 비율 (무위험 이자율 3.5% 가정)
            risk_free_rate = 0.035
            sharpe = (portfolio_return - risk_free_rate) / portfolio_volatility if portfolio_volatility > 0 else 0

            # 근거 생성
            rationale = self._generate_metrics_rationale(
                risk_profile=risk_profile,
                portfolio_return=portfolio_return,
                portfolio_volatility=portfolio_volatility
            )

            logger.info(f"📊 [Optimizer] 성과 지표: 수익률 {portfolio_return:.2%}, 변동성 {portfolio_volatility:.2%}, Sharpe {sharpe:.2f}")

            return {
                "expected_return": round(portfolio_return, 4),
                "expected_volatility": round(portfolio_volatility, 4),
                "sharpe_ratio": round(sharpe, 4),
                "rationale": rationale
            }

        except Exception as e:
            logger.warning(f"⚠️ [Optimizer] 성과 지표 계산 실패: {e}, 기본값 사용")
            return self._get_default_metrics(risk_profile)

    def _get_default_metrics(self, risk_profile: str) -> Dict[str, float]:
        """Fallback: 위험 성향별 기본 성과 지표"""
        defaults = {
            "conservative": {
                "expected_return": 0.08,
                "expected_volatility": 0.11,
                "sharpe_ratio": 0.78,
                "rationale": "보수적 포트폴리오: 낮은 변동성, 안정적 수익 추구"
            },
            "moderate": {
                "expected_return": 0.12,
                "expected_volatility": 0.17,
                "sharpe_ratio": 0.82,
                "rationale": "균형 포트폴리오: 적정 위험으로 중간 수익 추구"
            },
            "aggressive": {
                "expected_return": 0.16,
                "expected_volatility": 0.24,
                "sharpe_ratio": 0.74,
                "rationale": "공격적 포트폴리오: 높은 변동성, 고수익 추구"
            },
        }

        return defaults.get(risk_profile, defaults["moderate"])

    def _generate_metrics_rationale(
        self,
        risk_profile: str,
        portfolio_return: float,
        portfolio_volatility: float
    ) -> str:
        """성과 지표 근거 생성"""
        risk_desc = {
            "conservative": "보수적",
            "moderate": "균형",
            "aggressive": "공격적"
        }

        profile_name = risk_desc.get(risk_profile, "균형")

        rationale = (
            f"{profile_name} 포트폴리오 구성. "
            f"기대 수익률 {portfolio_return:.1%}, 변동성 {portfolio_volatility:.1%} 수준"
        )

        if portfolio_volatility > 0.25:
            rationale += ". 고변동성 주의"
        elif portfolio_volatility < 0.15:
            rationale += ". 안정적 변동성"

        return rationale


# 싱글톤 인스턴스
portfolio_optimizer = PortfolioOptimizer()


# 모듈 레벨 wrapper 함수 (backward compatibility)
async def calculate_target_allocation(*args, **kwargs):
    """
    모듈 레벨 wrapper 함수

    portfolio_optimizer 인스턴스의 calculate_target_allocation 메서드를 호출합니다.
    """
    return await portfolio_optimizer.calculate_target_allocation(*args, **kwargs)
