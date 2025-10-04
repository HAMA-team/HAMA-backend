"""
Strategy Agent 서브그래프 테스트

LangGraph 네이티브 구현 검증
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.strategy import strategy_subgraph


async def test_strategy_subgraph():
    """
    Strategy 서브그래프 기본 실행 테스트

    Flow:
    market_analysis → sector_rotation → asset_allocation → blueprint_creation
    """
    print("\n" + "=" * 60)
    print("🧪 Strategy 서브그래프 테스트")
    print("=" * 60)

    # 초기 상태
    initial_state = {
        "request_id": "test_002",
        "user_preferences": {
            "style": "growth",
            "horizon": "mid_term",
            "approach": "dollar_cost_averaging",
            "size": "large"
        },
        "risk_tolerance": "moderate",
        "market_outlook": None,
        "sector_strategy": None,
        "asset_allocation": None,
        "blueprint": None,
        "error": None,
    }

    print(f"\n📤 서브그래프 실행 (리스크 허용도: {initial_state['risk_tolerance']})")

    # 서브그래프 실행
    result = await strategy_subgraph.ainvoke(initial_state)

    print(f"\n📊 결과:")
    print(f"  - 시장 분석: {'✅' if result.get('market_outlook') else '❌'}")
    print(f"  - 섹터 전략: {'✅' if result.get('sector_strategy') else '❌'}")
    print(f"  - 자산 배분: {'✅' if result.get('asset_allocation') else '❌'}")
    print(f"  - Blueprint: {'✅' if result.get('blueprint') else '❌'}")

    if result.get("error"):
        print(f"\n❌ 에러: {result['error']}")
    elif result.get("blueprint"):
        blueprint = result["blueprint"]
        market_outlook = blueprint.get("market_outlook", {})
        sector_strategy = blueprint.get("sector_strategy", {})
        asset_allocation = blueprint.get("asset_allocation", {})

        print(f"\n✅ Strategic Blueprint:")
        print(f"  - 시장 사이클: {market_outlook.get('cycle')}")
        print(f"  - 시장 신뢰도: {market_outlook.get('confidence', 0):.0%}")
        print(f"  - Overweight 섹터: {', '.join(sector_strategy.get('overweight', [])[:3])}")
        print(f"  - Underweight 섹터: {', '.join(sector_strategy.get('underweight', [])[:3])}")
        print(f"  - 주식 비중: {asset_allocation.get('stocks', 0):.0%}")
        print(f"  - 현금 비중: {asset_allocation.get('cash', 0):.0%}")
        print(f"  - 전체 신뢰도: {blueprint.get('confidence_score', 0):.0%}")

    print("\n✅ 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(test_strategy_subgraph())
