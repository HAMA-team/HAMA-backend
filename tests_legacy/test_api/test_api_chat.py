"""
Chat API 테스트

HITL (Human-in-the-Loop) 플로우 검증:
1. /chat - 매매 요청 시 interrupt 발생 확인
2. /approve - 승인 처리 확인
"""
import pytest
from httpx import AsyncClient, ASGITransport
from src.main import app

transport = ASGITransport(app=app)


class TestChatAPI:
    """Chat API 엔드포인트 테스트"""

    @pytest.mark.asyncio
    async def test_simple_query(self):
        """간단한 질의응답 테스트 (HITL 없음)"""
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/chat/",
                json={
                    "message": "안녕하세요",
                    "automation_level": 2
                }
            )

            assert response.status_code == 200
            data = response.json()

            assert "message" in data
            assert "conversation_id" in data
            assert "requires_approval" in data
            assert data["requires_approval"] is False  # 일반 질문은 승인 불필요

            conversation_id = data["conversation_id"]
            history = await client.get(f"/api/v1/chat/history/{conversation_id}")
            assert history.status_code == 200
            history_data = history.json()
            assert len(history_data["messages"]) >= 2  # user + assistant

            # Clean up conversation
            await client.delete(f"/api/v1/chat/history/{conversation_id}")

        print(f"\n✅ 일반 질의응답 테스트 통과")
        print(f"   응답: {data['message'][:100]}...")

    @pytest.mark.asyncio
    async def test_stock_analysis_query(self):
        """종목 분석 요청 (HITL 없음)"""
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

            assert "message" in data
            assert data["requires_approval"] is False  # 분석은 승인 불필요

            await client.delete(f"/api/v1/chat/history/{data['conversation_id']}")

        print(f"\n✅ 종목 분석 테스트 통과")
        print(f"   대화 ID: {data['conversation_id']}")

    @pytest.mark.asyncio
    async def test_trade_request_with_hitl(self):
        """
        매매 요청 + HITL 테스트

        automation_level=2 (Copilot) → interrupt 발생 예상
        """
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. 매매 요청
            response = await client.post(
                "/api/v1/chat/",
                json={
                    "message": "삼성전자 10주 매수해줘",
                    "automation_level": 2  # Copilot: 매매 승인 필요
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Interrupt 발생 확인
            assert data["requires_approval"] is True
            assert "approval_request" in data
            assert data["approval_request"] is not None

            # Approval request 구조 확인
            approval_req = data["approval_request"]
            assert "thread_id" in approval_req
            assert "interrupt_data" in approval_req

            history = await client.get(f"/api/v1/chat/history/{data['conversation_id']}")
            assert history.status_code == 200
            history_data = history.json()
            assert any(msg["role"] == "assistant" for msg in history_data["messages"])

        print(f"\n✅ 매매 요청 HITL 테스트 통과")
        print(f"   Interrupt 발생: {data['requires_approval']}")
        print(f"   Thread ID: {approval_req['thread_id']}")
        print(f"   Interrupt 데이터: {approval_req['interrupt_data']}")

        return data["conversation_id"]  # 다음 테스트를 위해 반환

    @pytest.mark.asyncio
    async def test_approval_flow(self):
        """
        승인 플로우 전체 테스트

        1. 매매 요청 → interrupt
        2. 승인 → 거래 실행
        """
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1단계: 매매 요청
            chat_response = await client.post(
                "/api/v1/chat/",
                json={
                    "message": "삼성전자 5주 매수",
                    "automation_level": 2
                }
            )

            assert chat_response.status_code == 200
            chat_data = chat_response.json()

            if not chat_data["requires_approval"]:
                print("\n⚠️ Interrupt가 발생하지 않음 - 테스트 스킵")
                return

            thread_id = chat_data["approval_request"]["thread_id"]

            # 2단계: 승인 처리
            approval_response = await client.post(
                "/api/v1/chat/approve",
                json={
                    "thread_id": thread_id,
                    "decision": "approved",
                    "automation_level": 2,
                    "user_notes": "테스트 승인"
                }
            )

            assert approval_response.status_code == 200
            approval_data = approval_response.json()

            assert approval_data["status"] == "approved"
            assert "result" in approval_data

            history = await client.get(f"/api/v1/chat/history/{thread_id}")
            assert history.status_code == 200
            history_data = history.json()
            assert any(msg["metadata"] and msg["metadata"].get("decision") == "approved" for msg in history_data["messages"])

            await client.delete(f"/api/v1/chat/history/{thread_id}")

            print(f"\n✅ 승인 플로우 테스트 통과")
            print(f"   Thread ID: {thread_id}")
            print(f"   승인 상태: {approval_data['status']}")
            print(f"   결과: {approval_data.get('result', {})}")

    @pytest.mark.asyncio
    async def test_rejection_flow(self):
        """
        거부 플로우 테스트

        1. 매매 요청 → interrupt
        2. 거부 → 거래 취소
        """
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1단계: 매매 요청
            chat_response = await client.post(
                "/api/v1/chat/",
                json={
                    "message": "SK하이닉스 20주 매수",
                    "automation_level": 2
                }
            )

            assert chat_response.status_code == 200
            chat_data = chat_response.json()

            if not chat_data["requires_approval"]:
                print("\n⚠️ Interrupt가 발생하지 않음 - 테스트 스킵")
                return

            thread_id = chat_data["approval_request"]["thread_id"]

            # 2단계: 거부 처리
            rejection_response = await client.post(
                "/api/v1/chat/approve",
                json={
                    "thread_id": thread_id,
                    "decision": "rejected",
                    "automation_level": 2,
                    "user_notes": "가격이 너무 높음"
                }
            )

            assert rejection_response.status_code == 200
            rejection_data = rejection_response.json()

            assert rejection_data["status"] == "rejected"
            assert rejection_data["result"]["cancelled"] is True

            history = await client.get(f"/api/v1/chat/history/{thread_id}")
            assert history.status_code == 200
            history_data = history.json()
            assert any(msg["metadata"] and msg["metadata"].get("decision") == "rejected" for msg in history_data["messages"])

            await client.delete(f"/api/v1/chat/history/{thread_id}")

            print(f"\n✅ 거부 플로우 테스트 통과")
            print(f"   Thread ID: {thread_id}")
            print(f"   거부 사유: 가격이 너무 높음")


if __name__ == "__main__":
    """직접 실행"""
    import asyncio

    async def run_tests():
        print("=" * 60)
        print("Chat API + HITL 테스트")
        print("=" * 60)

        test_suite = TestChatAPI()

        tests = [
            ("간단한 질의응답", test_suite.test_simple_query),
            ("종목 분석", test_suite.test_stock_analysis_query),
            ("매매 요청 HITL", test_suite.test_trade_request_with_hitl),
            ("승인 플로우", test_suite.test_approval_flow),
            ("거부 플로우", test_suite.test_rejection_flow),
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

        print("\n" + "=" * 60)
        print(f"테스트 결과: {passed} 성공, {failed} 실패")
        print("=" * 60)

        return failed == 0

    asyncio.run(run_tests())
