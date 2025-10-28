"""
Portfolio Optimizer 테스트

동적 포트폴리오 비중 계산 및 성과 지표 산출 테스트
"""
import pytest
from src.services import portfolio_optimizer


class TestPortfolioOptimizer:
    """Portfolio Optimizer 테스트"""

    @pytest.mark.asyncio
    async def test_calculate_target_allocation_with_strategy(self):
        """Strategy 결과 기반 목표 비중 계산"""
        # 현재 보유 종목
        current_holdings = [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.40, "value": 4_000_000},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.30, "value": 3_000_000},
            {"stock_code": "CASH", "stock_name": "예수금", "weight": 0.30, "value": 3_000_000},
        ]

        # Strategy 결과
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

        # 총 비중 = 1.0
        total_weight = sum(h["weight"] for h in proposed)
        assert abs(total_weight - 1.0) < 0.01, f"총 비중 불일치: {total_weight}"

        # 성과 지표 존재 확인
        assert "expected_return" in metrics
        assert "expected_volatility" in metrics
        assert "sharpe_ratio" in metrics
        assert "rationale" in metrics

    @pytest.mark.asyncio
    async def test_optimizer_without_strategy(self):
        """Strategy 결과 없이 Fallback 동작 확인"""
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

        # Fallback 로직 검증
        assert len(proposed) > 0, "Fallback 계산 실패"
        assert metrics is not None, "Fallback 성과 지표 실패"

        # Conservative 프로필: 현금 비중 >= 40%
        cash_weight = next((h["weight"] for h in proposed if h["stock_code"] == "CASH"), 0)
        assert cash_weight >= 0.40, f"Conservative 현금 비중 부족: {cash_weight}"

    @pytest.mark.asyncio
    async def test_risk_profile_differences(self):
        """위험 성향별 비중 차이 검증"""
        current_holdings = [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.60, "value": 6_000_000},
            {"stock_code": "CASH", "stock_name": "예수금", "weight": 0.40, "value": 4_000_000},
        ]

        profiles = ["conservative", "moderate", "aggressive"]
        results = {}

        for profile in profiles:
            proposed, metrics = await portfolio_optimizer.calculate_target_allocation(
                current_holdings=current_holdings,
                strategy_result=None,
                risk_profile=profile,
                total_value=10_000_000
            )

            stock_weight = sum(h["weight"] for h in proposed if h["stock_code"] != "CASH")
            results[profile] = stock_weight

        # 공격적 > 중립 > 보수적
        assert results["aggressive"] >= results["moderate"]
        assert results["moderate"] >= results["conservative"]

    @pytest.mark.asyncio
    async def test_metrics_calculation(self):
        """성과 지표 계산 로직 검증"""
        current_holdings = [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 1.0, "value": 10_000_000},
        ]

        proposed, metrics = await portfolio_optimizer.calculate_target_allocation(
            current_holdings=current_holdings,
            strategy_result=None,
            risk_profile="moderate",
            total_value=10_000_000
        )

        # 실제 데이터 기반 계산 확인
        assert metrics["expected_return"] > 0, "기대 수익률이 0보다 커야 함"
        assert metrics["expected_volatility"] > 0, "변동성이 0보다 커야 함"
        assert isinstance(metrics["sharpe_ratio"], float), "샤프 비율은 float여야 함"
        assert len(metrics["rationale"]) > 0, "근거 문구가 있어야 함"
