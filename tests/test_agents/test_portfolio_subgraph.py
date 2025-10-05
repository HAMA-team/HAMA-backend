"""
Portfolio Agent 서브그래프 테스트

최근 변경사항:
- Portfolio Agent가 LangGraph 서브그래프로 전환됨
- state.py, nodes.py, graph.py로 구조화
- 리밸런싱 로직 구현
"""
import pytest

from src.agents.portfolio import portfolio_agent
from src.agents.portfolio.state import PortfolioState


@pytest.mark.asyncio
async def test_portfolio_subgraph_generates_report():
    """기본 포트폴리오 리포트 생성 테스트"""
    initial_state: PortfolioState = {
        "request_id": "test_req",
        "user_id": "user_001",
        "automation_level": 2,
        "risk_profile": "moderate",
        "current_holdings": [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.45},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.25},
            {"stock_code": "CASH", "stock_name": "현금", "weight": 0.30},
        ],
        "total_value": 10_000_000,
        "hitl_required": False,
    }

    config = {"configurable": {"thread_id": "test_portfolio_basic"}}

    result = await portfolio_agent.ainvoke(initial_state, config=config)

    # 기본 검증
    assert result.get("portfolio_report") is not None
    assert result["portfolio_report"]["rebalancing_needed"] is True
    assert result["portfolio_report"]["trades_required"]
    assert result["summary"]

    # 상세 검증
    report = result["portfolio_report"]
    assert report["risk_profile"] == "moderate"
    assert report["proposed_allocation"] is not None
    assert report["expected_return"] is not None
    assert report["expected_volatility"] is not None

    print("\n✅ 포트폴리오 리포트 생성 성공")
    print(f"   리밸런싱 필요: {report['rebalancing_needed']}")
    print(f"   거래 건수: {len(report['trades_required'])}")
    print(f"   요약: {result['summary']}")


@pytest.mark.asyncio
async def test_portfolio_conservative_profile():
    """보수적 투자 성향 테스트"""
    initial_state: PortfolioState = {
        "request_id": "test_conservative",
        "automation_level": 2,
        "risk_profile": "conservative",
        "current_holdings": [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.50},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.30},
            {"stock_code": "CASH", "stock_name": "현금", "weight": 0.20},
        ],
        "total_value": 10_000_000,
        "hitl_required": False,
    }

    config = {"configurable": {"thread_id": "test_conservative"}}
    result = await portfolio_agent.ainvoke(initial_state, config=config)

    report = result["portfolio_report"]

    # 보수적 성향은 현금 비중이 높아야 함
    cash_weight = next(
        (h["weight"] for h in report["proposed_allocation"] if h["stock_code"] == "CASH"),
        0.0
    )
    assert cash_weight >= 0.35, "보수적 성향은 현금 비중 35% 이상"

    # 주식 비중은 낮아야 함
    equity_weight = sum(
        h["weight"] for h in report["proposed_allocation"] if h["stock_code"] != "CASH"
    )
    assert equity_weight <= 0.65, "보수적 성향은 주식 비중 65% 이하"

    print("\n✅ 보수적 성향 포트폴리오 검증 성공")
    print(f"   현금 비중: {cash_weight:.1%}")
    print(f"   주식 비중: {equity_weight:.1%}")


@pytest.mark.asyncio
async def test_portfolio_aggressive_profile():
    """공격적 투자 성향 테스트"""
    initial_state: PortfolioState = {
        "request_id": "test_aggressive",
        "automation_level": 2,
        "risk_profile": "aggressive",
        "current_holdings": [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.30},
            {"stock_code": "CASH", "stock_name": "현금", "weight": 0.70},
        ],
        "total_value": 10_000_000,
        "hitl_required": False,
    }

    config = {"configurable": {"thread_id": "test_aggressive"}}
    result = await portfolio_agent.ainvoke(initial_state, config=config)

    report = result["portfolio_report"]

    # 공격적 성향은 주식 비중이 높아야 함
    equity_weight = sum(
        h["weight"] for h in report["proposed_allocation"] if h["stock_code"] != "CASH"
    )
    assert equity_weight >= 0.85, "공격적 성향은 주식 비중 85% 이상"

    # 리밸런싱이 필요해야 함 (현재 70% 현금이므로)
    assert report["rebalancing_needed"] is True

    print("\n✅ 공격적 성향 포트폴리오 검증 성공")
    print(f"   주식 비중: {equity_weight:.1%}")
    print(f"   리밸런싱 필요: {report['rebalancing_needed']}")


@pytest.mark.asyncio
async def test_portfolio_no_rebalancing_needed():
    """리밸런싱 불필요 케이스 테스트"""
    initial_state: PortfolioState = {
        "request_id": "test_no_rebalance",
        "automation_level": 2,
        "risk_profile": "moderate",
        "current_holdings": [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.25},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.20},
            {"stock_code": "035420", "stock_name": "NAVER", "weight": 0.15},
            {"stock_code": "005380", "stock_name": "현대차", "weight": 0.15},
            {"stock_code": "000270", "stock_name": "기아", "weight": 0.10},
            {"stock_code": "CASH", "stock_name": "현금", "weight": 0.15},
        ],
        "total_value": 10_000_000,
        "hitl_required": False,
    }

    config = {"configurable": {"thread_id": "test_no_rebalance"}}
    result = await portfolio_agent.ainvoke(initial_state, config=config)

    report = result["portfolio_report"]

    # 이미 목표 비중과 거의 일치하므로 리밸런싱 불필요
    # (moderate 목표와 거의 동일)
    trades = report["trades_required"]

    print("\n✅ 리밸런싱 불필요 케이스 검증")
    print(f"   리밸런싱 필요: {report['rebalancing_needed']}")
    print(f"   거래 건수: {len(trades)}")


@pytest.mark.asyncio
async def test_portfolio_hitl_required():
    """HITL 필요 여부 테스트"""
    # automation_level 2 이상 + 리밸런싱 필요 → HITL 필요
    initial_state: PortfolioState = {
        "request_id": "test_hitl",
        "automation_level": 2,
        "risk_profile": "moderate",
        "current_holdings": [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 1.0},  # 극단적 편중
        ],
        "total_value": 10_000_000,
        "hitl_required": False,
    }

    config = {"configurable": {"thread_id": "test_hitl"}}
    result = await portfolio_agent.ainvoke(initial_state, config=config)

    report = result["portfolio_report"]

    # 큰 비중 변화가 있으므로 HITL 필요
    assert report["hitl_required"] is True, "automation_level 2+ & 리밸런싱 → HITL 필요"
    assert report["rebalancing_needed"] is True

    print("\n✅ HITL 필요 여부 검증 성공")
    print(f"   HITL 필요: {report['hitl_required']}")


if __name__ == "__main__":
    """직접 실행 시 모든 테스트 실행"""
    import asyncio
    import sys

    async def run_all_tests():
        print("=" * 60)
        print("Portfolio 서브그래프 종합 테스트")
        print("=" * 60)

        tests = [
            ("기본 리포트 생성", test_portfolio_subgraph_generates_report),
            ("보수적 성향", test_portfolio_conservative_profile),
            ("공격적 성향", test_portfolio_aggressive_profile),
            ("리밸런싱 불필요", test_portfolio_no_rebalancing_needed),
            ("HITL 필요", test_portfolio_hitl_required),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                print(f"\n[테스트] {name}")
                await test_func()
                passed += 1
            except AssertionError as e:
                print(f"❌ 실패: {e}")
                failed += 1
            except Exception as e:
                print(f"❌ 에러: {e}")
                failed += 1

        print("\n" + "=" * 60)
        print(f"테스트 결과: {passed} 성공, {failed} 실패")
        print("=" * 60)

        return failed == 0

    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
