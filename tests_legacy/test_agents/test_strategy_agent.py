"""
Strategy Agent 테스트

섹터 로테이션 및 자산 배분 전략 테스트
"""
import pytest
from src.agents.strategy.sector_rotator import sector_rotator
from src.agents.strategy.risk_stance import risk_stance_analyzer


class TestStrategyAgent:
    """Strategy Agent 통합 테스트"""

    @pytest.mark.asyncio
    async def test_sector_rotation_with_real_data(self):
        """섹터 로테이션 (실제 데이터 기반)"""
        # 섹터 전략 생성
        strategy = await sector_rotator.create_strategy(
            market_cycle="mid_bull_market",
            user_preferences={"sectors": ["IT/전기전자", "반도체"]}
        )

        # 검증
        assert strategy is not None, "전략 생성 실패"
        assert len(strategy.sectors) > 0, "섹터 정보 없음"
        assert len(strategy.overweight) > 0, "Overweight 섹터 없음"
        assert len(strategy.rationale) > 0, "근거 없음"

    @pytest.mark.asyncio
    async def test_asset_allocation_with_volatility(self):
        """자산 배분 (변동성 기반 조정)"""
        # 자산 배분 결정
        allocation = await risk_stance_analyzer.determine_allocation(
            market_cycle="mid_bull_market",
            risk_tolerance="moderate"
        )

        # 검증
        assert allocation is not None, "자산 배분 실패"
        assert allocation.stocks + allocation.cash == 1.0, "비중 합이 1.0이 아님"
        assert 0.20 <= allocation.stocks <= 0.95, "주식 비중 범위 초과"
        assert len(allocation.rationale) > 0, "근거 없음"

    @pytest.mark.asyncio
    async def test_risk_tolerance_differences(self):
        """위험 허용도별 자산 배분 차이"""
        profiles = ["conservative", "moderate", "aggressive"]
        allocations = {}

        for profile in profiles:
            allocation = await risk_stance_analyzer.determine_allocation(
                market_cycle="mid_bull_market",
                risk_tolerance=profile
            )
            allocations[profile] = allocation.stocks

        # 공격적 > 중립 > 보수적
        assert allocations["aggressive"] >= allocations["moderate"]
        assert allocations["moderate"] >= allocations["conservative"]

    @pytest.mark.asyncio
    async def test_market_cycle_impact(self):
        """시장 사이클별 전략 차이"""
        cycles = ["early_bull_market", "late_bull_market", "bear_market"]
        allocations = {}

        for cycle in cycles:
            allocation = await risk_stance_analyzer.determine_allocation(
                market_cycle=cycle,
                risk_tolerance="moderate"
            )
            allocations[cycle] = allocation.stocks

        # 초기 강세 > 후기 강세 > 약세
        assert allocations["early_bull_market"] >= allocations["late_bull_market"]
        assert allocations["late_bull_market"] >= allocations["bear_market"]
