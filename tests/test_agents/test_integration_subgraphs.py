"""
Research + Strategy 서브그래프 통합 테스트

Master Graph에서 두 서브그래프가 연계되어 작동하는지 검증
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage
from src.agents.graph_master import build_graph


async def test_research_strategy_integration():
    """
    Research → Strategy 서브그래프 통합 테스트

    Flow:
    1. 사용자: "삼성전자 분석하고 투자 전략 세워줘"
    2. analyze_intent → determine_agents
    3. research_call (서브그래프)
    4. strategy_call (서브그래프)
    5. aggregate_results
    """
    print("\n" + "=" * 60)
    print("🧪 Research + Strategy 서브그래프 통합 테스트")
    print("=" * 60)

    # 초기 상태
    initial_state = {
        "messages": [HumanMessage(content="삼성전자 분석하고 투자 전략 세워줘")],
        "user_id": "test_user",
        "conversation_id": "test_integration_001",
        "automation_level": 2,
        "intent": None,
        "agents_to_call": [],
        "agents_called": [],
        "agent_results": {},
        "risk_status": "safe",
        "requires_approval": False,
        "approval_type": None,
        "final_response": None,
        "summary": None,
    }

    print(f"\n📤 사용자 요청: {initial_state['messages'][0].content}")
    print(f"📍 자동화 레벨: {initial_state['automation_level']}")

    # Master Graph 빌드
    app = build_graph(automation_level=initial_state['automation_level'])

    # Config 설정 (Checkpointer 필요)
    config = {
        "configurable": {
            "thread_id": initial_state["conversation_id"]
        }
    }

    # Master Graph 실행
    result = await app.ainvoke(initial_state, config=config)

    print(f"\n📊 실행 결과:")
    print(f"  - 의도 분석: {result.get('intent', 'N/A')}")
    print(f"  - 호출된 에이전트: {', '.join(result.get('agents_called', []))}")

    # Research Agent 결과 확인
    research_result = result.get("agent_results", {}).get("research_agent")
    if research_result:
        print(f"\n✅ Research Agent 결과:")
        print(f"  - 분석 완료: {research_result.get('stock_code', 'N/A')}")
        consensus = research_result.get("consensus", {})
        print(f"  - 투자의견: {consensus.get('recommendation', 'N/A')}")
        print(f"  - 신뢰도: {consensus.get('confidence', 0):.0%}")
    else:
        print(f"\n❌ Research Agent 결과 없음")

    # Strategy Agent 결과 확인
    strategy_result = result.get("agent_results", {}).get("strategy_agent")
    if strategy_result:
        print(f"\n✅ Strategy Agent 결과:")
        blueprint = strategy_result.get("blueprint", {})
        market_outlook = blueprint.get("market_outlook", {})
        asset_allocation = blueprint.get("asset_allocation", {})
        sector_strategy = blueprint.get("sector_strategy", {})

        print(f"  - 시장 사이클: {market_outlook.get('cycle', 'N/A')}")
        print(f"  - 주식 비중: {asset_allocation.get('stocks', 0):.0%}")
        print(f"  - 핵심 섹터: {', '.join(sector_strategy.get('overweight', [])[:2])}")
    else:
        print(f"\n❌ Strategy Agent 결과 없음")

    # 최종 응답 확인
    final_response = result.get("final_response")
    if final_response:
        print(f"\n💬최종 응답:")
        print(f"  메시지: {final_response.get('message', 'N/A')[:100]}...")

        if final_response.get("data"):
            print(f"\n📈 데이터 포함:")
            for agent_name, agent_data in final_response["data"].items():
                print(f"  - {agent_name}: ✅")
    else:
        print(f"\n❌ 최종 응답 없음")

    print("\n✅ 통합 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(test_research_strategy_integration())
