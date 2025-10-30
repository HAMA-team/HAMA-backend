"""
Portfolio Agent 제약 조건 단위 테스트

테스트 범위:
1. Market Condition 노드 (시장 상황 분석 및 슬롯 조정)
2. Validate Constraints 노드 (포트폴리오 제약 조건 검증)
3. 제약 조건 위반 시나리오

사용법:
    pytest tests/unit/test_agents/test_portfolio_constraints.py -v
    python tests/unit/test_agents/test_portfolio_constraints.py
"""
import asyncio
import pytest
from uuid import uuid4

from langchain_core.messages import HumanMessage

from src.agents.portfolio.nodes import (
    market_condition_node,
    validate_constraints_node,
)
from src.agents.portfolio.state import PortfolioState, PortfolioHolding


class TestPortfolioConstraints:
    """Portfolio Agent 제약 조건 테스트"""

    @pytest.mark.asyncio
    async def test_market_condition_bull_market(self):
        """
        Market Condition 테스트: 강세장

        KOSPI가 5% 이상 상승했을 때 최대 10개 슬롯을 권장하는지 검증
        """
        print("\n[Test] Market Condition - 강세장")

        state: PortfolioState = {
            "messages": [HumanMessage(content="시장 상황 분석")],
            "portfolio_snapshot": {
                "market_data": {
                    "kospi_change_rate": 0.08,  # 8% 상승
                },
            },
        }

        # 실행
        result = await market_condition_node(state)

        # 검증
        assert "market_condition" in result, "시장 상황이 있어야 함"
        assert "max_slots" in result, "최대 슬롯이 있어야 함"

        market_condition = result["market_condition"]
        max_slots = result["max_slots"]

        assert market_condition == "강세장", "KOSPI 8% 상승은 강세장이어야 함"
        assert max_slots == 10, "강세장에서는 최대 10개 슬롯이어야 함"

        print(f"  ✅ 시장 상황: {market_condition}")
        print(f"  ✅ 최대 슬롯: {max_slots}개")

    @pytest.mark.asyncio
    async def test_market_condition_bear_market(self):
        """
        Market Condition 테스트: 약세장

        KOSPI가 5% 이상 하락했을 때 최대 5개 슬롯을 권장하는지 검증
        """
        print("\n[Test] Market Condition - 약세장")

        state: PortfolioState = {
            "messages": [HumanMessage(content="시장 상황 분석")],
            "portfolio_snapshot": {
                "market_data": {
                    "kospi_change_rate": -0.10,  # 10% 하락
                },
            },
        }

        # 실행
        result = await market_condition_node(state)

        market_condition = result["market_condition"]
        max_slots = result["max_slots"]

        assert market_condition == "약세장", "KOSPI 10% 하락은 약세장이어야 함"
        assert max_slots == 5, "약세장에서는 최대 5개 슬롯이어야 함"

        print(f"  ✅ 시장 상황: {market_condition}")
        print(f"  ✅ 최대 슬롯: {max_slots}개 (리스크 관리)")

    @pytest.mark.asyncio
    async def test_market_condition_neutral_market(self):
        """
        Market Condition 테스트: 중립장

        KOSPI 변화가 ±5% 이내일 때 최대 7개 슬롯을 권장하는지 검증
        """
        print("\n[Test] Market Condition - 중립장")

        state: PortfolioState = {
            "messages": [HumanMessage(content="시장 상황 분석")],
            "portfolio_snapshot": {
                "market_data": {
                    "kospi_change_rate": 0.02,  # 2% 상승
                },
            },
        }

        # 실행
        result = await market_condition_node(state)

        market_condition = result["market_condition"]
        max_slots = result["max_slots"]

        assert market_condition == "중립장", "KOSPI 2% 변동은 중립장이어야 함"
        assert max_slots == 7, "중립장에서는 최대 7개 슬롯이어야 함"

        print(f"  ✅ 시장 상황: {market_condition}")
        print(f"  ✅ 최대 슬롯: {max_slots}개")

    @pytest.mark.asyncio
    async def test_validate_constraints_no_violations(self):
        """
        Validate Constraints 테스트: 제약 조건 충족

        모든 제약 조건을 충족하는 포트폴리오 검증
        """
        print("\n[Test] Validate Constraints - 제약 조건 충족")

        # 제약 조건을 충족하는 포트폴리오 (5개 종목, 분산됨)
        proposed_allocation: list[PortfolioHolding] = [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.20, "value": 2000000},
            {"stock_code": "035720", "stock_name": "카카오", "weight": 0.15, "value": 1500000},
            {"stock_code": "207940", "stock_name": "삼성바이오", "weight": 0.15, "value": 1500000},
            {"stock_code": "051910", "stock_name": "LG화학", "weight": 0.20, "value": 2000000},
            {"stock_code": "CASH", "stock_name": "현금", "weight": 0.30, "value": 3000000},
        ]

        state: PortfolioState = {
            "messages": [HumanMessage(content="제약 조건 검증")],
            "proposed_allocation": proposed_allocation,
            "max_slots": 10,
            "max_sector_concentration": 0.30,
            "max_same_industry_count": 3,
        }

        # 실행
        result = await validate_constraints_node(state)

        # 검증
        assert "constraint_violations" in result, "제약 조건 위반 내역이 있어야 함"
        violations = result["constraint_violations"]

        assert len(violations) == 0, "제약 조건 충족 시 위반 내역이 없어야 함"

        print("  ✅ 모든 제약 조건 충족")
        print(f"  ✅ 보유 종목: 4개 (현금 제외)")
        print(f"  ✅ 위반 건수: 0건")

    @pytest.mark.asyncio
    async def test_validate_constraints_max_slots_violation(self):
        """
        Validate Constraints 테스트: 최대 슬롯 초과

        최대 슬롯을 초과하는 포트폴리오 검증
        """
        print("\n[Test] Validate Constraints - 최대 슬롯 초과")

        # 12개 종목 (최대 10개 초과)
        proposed_allocation: list[PortfolioHolding] = [
            {"stock_code": f"{i:06d}", "stock_name": f"종목{i}", "weight": 0.08, "value": 800000}
            for i in range(12)
        ]

        state: PortfolioState = {
            "messages": [HumanMessage(content="제약 조건 검증")],
            "proposed_allocation": proposed_allocation,
            "max_slots": 10,
        }

        # 실행
        result = await validate_constraints_node(state)

        violations = result["constraint_violations"]

        # 검증
        assert len(violations) > 0, "최대 슬롯 초과 시 위반이 있어야 함"

        max_slots_violations = [v for v in violations if v["type"] == "max_slots"]
        assert len(max_slots_violations) > 0, "max_slots 위반이 있어야 함"

        violation = max_slots_violations[0]
        assert violation["severity"] == "high", "최대 슬롯 위반은 high severity여야 함"
        assert violation["current"] == 12, "현재 12개 종목이어야 함"
        assert violation["limit"] == 10, "제한은 10개여야 함"

        print(f"  ✅ 위반 감지: {violation['message']}")
        print(f"  ✅ Severity: {violation['severity']}")

    @pytest.mark.asyncio
    async def test_validate_constraints_sector_concentration_violation(self):
        """
        Validate Constraints 테스트: 섹터 집중도 초과

        동일 섹터 비중이 30%를 초과하는 포트폴리오 검증
        """
        print("\n[Test] Validate Constraints - 섹터 집중도 초과")

        # 동일 섹터(IT)에 집중된 포트폴리오
        proposed_allocation: list[PortfolioHolding] = [
            {"stock_code": "100000", "stock_name": "IT종목1", "weight": 0.20, "value": 2000000},
            {"stock_code": "100001", "stock_name": "IT종목2", "weight": 0.15, "value": 1500000},
            {"stock_code": "100002", "stock_name": "IT종목3", "weight": 0.10, "value": 1000000},
            # IT 섹터 합계: 45% (30% 초과)
            {"stock_code": "005930", "stock_name": "기타종목", "weight": 0.25, "value": 2500000},
            {"stock_code": "CASH", "stock_name": "현금", "weight": 0.30, "value": 3000000},
        ]

        state: PortfolioState = {
            "messages": [HumanMessage(content="제약 조건 검증")],
            "proposed_allocation": proposed_allocation,
            "max_sector_concentration": 0.30,
        }

        # 실행
        result = await validate_constraints_node(state)

        violations = result["constraint_violations"]

        # 검증
        sector_violations = [v for v in violations if v["type"] == "sector_concentration"]
        assert len(sector_violations) > 0, "섹터 집중도 초과 시 위반이 있어야 함"

        violation = sector_violations[0]
        assert violation["severity"] == "medium", "섹터 집중도 위반은 medium severity여야 함"
        assert violation["current"] > 0.30, "현재 비중이 30%를 초과해야 함"

        print(f"  ✅ 위반 감지: {violation['message']}")
        print(f"  ✅ Severity: {violation['severity']}")
        print(f"  ✅ 섹터: {violation['sector']}")

    @pytest.mark.asyncio
    async def test_validate_constraints_industry_count_violation(self):
        """
        Validate Constraints 테스트: 동일 산업군 종목 수 초과

        동일 산업군에 3개 이상 종목이 있는 포트폴리오 검증
        """
        print("\n[Test] Validate Constraints - 산업군 종목 수 초과")

        # 반도체 산업군(150000~199999)에 4개 종목
        proposed_allocation: list[PortfolioHolding] = [
            {"stock_code": "150000", "stock_name": "반도체1", "weight": 0.15, "value": 1500000},
            {"stock_code": "151000", "stock_name": "반도체2", "weight": 0.15, "value": 1500000},
            {"stock_code": "152000", "stock_name": "반도체3", "weight": 0.10, "value": 1000000},
            {"stock_code": "153000", "stock_name": "반도체4", "weight": 0.10, "value": 1000000},
            # 반도체 산업군 4개 (최대 3개 초과)
            {"stock_code": "CASH", "stock_name": "현금", "weight": 0.50, "value": 5000000},
        ]

        state: PortfolioState = {
            "messages": [HumanMessage(content="제약 조건 검증")],
            "proposed_allocation": proposed_allocation,
            "max_same_industry_count": 3,
        }

        # 실행
        result = await validate_constraints_node(state)

        violations = result["constraint_violations"]

        # 검증
        industry_violations = [v for v in violations if v["type"] == "industry_count"]
        assert len(industry_violations) > 0, "산업군 종목 수 초과 시 위반이 있어야 함"

        violation = industry_violations[0]
        assert violation["severity"] == "low", "산업군 종목 수 위반은 low severity여야 함"
        assert violation["current"] == 4, "현재 4개 종목이어야 함"
        assert violation["limit"] == 3, "제한은 3개여야 함"

        print(f"  ✅ 위반 감지: {violation['message']}")
        print(f"  ✅ Severity: {violation['severity']}")
        print(f"  ✅ 산업군: {violation['industry']}")

    @pytest.mark.asyncio
    async def test_validate_constraints_multiple_violations(self):
        """
        Validate Constraints 테스트: 복수 제약 조건 위반

        여러 제약 조건을 동시에 위반하는 포트폴리오 검증
        """
        print("\n[Test] Validate Constraints - 복수 위반")

        # 최대 슬롯 초과 + 섹터 집중도 초과
        proposed_allocation: list[PortfolioHolding] = [
            {"stock_code": f"1000{i:02d}", "stock_name": f"IT종목{i}", "weight": 0.08, "value": 800000}
            for i in range(12)  # 12개 종목 (최대 10개 초과)
        ]

        state: PortfolioState = {
            "messages": [HumanMessage(content="제약 조건 검증")],
            "proposed_allocation": proposed_allocation,
            "max_slots": 10,
            "max_sector_concentration": 0.30,
        }

        # 실행
        result = await validate_constraints_node(state)

        violations = result["constraint_violations"]

        # 검증
        assert len(violations) >= 2, "복수 위반이 있어야 함"

        violation_types = {v["type"] for v in violations}
        assert "max_slots" in violation_types, "최대 슬롯 위반이 있어야 함"
        assert "sector_concentration" in violation_types, "섹터 집중도 위반이 있어야 함"

        print(f"  ✅ 총 위반 건수: {len(violations)}건")
        print(f"  ✅ 위반 유형: {', '.join(violation_types)}")


if __name__ == "__main__":
    """직접 실행 시"""
    async def run_tests():
        test_suite = TestPortfolioConstraints()

        print("=" * 80)
        print("Portfolio Agent 제약 조건 테스트 시작")
        print("=" * 80)

        try:
            await test_suite.test_market_condition_bull_market()
            await test_suite.test_market_condition_bear_market()
            await test_suite.test_market_condition_neutral_market()
            await test_suite.test_validate_constraints_no_violations()
            await test_suite.test_validate_constraints_max_slots_violation()
            await test_suite.test_validate_constraints_sector_concentration_violation()
            await test_suite.test_validate_constraints_industry_count_violation()
            await test_suite.test_validate_constraints_multiple_violations()

            print("\n" + "=" * 80)
            print("✅ 모든 테스트 통과!")
            print("=" * 80)

        except AssertionError as e:
            print(f"\n❌ 테스트 실패: {e}")
        except Exception as e:
            print(f"\n❌ 예외 발생: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(run_tests())
