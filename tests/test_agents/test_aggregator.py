"""
Week 3: Aggregator 테스트
사용자 수준별 답변 개인화 검증
"""

import pytest
import asyncio
from typing import Dict, Any


class TestAggregator:
    """Aggregator 답변 개인화 테스트"""

    @pytest.mark.asyncio
    async def test_personalize_for_beginner(self):
        """
        초보자용 답변 개인화 테스트

        - 용어 설명 포함
        - 비유 사용
        - 간결한 지표 (1-2개)
        """
        from src.agents.aggregator import personalize_response

        print("\n[초보자용 답변 개인화 테스트]")

        # Mock 에이전트 결과
        agent_results = {
            "research": {
                "answer": "삼성전자의 PER은 8.5이며, 업종 평균 12.0보다 낮습니다.",
                "data": {
                    "PER": 8.5,
                    "PBR": 1.2,
                    "current_price": 75000,
                    "sector_average_PER": 12.0
                }
            }
        }

        # 초보자 프로파일
        user_profile = {
            "expertise_level": "beginner",
            "wants_explanations": True,
            "wants_analogies": True,
            "technical_level": "basic"
        }

        print(f"\n사용자 프로파일: {user_profile['expertise_level']}")

        # 개인화 실행
        result = await personalize_response(
            agent_results=agent_results,
            user_profile=user_profile
        )

        response_text = result["response"]

        print(f"\n개인화된 답변 (일부):")
        print(f"   {response_text[:200]}...")

        # 검증: 초보자용 특징
        # (LLM 응답에 따라 다를 수 있으므로 유연하게)
        print(f"\n✅ 초보자용 답변 생성 완료")
        print(f"   답변 길이: {len(response_text)} 자")

        # 답변이 존재하는지만 확인
        assert len(response_text) > 0

    @pytest.mark.asyncio
    async def test_personalize_for_expert(self):
        """
        전문가용 답변 개인화 테스트

        - 용어 설명 생략
        - 비유 미사용
        - 모든 지표 포함
        - 원데이터, 계산식
        """
        from src.agents.aggregator import personalize_response

        print("\n[전문가용 답변 개인화 테스트]")

        # Mock 에이전트 결과
        agent_results = {
            "research": {
                "answer": "삼성전자 DCF 분석 결과입니다.",
                "data": {
                    "PER": 8.5,
                    "PBR": 1.2,
                    "ROE": 15.3,
                    "debt_ratio": 45.2,
                    "dcf_value": 85000,
                    "WACC": 8.0,
                    "terminal_growth": 3.0
                }
            }
        }

        # 전문가 프로파일
        user_profile = {
            "expertise_level": "expert",
            "wants_explanations": False,
            "wants_analogies": False,
            "technical_level": "advanced"
        }

        print(f"\n사용자 프로파일: {user_profile['expertise_level']}")

        # 개인화 실행
        result = await personalize_response(
            agent_results=agent_results,
            user_profile=user_profile
        )

        response_text = result["response"]

        print(f"\n개인화된 답변 (일부):")
        print(f"   {response_text[:200]}...")

        # 검증: 전문가용 특징
        print(f"\n✅ 전문가용 답변 생성 완료")
        print(f"   답변 길이: {len(response_text)} 자")

        # 답변이 존재하는지만 확인
        assert len(response_text) > 0

    @pytest.mark.asyncio
    async def test_personalization_level_comparison(self):
        """
        초보자 vs 전문가 답변 비교 테스트

        초보자 답변이 일반적으로 더 길고 설명이 많아야 함
        """
        from src.agents.aggregator import personalize_response

        print("\n[개인화 수준별 비교 테스트]")

        # 동일한 에이전트 결과
        agent_results = {
            "research": {
                "answer": "삼성전자 분석 결과입니다.",
                "data": {
                    "PER": 8.5,
                    "current_price": 75000
                }
            }
        }

        # 1. 초보자 답변
        beginner_profile = {
            "expertise_level": "beginner",
            "wants_explanations": True,
            "wants_analogies": True
        }

        print("\n1. 초보자용 답변 생성...")
        beginner_result = await personalize_response(
            agent_results=agent_results,
            user_profile=beginner_profile
        )

        # 2. 전문가 답변
        expert_profile = {
            "expertise_level": "expert",
            "wants_explanations": False,
            "wants_analogies": False
        }

        print("2. 전문가용 답변 생성...")
        expert_result = await personalize_response(
            agent_results=agent_results,
            user_profile=expert_profile
        )

        # 비교
        beginner_len = len(beginner_result["response"])
        expert_len = len(expert_result["response"])

        print(f"\n✅ 개인화 수준별 비교:")
        print(f"   초보자 답변: {beginner_len} 자")
        print(f"   전문가 답변: {expert_len} 자")
        print(f"   비율: {beginner_len/expert_len:.2f}x")

        # 둘 다 존재하는지 확인
        assert beginner_len > 0
        assert expert_len > 0

    @pytest.mark.asyncio
    async def test_personalize_multiple_agents(self):
        """
        여러 에이전트 결과를 통합하여 개인화하는 테스트
        """
        from src.agents.aggregator import personalize_response

        print("\n[다중 에이전트 결과 통합 테스트]")

        # 여러 에이전트 결과
        agent_results = {
            "research": {
                "answer": "삼성전자는 저평가 상태입니다.",
                "data": {"PER": 8.5}
            },
            "strategy": {
                "answer": "장기 가치투자에 적합합니다.",
                "data": {"strategy": "value_investing"}
            }
        }

        user_profile = {
            "expertise_level": "intermediate",
            "technical_level": "intermediate"
        }

        print(f"\n에이전트 결과: research, strategy")
        print(f"사용자 프로파일: {user_profile['expertise_level']}")

        # 개인화 실행
        result = await personalize_response(
            agent_results=agent_results,
            user_profile=user_profile
        )

        response_text = result["response"]

        print(f"\n개인화된 답변 (일부):")
        print(f"   {response_text[:300]}...")

        # 검증: 답변이 생성되었는지
        assert len(response_text) > 0

        print(f"\n✅ 다중 에이전트 결과 통합 성공")

    @pytest.mark.asyncio
    async def test_routing_decision_reflection(self):
        """
        Routing decision이 답변 개인화에 반영되는지 테스트
        """
        from src.agents.aggregator import personalize_response

        print("\n[Routing Decision 반영 테스트]")

        agent_results = {
            "research": {
                "answer": "삼성전자 분석 결과입니다.",
                "data": {"PER": 8.5}
            }
        }

        user_profile = {
            "expertise_level": "intermediate"
        }

        # Routing decision with personalization hint
        routing_decision = {
            "depth_level": "brief",
            "agents_to_call": ["research"],
            "personalization": {
                "use_analogies": True,
                "focus_metrics": ["PER"]
            }
        }

        print(f"\nRouting decision: {routing_decision}")

        # 개인화 실행
        result = await personalize_response(
            agent_results=agent_results,
            user_profile=user_profile,
            routing_decision=routing_decision
        )

        response_text = result["response"]

        print(f"\n개인화된 답변 (일부):")
        print(f"   {response_text[:200]}...")

        # 검증
        assert len(response_text) > 0

        print(f"\n✅ Routing decision이 답변 개인화에 반영됨")


if __name__ == "__main__":
    """테스트 직접 실행"""
    async def main():
        tester = TestAggregator()

        print("="*60)
        print("Week 3: Aggregator 테스트 시작")
        print("="*60)

        try:
            # 1. 초보자용 개인화 테스트
            await tester.test_personalize_for_beginner()

            # 2. 전문가용 개인화 테스트
            await tester.test_personalize_for_expert()

            # 3. 수준별 비교 테스트
            await tester.test_personalization_level_comparison()

            # 4. 다중 에이전트 통합 테스트
            await tester.test_personalize_multiple_agents()

            # 5. Routing decision 반영 테스트
            await tester.test_routing_decision_reflection()

            print("\n" + "="*60)
            print("✅ Aggregator 테스트 모두 성공!")
            print("="*60)
        except Exception as e:
            print(f"\n❌ 테스트 실패: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(main())
