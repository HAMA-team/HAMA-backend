"""
통합 테스트: LangGraph 플로우 및 에러 핸들링

검증 항목:
- LangGraph StateGraph 플로우
- 에이전트 간 상태 전달
- 에러 핸들링
"""
import pytest
from fastapi import status


@pytest.mark.integration
async def test_langgraph_flow_completion(client):
    """LangGraph 플로우 전체 실행 테스트"""
    # Given: Chat 요청
    request_data = {
        "message": "삼성전자 분석해줘",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공적으로 플로우 완료
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # 응답 데이터 존재 확인
    assert "message" in data
    assert "metadata" in data
    assert "conversation_id" in data

    # 메타데이터에 플로우 정보 포함 확인
    metadata = data["metadata"]
    assert "intent" in metadata
    assert "agents_called" in metadata


@pytest.mark.integration
async def test_agent_state_passing(client):
    """에이전트 간 상태 전달 테스트"""
    # Given: 복잡한 요청 (여러 에이전트 호출 필요)
    request_data = {
        "message": "삼성전자 1000만원 매수 - 리스크 분석 포함",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # 여러 에이전트가 호출되었는지 확인
    metadata = data["metadata"]
    agents_called = metadata.get("agents_called", [])

    # 최소 1개 이상의 에이전트 호출
    assert len(agents_called) >= 1


@pytest.mark.integration
async def test_error_handling_invalid_request(client):
    """잘못된 요청 에러 핸들링 테스트"""
    # Given: 잘못된 요청 (필수 필드 누락)
    request_data = {
        # "message" 필드 누락
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 에러 응답
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.integration
async def test_error_handling_invalid_automation_level(client):
    """잘못된 자동화 레벨 에러 핸들링 테스트"""
    # Given: 잘못된 자동화 레벨
    request_data = {
        "message": "삼성전자 분석해줘",
        "automation_level": 5  # 유효하지 않은 레벨 (1-3만 유효)
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 에러 응답 또는 기본값으로 처리
    # (구현에 따라 422 또는 200 with 기본값)
    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_422_UNPROCESSABLE_ENTITY
    ]


@pytest.mark.integration
async def test_empty_message_handling(client):
    """빈 메시지 에러 핸들링 테스트"""
    # Given: 빈 메시지
    request_data = {
        "message": "",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 에러 응답 또는 기본 응답
    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        status.HTTP_400_BAD_REQUEST
    ]


@pytest.mark.integration
async def test_concurrent_requests(client):
    """동시 요청 처리 테스트"""
    # Given: 여러 개의 동시 요청
    requests = [
        {"message": "삼성전자 분석해줘", "automation_level": 2},
        {"message": "SK하이닉스는 어때?", "automation_level": 2},
        {"message": "NAVER 주가 알려줘", "automation_level": 2},
    ]

    # When: 순차적으로 요청 (동시성 테스트의 간소화 버전)
    responses = []
    for req in requests:
        response = client.post("/v1/chat/", json=req)
        responses.append(response)

    # Then: 모든 요청이 성공
    for response in responses:
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert "conversation_id" in data


@pytest.mark.integration
async def test_conversation_continuity(client):
    """대화 연속성 테스트"""
    # Given: 첫 번째 요청
    first_request = {
        "message": "삼성전자 분석해줘",
        "automation_level": 2
    }

    # When: 첫 번째 요청
    first_response = client.post("/v1/chat/", json=first_request)
    assert first_response.status_code == status.HTTP_200_OK

    first_data = first_response.json()
    conversation_id = first_data["conversation_id"]

    # Given: 같은 대화의 후속 요청
    second_request = {
        "message": "그럼 매수해도 될까?",
        "automation_level": 2,
        "conversation_id": conversation_id
    }

    # When: 두 번째 요청
    second_response = client.post("/v1/chat/", json=second_request)

    # Then: 성공 응답 및 같은 conversation_id 유지
    assert second_response.status_code == status.HTTP_200_OK

    second_data = second_response.json()
    assert second_data["conversation_id"] == conversation_id


@pytest.mark.integration
async def test_metadata_completeness(client):
    """메타데이터 완전성 테스트"""
    # Given: Chat 요청
    request_data = {
        "message": "삼성전자 1000만원 매수",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 메타데이터 완전성 확인
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    metadata = data["metadata"]

    # 필수 메타데이터 필드 확인
    required_fields = ["intent", "agents_called"]
    for field in required_fields:
        assert field in metadata, f"Missing metadata field: {field}"

    # agents_called가 리스트인지 확인
    assert isinstance(metadata["agents_called"], list)


@pytest.mark.integration
@pytest.mark.slow
async def test_large_context_handling(client):
    """큰 컨텍스트 처리 테스트"""
    # Given: 긴 메시지
    long_message = "삼성전자에 대해 " + "상세히 " * 100 + "분석해줘"

    request_data = {
        "message": long_message,
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답 (또는 적절한 에러 처리)
    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    ]


@pytest.mark.integration
async def test_special_characters_handling(client):
    """특수 문자 처리 테스트"""
    # Given: 특수 문자 포함 요청
    request_data = {
        "message": "삼성전자 <script>alert('test')</script> 분석해줘",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답 (XSS 방어 확인)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    # 응답에 스크립트 태그가 그대로 포함되지 않음
    assert "<script>" not in data["message"]
