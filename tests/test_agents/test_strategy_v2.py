"""
Strategy Agent v2.0 테스트

거시 대전략 수립 기능 검증
"""

import asyncio
import sys
sys.path.insert(0, '/Users/elaus/PycharmProjects/HAMA-backend')

from src.agents.strategy import strategy_agent
from src.schemas.agent import AgentInput
import uuid
import json


async def test_strategy_basic():
    """기본 전략 생성 테스트"""
    print("\n" + "="*80)
    print("🎯 TEST 1: 기본 Strategic Blueprint 생성")
    print("="*80)

    input_data = AgentInput(
        request_id=str(uuid.uuid4()),
        user_id="test_user",
        context={
            "user_preferences": {
                "sectors": ["IT", "헬스케어"],
                "style": "growth",
                "horizon": "mid_term"
            },
            "risk_tolerance": "moderate"
        },
        automation_level=2
    )

    result = await strategy_agent.process(input_data)

    assert result.status == "success", f"Expected success, got {result.status}: {result.error}"
    assert "blueprint" in result.data, "Blueprint not found in result"

    blueprint = result.data["blueprint"]
    print(f"\n✅ Strategic Blueprint 생성 완료!")
    print(f"\n📊 시장 전망:")
    print(f"   사이클: {blueprint['market_outlook']['cycle']}")
    print(f"   신뢰도: {blueprint['market_outlook']['confidence']:.0%}")
    print(f"   요약: {blueprint['market_outlook']['summary']}")

    print(f"\n💼 섹터 전략:")
    print(f"   비중 확대: {', '.join(blueprint['sector_strategy']['overweight'])}")
    print(f"   비중 축소: {', '.join(blueprint['sector_strategy']['underweight'])}")

    print(f"\n💰 자산 배분:")
    print(f"   주식: {float(blueprint['asset_allocation']['stocks']):.0%}")
    print(f"   현금: {float(blueprint['asset_allocation']['cash']):.0%}")

    print(f"\n📈 투자 스타일:")
    print(f"   유형: {blueprint['investment_style']['type']}")
    print(f"   기간: {blueprint['investment_style']['horizon']}")
    print(f"   방식: {blueprint['investment_style']['approach']}")

    print(f"\n🎯 제약조건:")
    print(f"   최대 종목 수: {blueprint['constraints']['max_stocks']}")
    print(f"   종목당 최대 비중: {blueprint['constraints']['max_per_stock']:.0%}")

    return result


async def test_strategy_conservative():
    """보수적 리스크 허용도 테스트"""
    print("\n" + "="*80)
    print("🎯 TEST 2: 보수적 리스크 허용도")
    print("="*80)

    input_data = AgentInput(
        request_id=str(uuid.uuid4()),
        context={
            "risk_tolerance": "conservative"
        }
    )

    result = await strategy_agent.process(input_data)
    blueprint = result.data["blueprint"]

    stocks_ratio = float(blueprint['asset_allocation']['stocks'])
    print(f"\n✅ 주식 비중: {stocks_ratio:.0%}")
    assert stocks_ratio <= 0.65, f"보수적 전략의 주식 비중이 너무 높음: {stocks_ratio:.0%}"


async def test_strategy_aggressive():
    """공격적 리스크 허용도 테스트"""
    print("\n" + "="*80)
    print("🎯 TEST 3: 공격적 리스크 허용도")
    print("="*80)

    input_data = AgentInput(
        request_id=str(uuid.uuid4()),
        context={
            "risk_tolerance": "aggressive"
        }
    )

    result = await strategy_agent.process(input_data)
    blueprint = result.data["blueprint"]

    stocks_ratio = float(blueprint['asset_allocation']['stocks'])
    print(f"\n✅ 주식 비중: {stocks_ratio:.0%}")
    assert stocks_ratio >= 0.80, f"공격적 전략의 주식 비중이 너무 낮음: {stocks_ratio:.0%}"


async def main():
    """모든 테스트 실행"""
    print("\n" + "="*80)
    print("🚀 Strategy Agent v2.0 통합 테스트 시작")
    print("="*80)

    try:
        # Test 1: 기본 전략
        await test_strategy_basic()

        # Test 2: 보수적 전략
        await test_strategy_conservative()

        # Test 3: 공격적 전략
        await test_strategy_aggressive()

        print("\n" + "="*80)
        print("✅ 모든 테스트 통과!")
        print("="*80 + "\n")

    except AssertionError as e:
        print(f"\n❌ 테스트 실패: {e}\n")
        raise
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}\n")
        raise


if __name__ == "__main__":
    asyncio.run(main())
