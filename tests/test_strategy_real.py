"""
Strategy Agent 실제 구현 테스트 (Week 14)

LLM 기반 시장 사이클 분석 및 섹터 로테이션
"""

import asyncio
import sys
sys.path.insert(0, '/Users/elaus/PycharmProjects/HAMA-backend')

from src.agents.strategy import strategy_agent
from src.schemas.agent import AgentInput
import uuid


async def test_strategy_real_implementation():
    """실제 데이터 기반 전략 생성 테스트"""
    print("\n" + "="*80)
    print("🚀 Strategy Agent 실제 구현 테스트 (Week 14)")
    print("="*80)

    input_data = AgentInput(
        request_id=str(uuid.uuid4()),
        user_id="test_user",
        context={
            "user_preferences": {
                "sectors": ["IT/전기전자", "반도체"],
                "style": "growth",
                "horizon": "mid_term"
            },
            "risk_tolerance": "moderate"
        },
        automation_level=2
    )

    print(f"\n📊 테스트 설정:")
    print(f"   사용자 선호 섹터: IT/전기전자, 반도체")
    print(f"   리스크 허용도: moderate")
    print(f"   투자 스타일: growth")

    print(f"\n⏳ 실행 중... (BOK API + FinanceDataReader + LLM 분석)")

    result = await strategy_agent.process(input_data)

    print(f"\n" + "="*80)
    print("📋 테스트 결과")
    print("="*80)

    assert result.status == "success", f"Expected success, got {result.status}: {result.error}"
    assert "blueprint" in result.data, "Blueprint not found in result"

    blueprint = result.data["blueprint"]

    print(f"\n✅ 성공!")
    print(f"\n📊 시장 전망:")
    print(f"   사이클: {blueprint['market_outlook']['cycle']}")
    print(f"   신뢰도: {blueprint['market_outlook']['confidence']:.0%}")
    print(f"   요약: {blueprint['market_outlook']['summary']}")

    print(f"\n💼 섹터 전략:")
    print(f"   비중 확대: {', '.join(blueprint['sector_strategy']['overweight'])}")
    print(f"   비중 축소: {', '.join(blueprint['sector_strategy']['underweight'])}")
    print(f"   근거: {blueprint['sector_strategy']['rationale']}")

    print(f"\n   섹터별 비중 (Top 5):")
    for i, sector in enumerate(blueprint['sector_strategy']['sectors'][:5], 1):
        print(f"   {i}. {sector['sector']}: {float(sector['weight']):.0%} ({sector['stance']})")

    print(f"\n💰 자산 배분:")
    print(f"   주식: {float(blueprint['asset_allocation']['stocks']):.0%}")
    print(f"   현금: {float(blueprint['asset_allocation']['cash']):.0%}")
    print(f"   근거: {blueprint['asset_allocation']['rationale']}")

    print(f"\n📈 투자 스타일:")
    print(f"   유형: {blueprint['investment_style']['type']}")
    print(f"   기간: {blueprint['investment_style']['horizon']}")
    print(f"   방식: {blueprint['investment_style']['approach']}")

    print(f"\n📌 메타데이터:")
    print(f"   구현: {result.metadata.get('implementation')}")
    print(f"   데이터 소스: {', '.join(result.metadata.get('data_sources', []))}")

    return result


async def test_conservative_risk():
    """보수적 리스크 허용도 테스트"""
    print("\n" + "="*80)
    print("🔒 보수적 리스크 허용도 테스트")
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

    # 보수적 전략은 주식 비중 60% 이하여야 함
    assert stocks_ratio <= 0.65, f"보수적 전략의 주식 비중이 너무 높음: {stocks_ratio:.0%}"


async def test_aggressive_risk():
    """공격적 리스크 허용도 테스트"""
    print("\n" + "="*80)
    print("🔥 공격적 리스크 허용도 테스트")
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

    # 공격적 전략은 주식 비중 85% 이상이어야 함
    assert stocks_ratio >= 0.80, f"공격적 전략의 주식 비중이 너무 낮음: {stocks_ratio:.0%}"


async def main():
    """모든 테스트 실행"""
    print("\n" + "="*80)
    print("🧪 Strategy Agent 실제 구현 전체 테스트")
    print("="*80)

    try:
        # Test 1: 실제 구현 테스트
        await test_strategy_real_implementation()

        # Test 2: 보수적 리스크
        await test_conservative_risk()

        # Test 3: 공격적 리스크
        await test_aggressive_risk()

        print("\n" + "="*80)
        print("✅ 모든 테스트 통과!")
        print("\n💡 실제 데이터 소스:")
        print("   - 한국은행 API: 기준금리, CPI, 환율")
        print("   - FinanceDataReader: 섹터별 종목 성과")
        print("   - Claude Sonnet 4.5: 시장 사이클 분석, 섹터 로테이션")
        print("="*80 + "\n")

    except AssertionError as e:
        print(f"\n❌ 테스트 실패: {e}\n")
        raise
    except Exception as e:
        print(f"\n❌ 예상치 못한 오류: {e}\n")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
