"""
Risk Agent 서브그래프 테스트

리스크 평가 워크플로우 검증
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.risk import risk_subgraph


async def test_risk_subgraph():
    """
    Risk Agent 서브그래프 단위 테스트

    Flow:
    1. collect_data → 포트폴리오 데이터 수집
    2. concentration_check → 집중도 리스크
    3. market_risk → 시장 리스크 (VaR, 변동성)
    4. final_assessment → 최종 평가
    """
    print("\n" + "=" * 60)
    print("🧪 Risk Agent 서브그래프 테스트")
    print("=" * 60)

    # 초기 상태
    initial_state = {
        "request_id": "test_risk_001",
        "portfolio_data": None,
        "market_data": None,
        "concentration_risk": None,
        "market_risk": None,
        "risk_assessment": None,
        "error": None,
    }

    print(f"\n📤 초기 상태: {initial_state['request_id']}")

    # 서브그래프 실행
    result = await risk_subgraph.ainvoke(initial_state)

    print(f"\n📊 실행 결과:")

    # Portfolio 데이터
    portfolio = result.get("portfolio_data")
    if portfolio:
        print(f"\n✅ 포트폴리오 데이터:")
        print(f"  - 총 자산: {portfolio.get('total_value'):,}원")
        print(f"  - 보유 종목: {len(portfolio.get('holdings', []))}개")
        for holding in portfolio.get("holdings", []):
            print(f"    · {holding['stock_name']}: {holding['weight']:.0%}")

    # 집중도 리스크
    concentration = result.get("concentration_risk")
    if concentration:
        print(f"\n✅ 집중도 리스크:")
        print(f"  - HHI: {concentration.get('hhi', 0):.3f}")
        print(f"  - 레벨: {concentration.get('level')}")
        print(f"  - 최대 종목 비중: {concentration.get('top_holding_weight', 0):.0%}")
        print(f"  - 최대 섹터 비중: {concentration.get('top_sector_weight', 0):.0%}")
        if concentration.get("warnings"):
            print(f"  - 경고: {len(concentration['warnings'])}개")

    # 시장 리스크
    market = result.get("market_risk")
    if market:
        print(f"\n✅ 시장 리스크:")
        print(f"  - 포트폴리오 변동성: {market.get('portfolio_volatility', 0):.2%}")
        print(f"  - 포트폴리오 베타: {market.get('portfolio_beta', 0):.2f}")
        print(f"  - VaR 95%: {market.get('var_95', 0):.2%}")
        print(f"  - 최대 손실 추정: {market.get('max_drawdown_estimate', 0):.2%}")
        print(f"  - 리스크 레벨: {market.get('risk_level')}")

    # 최종 평가
    assessment = result.get("risk_assessment")
    if assessment:
        print(f"\n✅ 최종 리스크 평가:")
        print(f"  - 리스크 레벨: {assessment.get('risk_level')}")
        print(f"  - 리스크 점수: {assessment.get('risk_score', 0):.0f}/100")
        print(f"  - HITL 트리거: {assessment.get('should_trigger_hitl')}")

        warnings = assessment.get("warnings", [])
        if warnings:
            print(f"\n  ⚠️  경고 ({len(warnings)}개):")
            for warning in warnings:
                print(f"    - {warning}")

        recommendations = assessment.get("recommendations", [])
        if recommendations:
            print(f"\n  💡 권고사항 ({len(recommendations)}개):")
            for rec in recommendations:
                print(f"    - {rec}")

    print("\n✅ Risk Agent 서브그래프 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(test_risk_subgraph())
