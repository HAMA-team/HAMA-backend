"""
Risk Stance - 리스크 스탠스 결정 서브모듈

책임:
- 시장 상황별 리스크 수준 판단
- 주식/현금 비율 결정
- 방어 수위 조정
"""

from decimal import Decimal
from src.schemas.strategy import AssetAllocation


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
            volatility_index: 변동성 지수 (VIX 등)

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

        # 3. 변동성 조정 (Week 14 구현)
        if volatility_index:
            equity_weight = self._adjust_for_volatility(equity_weight, volatility_index)

        # 4. 범위 제한 (20% ~ 95%)
        equity_weight = max(Decimal("0.20"), min(Decimal("0.95"), equity_weight))
        cash_weight = Decimal("1.00") - equity_weight

        # 5. 근거 생성
        rationale = self._generate_rationale(
            market_cycle,
            risk_tolerance,
            equity_weight
        )

        return AssetAllocation(
            stocks=equity_weight,
            cash=cash_weight,
            rationale=rationale
        )

    def _adjust_for_volatility(
        self,
        equity_weight: Decimal,
        volatility_index: float
    ) -> Decimal:
        """
        변동성 지표에 따른 조정

        Week 14 구현:
        - VIX > 30: 주식 비중 -10%p
        - VIX 20-30: 주식 비중 -5%p
        - VIX < 20: 조정 없음
        """
        # Mock: 그대로 반환
        return equity_weight

    def _generate_rationale(
        self,
        market_cycle: str,
        risk_tolerance: str,
        equity_weight: Decimal
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

        return (
            f"{cycle_name} 기조에서 {tolerance_name} 리스크 허용도에 맞춘 자산 배분. "
            f"주식 {equity_weight:.0%} 비중 권장"
        )


# Global instance
risk_stance_analyzer = RiskStanceAnalyzer()
