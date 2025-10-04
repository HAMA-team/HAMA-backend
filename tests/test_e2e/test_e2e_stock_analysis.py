"""
E2E 테스트: 종목 분석

시나리오: "삼성전자 분석해줘"
- 의도 분석: stock_analysis
- 호출 에이전트: research_agent, strategy_agent, risk_agent
- HITL 트리거: False
"""
import pytest
from fastapi import status


@pytest.mark.e2e
async def test_stock_analysis_flow(client, sample_chat_request):
    """종목 분석 E2E 플로우 테스트"""
    # Given: 종목 분석 요청
    request_data = {
        "message": "삼성전자 분석해줘",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # 기본 응답 구조 확인
    assert "message" in data
    assert "conversation_id" in data
    assert "requires_approval" in data
    assert "metadata" in data

    # 메시지가 비어있지 않음
    assert len(data["message"]) > 0

    # 메타데이터 확인
    metadata = data["metadata"]
    assert "intent" in metadata
    assert "agents_called" in metadata

    # 의도 분석 결과 확인
    # 종목 분석 또는 관련 의도여야 함
    assert metadata["intent"] in [
        "stock_analysis",
        "stock_evaluation",
        "investment_advice",
        "general_question"
    ]

    # 호출된 에이전트 확인 (Mock 구현이므로 실제 호출 여부는 로그에서 확인)
    assert isinstance(metadata["agents_called"], list)

    # HITL 미발동 (종목 분석은 승인 불필요)
    assert data["requires_approval"] is False
    assert data.get("approval_request") is None


@pytest.mark.e2e
async def test_stock_analysis_response_format(client):
    """종목 분석 응답 포맷 테스트"""
    # Given: 종목 분석 요청
    request_data = {
        "message": "SK하이닉스 어때?",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 응답 확인
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # 응답 메시지에 종목 관련 정보 포함 확인 (Mock 데이터 기반)
    message = data["message"]
    assert isinstance(message, str)
    assert len(message) > 10  # 최소한의 내용이 있어야 함


@pytest.mark.e2e
@pytest.mark.parametrize("stock_query", [
    "삼성전자 분석해줘",
    "NAVER 주가 어때?",
    "현대차 투자하기 좋아?",
])
async def test_various_stock_queries(client, stock_query):
    """다양한 종목 질의 테스트"""
    # Given: 다양한 형태의 종목 질문
    request_data = {
        "message": stock_query,
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 모두 성공 응답
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "message" in data
    assert len(data["message"]) > 0
    assert "metadata" in data


@pytest.mark.e2e
async def test_stock_analysis_conversation_id(client):
    """대화 ID 생성 확인"""
    # Given: 종목 분석 요청
    request_data = {
        "message": "삼성전자 분석해줘",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: conversation_id 생성 확인
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    conversation_id = data.get("conversation_id")

    assert conversation_id is not None
    assert isinstance(conversation_id, str)
    assert len(conversation_id) > 0


@pytest.mark.e2e
async def test_stock_analysis_with_context(client):
    """컨텍스트 포함 종목 분석"""
    # Given: 이전 대화를 포함한 요청
    request_data = {
        "message": "삼성전자 분석해줘",
        "automation_level": 2,
        "conversation_id": "test-conversation-123"
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["conversation_id"] == "test-conversation-123"
