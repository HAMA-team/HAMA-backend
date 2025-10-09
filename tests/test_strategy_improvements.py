"""
Strategy Agent 개선 사항 통합 테스트

1. DART 전체 매핑 (3,901개 종목)
2. 섹터 로테이션 (실제 데이터)
3. 자산 배분 (변동성 기반)
"""
import asyncio
import pytest

from src.services import dart_service
from src.agents.strategy.sector_rotator import sector_rotator
from src.agents.strategy.risk_stance import risk_stance_analyzer
from src.config.settings import settings


class TestStrategyImprovements:
    """Strategy Agent 개선 사항 테스트"""

    @pytest.mark.asyncio
    async def test_dart_full_mapping(self):
        """DART 전체 종목 매핑 테스트"""
        if not settings.DART_API_KEY:
            pytest.skip("DART_API_KEY not configured")

        # 주요 10개 종목 조회
        test_stocks = ["005930", "000660", "035420", "005380", "051910",
                      "005490", "006400", "207940", "068270", "035720"]

        print("\n📋 DART 전체 매핑 테스트:")
        success_count = 0

        for stock_code in test_stocks:
            corp_code = await dart_service.search_corp_code_by_stock_code(stock_code)
            if corp_code:
                success_count += 1
                print(f"   ✅ {stock_code} → {corp_code}")
            else:
                print(f"   ❌ {stock_code} → None")

        # 최소 8개 이상 성공
        assert success_count >= 8, f"매핑 성공률 부족: {success_count}/10"
        print(f"\n✅ DART 매핑 테스트 통과: {success_count}/10개 성공")

    @pytest.mark.asyncio
    async def test_sector_rotation_real_data(self):
        """섹터 로테이션 실제 데이터 테스트"""
        print("\n🔄 섹터 로테이션 (실제 데이터) 테스트:")

        # 섹터 전략 생성
        strategy = await sector_rotator.create_strategy(
            market_cycle="mid_bull_market",
            user_preferences={"sectors": ["IT/전기전자", "반도체"]}
        )

        # 검증
        assert strategy is not None
        assert len(strategy.sectors) > 0
        assert len(strategy.overweight) > 0
        assert len(strategy.rationale) > 0

        print(f"   Overweight: {', '.join(strategy.overweight)}")
        print(f"   Underweight: {', '.join(strategy.underweight)}")
        print(f"   Rationale: {strategy.rationale}")

        print(f"\n✅ 섹터 로테이션 테스트 통과")

    @pytest.mark.asyncio
    async def test_asset_allocation_volatility(self):
        """자산 배분 (변동성 기반) 테스트"""
        print("\n💰 자산 배분 (변동성 기반) 테스트:")

        # 자산 배분 결정
        allocation = await risk_stance_analyzer.determine_allocation(
            market_cycle="mid_bull_market",
            risk_tolerance="moderate"
        )

        # 검증
        assert allocation is not None
        assert allocation.stocks + allocation.cash == 1.0
        assert 0.20 <= allocation.stocks <= 0.95
        assert len(allocation.rationale) > 0

        print(f"   주식 비중: {allocation.stocks:.0%}")
        print(f"   현금 비중: {allocation.cash:.0%}")
        print(f"   Rationale: {allocation.rationale}")

        # 변동성 정보가 근거에 포함되어 있는지 확인
        if "변동성" in allocation.rationale:
            print(f"   ✅ 변동성 정보 반영됨")

        print(f"\n✅ 자산 배분 테스트 통과")


if __name__ == "__main__":
    """테스트 직접 실행"""
    async def main():
        print("\n" + "="*60)
        print("Strategy Agent 개선 사항 통합 테스트")
        print("="*60)

        tester = TestStrategyImprovements()

        # 1. DART 전체 매핑 테스트
        print("\n[1/3] DART 전체 매핑 테스트...")
        try:
            await tester.test_dart_full_mapping()
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        # 2. 섹터 로테이션 테스트
        print("\n[2/3] 섹터 로테이션 (실제 데이터) 테스트...")
        try:
            await tester.test_sector_rotation_real_data()
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        # 3. 자산 배분 테스트
        print("\n[3/3] 자산 배분 (변동성 기반) 테스트...")
        try:
            await tester.test_asset_allocation_volatility()
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        print("\n" + "="*60)
        print("모든 테스트 완료!")
        print("="*60)

    asyncio.run(main())
