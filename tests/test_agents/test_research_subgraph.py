"""
Research Agent 서브그래프 테스트

LangGraph 네이티브 구현 검증
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.research import research_subgraph


async def test_research_subgraph():
    """
    Research 서브그래프 기본 실행 테스트

    Flow:
    collect_data → [bull_analysis, bear_analysis] → consensus
    """
    print("\n" + "=" * 60)
    print("🧪 Research 서브그래프 테스트")
    print("=" * 60)

    # 초기 상태
    initial_state = {
        "stock_code": "005930",  # 삼성전자
        "request_id": "test_001",
        "price_data": None,
        "financial_data": None,
        "company_data": None,
        "bull_analysis": None,
        "bear_analysis": None,
        "consensus": None,
        "error": None,
    }

    print(f"\n📤 서브그래프 실행: {initial_state['stock_code']}")

    # 서브그래프 실행
    result = await research_subgraph.ainvoke(initial_state)

    print(f"\n📊 결과:")
    print(f"  - 주가 데이터: {'✅' if result.get('price_data') else '❌'}")
    print(f"  - 재무 데이터: {'✅' if result.get('financial_data') else '❌'}")
    print(f"  - 기업 정보: {'✅' if result.get('company_data') else '❌'}")
    print(f"  - 강세 분석: {'✅' if result.get('bull_analysis') else '❌'}")
    print(f"  - 약세 분석: {'✅' if result.get('bear_analysis') else '❌'}")
    print(f"  - 최종 의견: {'✅' if result.get('consensus') else '❌'}")

    if result.get("error"):
        print(f"\n❌ 에러: {result['error']}")
    elif result.get("consensus"):
        consensus = result["consensus"]
        print(f"\n✅ 최종 의견:")
        print(f"  - 추천: {consensus.get('recommendation')}")
        print(f"  - 목표가: {consensus.get('target_price'):,}원")
        print(f"  - 현재가: {consensus.get('current_price'):,}원")
        print(f"  - 상승 여력: {consensus.get('upside_potential')}")
        print(f"  - 신뢰도: {consensus.get('confidence')}/5")
        print(f"  - 요약: {consensus.get('summary')}")

    print("\n✅ 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(test_research_subgraph())
