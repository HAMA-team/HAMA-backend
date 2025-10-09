"""
Risk Stance - 리스크 스탠스 결정 서브모듈

책임:
- 시장 상황별 리스크 수준 판단
- 주식/현금 비율 결정
- 방어 수위 조정
"""

import logging
from decimal import Decimal
from src.schemas.strategy import AssetAllocation
from src.services.stock_data_service import stock_data_service

logger = logging.getLogger(__name__)


class RiskStanceAnalyzer:
    """
    리스크 스탠스 분석기

    Week 13 Mock 구현:
    - 규칙 기반 자산 배분

    Week 14 실제 구현:
    - 변동성 지표 분석 (VIX 등)
    - 시장 심리 지표 통합
    - 동적 리스크 조정
    """

    # 시장 사이클별 기본 주식 비중 (공격적 기준)
    CYCLE_EQUITY_WEIGHT = {
        "early_bull_market": Decimal("0.90"),
        "mid_bull_market": Decimal("0.85"),
        "late_bull_market": Decimal("0.70"),
        "bear_market": Decimal("0.40"),
        "consolidation": Decimal("0.65"),
    }

    # 리스크 허용도별 조정 배수
    RISK_TOLERANCE_MULTIPLIER = {
        "conservative": Decimal("0.67"),   # 2/3 수준
        "moderate": Decimal("0.88"),       # 88% 수준
        "aggressive": Decimal("1.00"),     # 100% 수준
    }

    def __init__(self):
        pass

    async def determine_allocation(
        self,
        market_cycle: str,
        risk_tolerance: str,
        volatility_index: float = None
    ) -> AssetAllocation:
        """
        자산 배분 결정

        Args:
            market_cycle: 시장 사이클
            risk_tolerance: 리스크 허용도 (conservative/moderate/aggressive)
            volatility_index: 변동성 지수 (제공되지 않으면 자동 계산)

        Returns:
            AssetAllocation: 자산 배분 전략
        """
        # 1. 기본 주식 비중 결정
        base_equity = self.CYCLE_EQUITY_WEIGHT.get(
            market_cycle,
            Decimal("0.75")  # 기본값
        )

        # 2. 리스크 허용도 반영
        multiplier = self.RISK_TOLERANCE_MULTIPLIER.get(
            risk_tolerance,
            Decimal("0.88")  # 기본값: moderate
        )
        equity_weight = base_equity * multiplier

        # 3. 변동성 조정 (실제 데이터)
        if volatility_index is None:
            # 변동성 지수 자동 계산
            volatility_index = await self._calculate_market_volatility()

        if volatility_index is not None:
            equity_weight = self._adjust_for_volatility(equity_weight, volatility_index)
            logger.info(f"📊 [Risk Stance] 변동성 {volatility_index:.2f}% 반영 완료")

        # 4. 범위 제한 (20% ~ 95%)
        equity_weight = max(Decimal("0.20"), min(Decimal("0.95"), equity_weight))
        cash_weight = Decimal("1.00") - equity_weight

        # 5. 근거 생성
        rationale = self._generate_rationale(
            market_cycle,
            risk_tolerance,
            equity_weight,
            volatility_index
        )

        return AssetAllocation(
            stocks=equity_weight,
            cash=cash_weight,
            rationale=rationale
        )

    async def _calculate_market_volatility(self) -> float | None:
        """
        시장 변동성 계산 (KOSPI 지수 기준)

        Returns:
            변동성 지수 (%) 또는 None

        Raises:
            Exception: Rate Limit 등으로 데이터 조회 실패 시
        """
        # KOSPI 지수 최근 60일 데이터 조회 (Rate Limit 방지 최적화)
        df = await stock_data_service.get_market_index("KS11", days=60)

        if df is None or len(df) < 20:
            logger.warning("⚠️ [Risk Stance] KOSPI 데이터 부족, 변동성 계산 불가")
            return None

        # 일일 수익률 계산
        returns = df["Close"].pct_change().dropna()

        # 변동성 = 일일 수익률 표준편차 * √252 (연환산)
        daily_volatility = returns.std()
        annual_volatility = daily_volatility * (252 ** 0.5)

        # 백분율로 변환
        volatility_pct = annual_volatility * 100

        logger.info(f"📊 [Risk Stance] KOSPI 변동성: {volatility_pct:.2f}%")
        return float(volatility_pct)

    def _adjust_for_volatility(
        self,
        equity_weight: Decimal,
        volatility_index: float
    ) -> Decimal:
        """
        변동성 지표에 따른 자산 배분 조정

        조정 규칙:
        - 변동성 > 30%: 주식 비중 -10%p
        - 변동성 20-30%: 주식 비중 -5%p
        - 변동성 < 20%: 조정 없음
        """
        adjustment = Decimal("0.00")

        if volatility_index > 30:
            adjustment = Decimal("-0.10")
            logger.info(f"⚠️ [Risk Stance] 고변동성 감지 ({volatility_index:.1f}%), 주식 비중 -10%p")
        elif volatility_index > 20:
            adjustment = Decimal("-0.05")
            logger.info(f"⚠️ [Risk Stance] 중변동성 ({volatility_index:.1f}%), 주식 비중 -5%p")
        else:
            logger.info(f"✅ [Risk Stance] 저변동성 ({volatility_index:.1f}%), 조정 없음")

        return equity_weight + adjustment

    def _generate_rationale(
        self,
        market_cycle: str,
        risk_tolerance: str,
        equity_weight: Decimal,
        volatility_index: float = None
    ) -> str:
        """자산 배분 근거 생성"""
        cycle_desc = {
            "early_bull_market": "초기 강세장",
            "mid_bull_market": "중기 강세장",
            "late_bull_market": "후기 강세장",
            "bear_market": "약세장",
            "consolidation": "횡보장",
        }

        tolerance_desc = {
            "conservative": "보수적",
            "moderate": "중립적",
            "aggressive": "공격적",
        }

        cycle_name = cycle_desc.get(market_cycle, market_cycle)
        tolerance_name = tolerance_desc.get(risk_tolerance, risk_tolerance)

        base_rationale = (
            f"{cycle_name} 기조에서 {tolerance_name} 리스크 허용도에 맞춘 자산 배분. "
            f"주식 {equity_weight:.0%} 비중 권장"
        )

        # 변동성 정보 추가
        if volatility_index is not None:
            if volatility_index > 30:
                base_rationale += f". 고변동성({volatility_index:.1f}%)으로 방어적 조정"
            elif volatility_index > 20:
                base_rationale += f". 중간 변동성({volatility_index:.1f}%)으로 일부 조정"

        return base_rationale


# Global instance
risk_stance_analyzer = RiskStanceAnalyzer()
