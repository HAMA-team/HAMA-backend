"""
E2E 시나리오 테스트 (실제 LLM 연동)

시나리오: "삼성전자와 SK하이닉스 중 어디에 투자해야 할까?"

흐름:
1. Research Agent가 각 종목 분석 (LLM 사용)
2. Strategy Agent가 두 종목 비교 (LLM 사용)
3. 최종 투자 의견 도출
"""

import asyncio
import sys
sys.path.insert(0, '/Users/elaus/PycharmProjects/HAMA-backend')

from src.agents.research import research_agent
from src.agents.strategy import strategy_agent
from src.schemas.agent import AgentInput, AgentOutput
import uuid


async def test_research_samsung():
    """삼성전자 분석 테스트"""
    print("\n" + "="*80)
    print("📊 TEST 1: 삼성전자 종목 분석")
    print("="*80)

    input_data = AgentInput(
        request_id=str(uuid.uuid4()),
        user_id="test_user",
        context={"stock_code": "005930"},
        automation_level=2
    )

    result = await research_agent.process(input_data)

    assert result.status == "success", f"Expected success, got {result.status}: {result.error}"
    assert "analysis" in result.data, "Analysis not found in result"

    analysis = result.data["analysis"]
    print(f"\n✅ 분석 완료!")
    print(f"종목명: {result.data.get('stock_name')}")
    print(f"투자 의견: {analysis.get('recommendation')}")
    print(f"신뢰도: {analysis.get('confidence')}/5")
    print(f"현재가: {analysis.get('current_price'):,}원")
    print(f"목표가: {analysis.get('target_price'):,}원")
    print(f"핵심 포인트:")
    for i, point in enumerate(analysis.get('key_points', []), 1):
        print(f"  {i}. {point}")
    print(f"리스크:")
    for i, risk in enumerate(analysis.get('risks', []), 1):
        print(f"  {i}. {risk}")
    print(f"요약: {analysis.get('summary')}")

    return result


async def test_research_skhynix():
    """SK하이닉스 분석 테스트"""
    print("\n" + "="*80)
    print("📊 TEST 2: SK하이닉스 종목 분석")
    print("="*80)

    input_data = AgentInput(
        request_id=str(uuid.uuid4()),
        user_id="test_user",
        context={"stock_code": "000660"},
        automation_level=2
    )

    result = await research_agent.process(input_data)

    assert result.status == "success", f"Expected success, got {result.status}: {result.error}"
    assert "analysis" in result.data, "Analysis not found in result"

    analysis = result.data["analysis"]
    print(f"\n✅ 분석 완료!")
    print(f"종목명: {result.data.get('stock_name')}")
    print(f"투자 의견: {analysis.get('recommendation')}")
    print(f"신뢰도: {analysis.get('confidence')}/5")
    print(f"현재가: {analysis.get('current_price'):,}원")
    print(f"목표가: {analysis.get('target_price'):,}원")
    print(f"핵심 포인트:")
    for i, point in enumerate(analysis.get('key_points', []), 1):
        print(f"  {i}. {point}")
    print(f"리스크:")
    for i, risk in enumerate(analysis.get('risks', []), 1):
        print(f"  {i}. {risk}")
    print(f"요약: {analysis.get('summary')}")

    return result


async def test_strategy_comparison():
    """두 종목 비교 전략 테스트"""
    print("\n" + "="*80)
    print("🎯 TEST 3: 삼성전자 vs SK하이닉스 비교 분석")
    print("="*80)

    input_data = AgentInput(
        request_id=str(uuid.uuid4()),
        user_id="test_user",
        context={"stock_codes": ["005930", "000660"]},
        automation_level=2
    )

    result = await strategy_agent.process(input_data)

    assert result.status == "success", f"Expected success, got {result.status}: {result.error}"
    assert "comparison" in result.data, "Comparison not found in result"

    comparison = result.data["comparison"]
    print(f"\n✅ 비교 분석 완료!")
    print(f"\n🏆 추천 종목: {comparison.get('recommended_name')} ({comparison.get('recommended_stock')})")
    print(f"\n📝 추천 이유:")
    for i, reason in enumerate(comparison.get('reasons', []), 1):
        print(f"  {i}. {reason}")
    print(f"\n🔍 다른 종목과의 차이점:")
    for i, diff in enumerate(comparison.get('differences', []), 1):
        print(f"  {i}. {diff}")
    print(f"\n💡 투자 전략: {comparison.get('strategy')}")
    print(f"⚠️  위험도: {comparison.get('risk_level')}/5")
    print(f"\n📌 최종 의견: {comparison.get('final_opinion')}")

    return result


async def test_full_scenario():
    """전체 시나리오 테스트"""
    print("\n" + "🚀"*40)
    print("E2E 시나리오 테스트: 삼성전자 vs SK하이닉스 투자 비교")
    print("🚀"*40)

    print("\n[시나리오]")
    print("사용자 질문: '삼성전자와 SK하이닉스 중 어디에 투자해야 할까?'")
    print("\n[처리 플로우]")
    print("1. Research Agent: 삼성전자 분석")
    print("2. Research Agent: SK하이닉스 분석")
    print("3. Strategy Agent: 두 종목 비교 및 최종 의견")

    # 1. 삼성전자 분석
    samsung_result = await test_research_samsung()

    # 2. SK하이닉스 분석
    skhynix_result = await test_research_skhynix()

    # 3. 비교 분석
    comparison_result = await test_strategy_comparison()

    print("\n" + "="*80)
    print("🎉 전체 시나리오 테스트 완료!")
    print("="*80)

    print("\n📊 최종 결과 요약:")
    samsung_analysis = samsung_result.data["analysis"]
    skhynix_analysis = skhynix_result.data["analysis"]
    comparison = comparison_result.data["comparison"]

    print(f"\n1️⃣  삼성전자 (005930)")
    print(f"   - 의견: {samsung_analysis.get('recommendation')}")
    print(f"   - 현재가: {samsung_analysis.get('current_price'):,}원")
    print(f"   - 목표가: {samsung_analysis.get('target_price'):,}원")
    print(f"   - 요약: {samsung_analysis.get('summary')}")

    print(f"\n2️⃣  SK하이닉스 (000660)")
    print(f"   - 의견: {skhynix_analysis.get('recommendation')}")
    print(f"   - 현재가: {skhynix_analysis.get('current_price'):,}원")
    print(f"   - 목표가: {skhynix_analysis.get('target_price'):,}원")
    print(f"   - 요약: {skhynix_analysis.get('summary')}")

    print(f"\n🏆 최종 추천: {comparison.get('recommended_name')} ({comparison.get('recommended_stock')})")
    print(f"📌 이유: {comparison.get('final_opinion')}")

    print("\n" + "✅"*40)
    print("모든 테스트 통과! 실제 LLM 연동 성공!")
    print("✅"*40)


if __name__ == "__main__":
    asyncio.run(test_full_scenario())
