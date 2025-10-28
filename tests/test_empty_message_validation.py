"""
빈 메시지 검증 테스트

빈 메시지가 LLM API에 전달되지 않도록 하는 검증 로직 테스트
"""
import pytest
from pydantic import ValidationError

from src.api.routes.chat import ChatRequest
from src.agents.general.nodes import answer_question_node
from src.agents.router.router_agent import route_query


class TestEmptyMessageValidation:
    """빈 메시지 검증 테스트"""

    def test_chat_request_empty_message_validation(self):
        """ChatRequest 스키마가 빈 메시지를 거부하는지 테스트"""
        # 빈 메시지는 ValidationError 발생해야 함
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message="")

        # 에러 메시지 확인
        errors = exc_info.value.errors()
        assert any("min_length" in str(error) for error in errors)

    def test_chat_request_whitespace_only_message_validation(self):
        """공백만 있는 메시지도 거부하는지 테스트"""
        # 공백만 있는 메시지도 ValidationError 발생해야 함
        with pytest.raises(ValidationError):
            ChatRequest(message="   ")

    def test_chat_request_valid_message(self):
        """정상적인 메시지는 통과하는지 테스트"""
        # 정상 메시지는 검증 통과
        request = ChatRequest(message="삼성전자 분석해줘")
        assert request.message == "삼성전자 분석해줘"

    async def test_general_agent_empty_query_handling(self):
        """General Agent가 빈 쿼리를 안전하게 처리하는지 테스트"""
        # 빈 쿼리로 호출
        state = {
            "query": "",
            "messages": [],
        }

        result = await answer_question_node(state)

        # 에러 대신 안전한 응답 반환
        assert "answer" in result
        assert "비어있습니다" in result["answer"]
        assert "sources" in result
        assert result["sources"] == []

    async def test_general_agent_whitespace_query_handling(self):
        """General Agent가 공백 쿼리를 안전하게 처리하는지 테스트"""
        # 공백만 있는 쿼리로 호출
        state = {
            "query": "   \n\t  ",
            "messages": [],
        }

        result = await answer_question_node(state)

        # 에러 대신 안전한 응답 반환
        assert "answer" in result
        assert "비어있습니다" in result["answer"]

    async def test_router_agent_empty_query_handling(self):
        """Router Agent가 빈 쿼리를 안전하게 처리하는지 테스트"""
        # 빈 쿼리로 호출
        result = await route_query(
            query="",
            user_profile={},
            conversation_history=None,
        )

        # 기본 라우팅 반환
        assert result.agents_to_call == ["general"]
        assert "빈 질문" in result.reasoning

    async def test_router_agent_whitespace_query_handling(self):
        """Router Agent가 공백 쿼리를 안전하게 처리하는지 테스트"""
        # 공백만 있는 쿼리로 호출
        result = await route_query(
            query="   \n\t  ",
            user_profile={},
            conversation_history=None,
        )

        # 기본 라우팅 반환
        assert result.agents_to_call == ["general"]
        assert "빈 질문" in result.reasoning


if __name__ == "__main__":
    """테스트 직접 실행"""
    import asyncio

    async def main():
        tester = TestEmptyMessageValidation()

        print("1. ChatRequest 빈 메시지 검증 테스트...")
        tester.test_chat_request_empty_message_validation()
        print("✅ 통과")

        print("\n2. ChatRequest 공백 메시지 검증 테스트...")
        tester.test_chat_request_whitespace_only_message_validation()
        print("✅ 통과")

        print("\n3. ChatRequest 정상 메시지 테스트...")
        tester.test_chat_request_valid_message()
        print("✅ 통과")

        print("\n4. General Agent 빈 쿼리 처리 테스트...")
        await tester.test_general_agent_empty_query_handling()
        print("✅ 통과")

        print("\n5. General Agent 공백 쿼리 처리 테스트...")
        await tester.test_general_agent_whitespace_query_handling()
        print("✅ 통과")

        print("\n6. Router Agent 빈 쿼리 처리 테스트...")
        await tester.test_router_agent_empty_query_handling()
        print("✅ 통과")

        print("\n7. Router Agent 공백 쿼리 처리 테스트...")
        await tester.test_router_agent_whitespace_query_handling()
        print("✅ 통과")

        print("\n✅ 모든 테스트 통과!")

    asyncio.run(main())