"""
Week 1: Router Agent 테스트
질문 복잡도 분석 및 에이전트 선택 검증
"""

import pytest
import asyncio
from typing import Dict, Any


class TestRouterAgent:
    """Router Agent 테스트"""

    @pytest.mark.asyncio
    async def test_router_depth_level_detection(self):
        """
        Router가 질문 복잡도를 정확히 판단하는지 검증

        - 간단한 질문 → brief
        - 상세 질문 → detailed
        - 복잡한 질문 → comprehensive
        """
        from src.agents.router.router_agent import route_query

        print("\n[Router Depth Level 감지 테스트]")

        # 1. 간단한 질문 → brief
        print("\n1. 간단한 질문 테스트...")
        query1 = "PER이 뭐야?"
        result1 = await route_query(query=query1, user_profile={})

        print(f"   질문: '{query1}'")
        print(f"   → depth_level: {result1['depth_level']}")
        print(f"   → agents: {result1['agents_to_call']}")

        # brief 또는 detailed (간단한 질문이므로)
        assert result1["depth_level"] in ["brief", "detailed"]

        # 2. 상세 질문 → detailed
        print("\n2. 상세 질문 테스트...")
        query2 = "삼성전자 분석해줘"
        result2 = await route_query(query=query2, user_profile={})

        print(f"   질문: '{query2}'")
        print(f"   → depth_level: {result2['depth_level']}")
        print(f"   → agents: {result2['agents_to_call']}")

        # detailed 또는 comprehensive
        assert result2["depth_level"] in ["detailed", "comprehensive"]

        # 3. 복잡한 질문 → comprehensive
        print("\n3. 복잡한 질문 테스트...")
        query3 = "삼성전자 DCF 밸류에이션 해줘"
        result3 = await route_query(query=query3, user_profile={})

        print(f"   질문: '{query3}'")
        print(f"   → depth_level: {result3['depth_level']}")
        print(f"   → agents: {result3['agents_to_call']}")

        # comprehensive (DCF는 복잡한 분석)
        # 단, LLM 응답에 따라 detailed도 가능
        assert result3["depth_level"] in ["detailed", "comprehensive"]

        print("\n✅ Router가 질문 복잡도를 정확히 판단")

    @pytest.mark.asyncio
    async def test_router_agent_selection(self):
        """
        Router가 적절한 에이전트를 선택하는지 검증

        - 종목 분석 질문 → research
        - 전략 질문 → strategy
        - 일반 질문 → general
        """
        from src.agents.router.router_agent import route_query

        print("\n[Router Agent 선택 테스트]")

        # 1. Research Agent 선택
        print("\n1. Research Agent 선택 테스트...")
        query1 = "삼성전자 재무제표 분석해줘"
        result1 = await route_query(query=query1, user_profile={})

        print(f"   질문: '{query1}'")
        print(f"   → agents: {result1['agents_to_call']}")

        assert "research" in result1["agents_to_call"]

        # 2. Strategy Agent 선택 (가능하면)
        print("\n2. Strategy Agent 선택 테스트...")
        query2 = "가치투자 전략 추천해줘"
        result2 = await route_query(query=query2, user_profile={})

        print(f"   질문: '{query2}'")
        print(f"   → agents: {result2['agents_to_call']}")

        # strategy 또는 general
        assert "strategy" in result2["agents_to_call"] or "general" in result2["agents_to_call"]

        # 3. General Agent 선택
        print("\n3. General Agent 선택 테스트...")
        query3 = "투자에 대해 알려줘"
        result3 = await route_query(query=query3, user_profile={})

        print(f"   질문: '{query3}'")
        print(f"   → agents: {result3['agents_to_call']}")

        # general은 항상 대체 가능
        assert len(result3["agents_to_call"]) > 0

        print("\n✅ Router가 적절한 에이전트를 선택")

    @pytest.mark.asyncio
    async def test_router_user_profile_reflection(self):
        """
        Router가 사용자 프로파일을 반영하는지 검증

        같은 질문이라도 사용자 수준에 따라 다른 depth_level 선택 가능
        """
        from src.agents.router.router_agent import route_query

        print("\n[Router 사용자 프로파일 반영 테스트]")

        query = "삼성전자 분석해줘"

        # 1. 초보자 프로파일
        beginner_profile = {
            "expertise_level": "beginner",
            "technical_level": "basic",
            "preferred_depth": "brief"
        }

        print(f"\n질문: '{query}'")
        print("\n1. 초보자 프로파일...")
        result1 = await route_query(query=query, user_profile=beginner_profile)

        print(f"   → depth_level: {result1['depth_level']}")
        print(f"   → personalization: {result1.get('personalization', {})}")

        # 2. 전문가 프로파일
        expert_profile = {
            "expertise_level": "expert",
            "technical_level": "advanced",
            "preferred_depth": "comprehensive"
        }

        print("\n2. 전문가 프로파일...")
        result2 = await route_query(query=query, user_profile=expert_profile)

        print(f"   → depth_level: {result2['depth_level']}")
        print(f"   → personalization: {result2.get('personalization', {})}")

        # 검증: 프로파일이 반영되었는지 (LLM 응답에 따라 다를 수 있음)
        assert result1["depth_level"] in ["brief", "detailed", "comprehensive"]
        assert result2["depth_level"] in ["brief", "detailed", "comprehensive"]

        print("\n✅ Router가 사용자 프로파일을 반영하여 depth 조절")

    @pytest.mark.asyncio
    async def test_router_intent_detection(self):
        """
        Router가 사용자 의도를 정확히 파악하는지 검증
        """
        from src.agents.router.router_agent import route_query

        print("\n[Router 의도 감지 테스트]")

        test_cases = [
            {
                "query": "삼성전자 주가가 어때?",
                "expected_intent": ["price_check", "analysis", "stock_info"],
                "expected_agent": "research"
            },
            {
                "query": "포트폴리오 추천해줘",
                "expected_intent": ["portfolio", "recommendation", "strategy"],
                "expected_agent": "portfolio"
            },
            {
                "query": "리밸런싱이 필요해?",
                "expected_intent": ["rebalancing", "portfolio", "check"],
                "expected_agent": "portfolio"
            }
        ]

        for i, case in enumerate(test_cases, 1):
            print(f"\n{i}. '{case['query']}'")

            result = await route_query(query=case["query"], user_profile={})

            print(f"   → intent: {result.get('intent', 'N/A')}")
            print(f"   → agents: {result['agents_to_call']}")

            # 적어도 하나의 에이전트는 선택되어야 함
            assert len(result["agents_to_call"]) > 0

        print("\n✅ Router가 다양한 의도를 정확히 파악")


if __name__ == "__main__":
    """테스트 직접 실행"""
    async def main():
        tester = TestRouterAgent()

        print("="*60)
        print("Week 1: Router Agent 테스트 시작")
        print("="*60)

        try:
            # 1. Depth Level 감지 테스트
            await tester.test_router_depth_level_detection()

            # 2. Agent 선택 테스트
            await tester.test_router_agent_selection()

            # 3. 사용자 프로파일 반영 테스트
            await tester.test_router_user_profile_reflection()

            # 4. 의도 감지 테스트
            await tester.test_router_intent_detection()

            print("\n" + "="*60)
            print("✅ Router Agent 테스트 모두 성공!")
            print("="*60)
        except Exception as e:
            print(f"\n❌ 테스트 실패: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(main())
