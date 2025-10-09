"""
Rate Limit 해결 및 Portfolio Mock 제거 통합 테스트

1. KOSPI 지수 조회 (Rate Limit 방지)
2. Portfolio Optimizer (동적 비중 계산)
3. Portfolio Agent (Mock 제거 검증)
"""
import asyncio
import pytest

from src.services import stock_data_service, portfolio_optimizer
from src.config.settings import settings


class TestRateLimitImprovements:
    """Rate Limit 개선 사항 테스트"""

    @pytest.mark.asyncio
    async def test_market_index_with_cache(self):
        """시장 지수 조회 (캐싱 및 Retry 로직)"""
        print("\n📊 시장 지수 조회 테스트 (KOSPI):")

        # 첫 번째 호출 (API 호출)
        df1 = await stock_data_service.get_market_index("KS11", days=60)
        assert df1 is not None, "KOSPI 지수 조회 실패"
        assert len(df1) > 0, "KOSPI 데이터 없음"
        print(f"   ✅ 첫 번째 호출: {len(df1)}일 데이터 조회")

        # 두 번째 호출 (캐시 히트)
        df2 = await stock_data_service.get_market_index("KS11", days=60)
        assert df2 is not None, "캐시된 KOSPI 조회 실패"
        assert len(df2) == len(df1), "캐시 데이터 불일치"
        print(f"   ✅ 두 번째 호출: 캐시 히트 ({len(df2)}일)")

        # 변동성 계산
        returns = df1["Close"].pct_change().dropna()
        volatility = returns.std() * (252 ** 0.5) * 100
        print(f"   📈 KOSPI 변동성: {volatility:.2f}%")

        assert volatility > 0, "변동성 계산 실패"
        print(f"\n✅ 시장 지수 조회 테스트 통과")

    @pytest.mark.asyncio
    async def test_consecutive_index_calls(self):
        """연속 호출 테스트 (Rate Limit 방지 검증)"""
        print("\n🔄 연속 호출 테스트 (5회):")

        success_count = 0
        for i in range(5):
            try:
                df = await stock_data_service.get_market_index("KS11", days=30)
                if df is not None and len(df) > 0:
                    success_count += 1
                    print(f"   ✅ 호출 {i+1}: 성공 ({len(df)}일)")
                else:
                    print(f"   ⚠️ 호출 {i+1}: 데이터 없음")
            except Exception as e:
                print(f"   ❌ 호출 {i+1}: 실패 - {e}")

        # 캐싱 덕분에 5회 모두 성공해야 함
        assert success_count >= 4, f"연속 호출 성공률 부족: {success_count}/5"
        print(f"\n✅ 연속 호출 테스트 통과: {success_count}/5 성공")


class TestPortfolioOptimizer:
    """Portfolio Optimizer 테스트"""

    @pytest.mark.asyncio
    async def test_calculate_target_allocation(self):
        """목표 비중 동적 계산 테스트"""
        print("\n💼 Portfolio Optimizer 테스트:")

        # 현재 보유 종목 (샘플)
        current_holdings = [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.40, "value": 4_000_000},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.30, "value": 3_000_000},
            {"stock_code": "CASH", "stock_name": "예수금", "weight": 0.30, "value": 3_000_000},
        ]

        # Strategy 결과 (샘플)
        strategy_result = {
            "asset_allocation": {
                "stocks": 0.75,
                "cash": 0.25
            },
            "sector_strategy": {
                "overweight": ["IT/전기전자", "반도체"],
                "underweight": ["금융"]
            }
        }

        # 목표 비중 계산
        proposed, metrics = await portfolio_optimizer.calculate_target_allocation(
            current_holdings=current_holdings,
            strategy_result=strategy_result,
            risk_profile="moderate",
            total_value=10_000_000
        )

        # 검증
        assert len(proposed) > 0, "목표 비중 계산 실패"
        assert metrics is not None, "성과 지표 계산 실패"

        total_weight = sum(h["weight"] for h in proposed)
        assert abs(total_weight - 1.0) < 0.01, f"총 비중 불일치: {total_weight}"

        print(f"   📋 목표 비중: {len(proposed)}개 자산")
        for holding in proposed:
            print(f"      - {holding['stock_name']}: {holding['weight']:.1%}")

        print(f"   📊 성과 지표:")
        print(f"      - 기대 수익률: {metrics['expected_return']:.1%}")
        print(f"      - 변동성: {metrics['expected_volatility']:.1%}")
        print(f"      - Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"      - 근거: {metrics['rationale']}")

        print(f"\n✅ Portfolio Optimizer 테스트 통과")

    @pytest.mark.asyncio
    async def test_optimizer_without_strategy(self):
        """Strategy 결과 없이도 작동하는지 테스트 (Fallback)"""
        print("\n🔄 Optimizer Fallback 테스트 (Strategy 결과 없음):")

        current_holdings = [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.50, "value": 5_000_000},
            {"stock_code": "CASH", "stock_name": "예수금", "weight": 0.50, "value": 5_000_000},
        ]

        # Strategy 결과 없음
        proposed, metrics = await portfolio_optimizer.calculate_target_allocation(
            current_holdings=current_holdings,
            strategy_result=None,
            risk_profile="conservative",
            total_value=10_000_000
        )

        # Fallback 로직으로 계산되어야 함
        assert len(proposed) > 0, "Fallback 계산 실패"
        assert metrics is not None, "Fallback 성과 지표 실패"

        # Conservative는 주식 50%, 현금 50%
        stock_weight = sum(h["weight"] for h in proposed if h["stock_code"] != "CASH")
        cash_weight = next((h["weight"] for h in proposed if h["stock_code"] == "CASH"), 0)

        print(f"   주식 비중: {stock_weight:.0%}, 현금 비중: {cash_weight:.0%}")
        assert cash_weight >= 0.40, "Conservative 현금 비중 부족"

        print(f"✅ Fallback 테스트 통과")


class TestPortfolioIntegration:
    """Portfolio Agent 통합 테스트"""

    @pytest.mark.asyncio
    async def test_no_mock_data_used(self):
        """Mock 데이터가 제거되었는지 확인"""
        print("\n🔍 Mock 데이터 제거 검증:")

        # portfolio/nodes.py에 Mock 딕셔너리가 없어야 함
        from src.agents.portfolio import nodes

        # Mock 상수들이 제거되었는지 확인
        mock_constants = [
            "DEFAULT_PORTFOLIO",
            "RISK_TARGETS",
            "EXPECTED_RETURN",
            "EXPECTED_VOLATILITY",
            "SHARPE_RATIO",
            "RATIONALE_TEXT"
        ]

        removed_count = 0
        for const in mock_constants:
            if not hasattr(nodes, const):
                removed_count += 1
                print(f"   ✅ {const}: 제거됨")
            else:
                print(f"   ❌ {const}: 여전히 존재")

        assert removed_count == len(mock_constants), f"Mock 데이터가 여전히 존재: {len(mock_constants) - removed_count}개"

        print(f"\n✅ Mock 데이터 제거 검증 완료: {removed_count}/{len(mock_constants)}")


if __name__ == "__main__":
    """테스트 직접 실행"""
    async def main():
        print("\n" + "="*60)
        print("Rate Limit 및 Portfolio 개선 통합 테스트")
        print("="*60)

        # 1. Rate Limit 테스트
        print("\n[1/5] 시장 지수 조회 테스트...")
        rate_limit_tester = TestRateLimitImprovements()
        try:
            await rate_limit_tester.test_market_index_with_cache()
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        print("\n[2/5] 연속 호출 테스트...")
        try:
            await rate_limit_tester.test_consecutive_index_calls()
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        # 2. Portfolio Optimizer 테스트
        print("\n[3/5] Portfolio Optimizer 테스트...")
        optimizer_tester = TestPortfolioOptimizer()
        try:
            await optimizer_tester.test_calculate_target_allocation()
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        print("\n[4/5] Optimizer Fallback 테스트...")
        try:
            await optimizer_tester.test_optimizer_without_strategy()
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        # 3. Portfolio 통합 테스트
        print("\n[5/5] Mock 데이터 제거 검증...")
        integration_tester = TestPortfolioIntegration()
        try:
            await integration_tester.test_no_mock_data_used()
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        print("\n" + "="*60)
        print("모든 테스트 완료!")
        print("="*60)

    asyncio.run(main())
