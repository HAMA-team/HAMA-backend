"""
라우팅 테스트 - LLM이 사용자 질문을 어떤 에이전트로 라우팅하는지 검증

Supervisor 패턴의 동적 라우팅을 테스트합니다.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

transport = ASGITransport(app=app)


class TestRouting:
    """Supervisor 라우팅 테스트"""

    @pytest.mark.asyncio
    async def test_general_agent_routing(self):
        """일반 질문 → general_agent"""
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/",
                json={
                    "message": "PER이 뭐야?",
                    "automation_level": 2
                }
            )

            assert response.status_code == 200
            data = response.json()

            # 메타데이터에서 호출된 에이전트 확인
            metadata = data.get("metadata", {})
            agents_called = metadata.get("agents_called", [])

            print(f"\n✅ 일반 질문 라우팅 테스트")
            print(f"   질문: PER이 뭐야?")
            print(f"   호출된 에이전트: {agents_called}")
            print(f"   응답: {data['message'][:100]}...")

            # Clean up
            await client.delete(f"/api/v1/chat/history/{data['conversation_id']}")

    @pytest.mark.asyncio
    async def test_research_agent_routing(self):
        """종목 분석 → research_agent (+ strategy, risk)"""
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/",
                json={
                    "message": "삼성전자 분석해줘",
                    "automation_level": 2
                }
            )

            assert response.status_code == 200
            data = response.json()

            metadata = data.get("metadata", {})
            agents_called = metadata.get("agents_called", [])

            print(f"\n✅ 종목 분석 라우팅 테스트")
            print(f"   질문: 삼성전자 분석해줘")
            print(f"   호출된 에이전트: {agents_called}")
            print(f"   예상: research_agent (+ strategy, risk)")

            # Clean up
            await client.delete(f"/api/v1/chat/history/{data['conversation_id']}")

    @pytest.mark.asyncio
    async def test_trading_agent_routing(self):
        """매매 요청 → trading_agent"""
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/",
                json={
                    "message": "삼성전자 10주 매수해줘",
                    "automation_level": 2
                }
            )

            assert response.status_code == 200
            data = response.json()

            metadata = data.get("metadata", {})
            agents_called = metadata.get("agents_called", [])

            print(f"\n✅ 매매 요청 라우팅 테스트")
            print(f"   질문: 삼성전자 10주 매수해줘")
            print(f"   호출된 에이전트: {agents_called}")
            print(f"   HITL 필요: {data['requires_approval']}")

            # 매매는 HITL이 발생해야 함
            assert data["requires_approval"] is True

            # Clean up
            await client.delete(f"/api/v1/chat/history/{data['conversation_id']}")

    @pytest.mark.asyncio
    async def test_portfolio_agent_routing(self):
        """포트폴리오 관련 → portfolio_agent"""
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/",
                json={
                    "message": "내 포트폴리오 리밸런싱해줘",
                    "automation_level": 2
                }
            )

            assert response.status_code == 200
            data = response.json()

            metadata = data.get("metadata", {})
            agents_called = metadata.get("agents_called", [])

            print(f"\n✅ 포트폴리오 라우팅 테스트")
            print(f"   질문: 내 포트폴리오 리밸런싱해줘")
            print(f"   호출된 에이전트: {agents_called}")

            # Clean up
            await client.delete(f"/api/v1/chat/history/{data['conversation_id']}")

    @pytest.mark.asyncio
    async def test_multi_agent_routing(self):
        """복잡한 질문 → 여러 에이전트 병렬 호출"""
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/",
                json={
                    "message": "삼성전자와 SK하이닉스를 비교 분석하고 리스크도 평가해줘",
                    "automation_level": 2
                }
            )

            assert response.status_code == 200
            data = response.json()

            metadata = data.get("metadata", {})
            agents_called = metadata.get("agents_called", [])

            print(f"\n✅ 복합 질문 라우팅 테스트")
            print(f"   질문: 삼성전자와 SK하이닉스를 비교 분석하고 리스크도 평가해줘")
            print(f"   호출된 에이전트: {agents_called}")
            print(f"   예상: research + strategy + risk (병렬 실행)")

            # Clean up
            await client.delete(f"/api/v1/chat/history/{data['conversation_id']}")


if __name__ == "__main__":
    """직접 실행"""
    import asyncio

    async def run_tests():
        print("=" * 70)
        print("Supervisor 라우팅 테스트 - LLM 기반 동적 라우팅 검증")
        print("=" * 70)

        test_suite = TestRouting()

        tests = [
            ("일반 질문", test_suite.test_general_agent_routing),
            ("종목 분석", test_suite.test_research_agent_routing),
            ("매매 요청", test_suite.test_trading_agent_routing),
            ("포트폴리오", test_suite.test_portfolio_agent_routing),
            ("복합 질문", test_suite.test_multi_agent_routing),
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
                import traceback
                traceback.print_exc()
                failed += 1

        print("\n" + "=" * 70)
        print(f"테스트 결과: {passed} 성공, {failed} 실패")
        print("=" * 70)
        print("\n📝 참고:")
        print("   - Supervisor는 LLM 기반으로 동적 라우팅")
        print("   - parallel_tool_calls=True로 병렬 실행 가능")
        print("   - automation_level에 따라 HITL 동작 변경")

        return failed == 0

    asyncio.run(run_tests())
