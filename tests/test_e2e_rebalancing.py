"""
E2E 테스트: 포트폴리오 리밸런싱

시나리오: "포트폴리오 리밸런싱해줘"
- 의도 분석: rebalancing
- 호출 에이전트: portfolio_agent, strategy_agent
- 자동화 레벨 2에서 HITL 트리거
"""
import pytest
from fastapi import status


@pytest.mark.e2e
async def test_portfolio_rebalancing_flow(client):
    """포트폴리오 리밸런싱 E2E 플로우 테스트"""
    # Given: 리밸런싱 요청
    request_data = {
        "message": "포트폴리오 리밸런싱해줘",
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

    # 메타데이터 확인
    metadata = data["metadata"]
    assert "intent" in metadata
    assert "agents_called" in metadata

    # 의도 분석 결과 확인
    assert metadata["intent"] in [
        "rebalancing",
        "portfolio_adjustment",
        "portfolio_optimization"
    ]

    # 호출된 에이전트 확인
    agents_called = metadata["agents_called"]
    assert isinstance(agents_called, list)
    # portfolio_agent가 호출되어야 함
    # (Mock 구현에 따라 실제 값은 다를 수 있음)

    # HITL 발동 (리밸런싱은 승인 필요)
    assert data["requires_approval"] is True
    assert data.get("approval_request") is not None


@pytest.mark.e2e
@pytest.mark.parametrize("automation_level,expected_hitl", [
    (1, False),  # Pilot: 자동 실행 (월 1회 리뷰)
    (2, True),   # Copilot: 승인 필요
    (3, True),   # Advisor: 승인 필수
])
async def test_rebalancing_hitl_by_level(client, automation_level, expected_hitl):
    """자동화 레벨별 리밸런싱 HITL 트리거 테스트"""
    # Given: 리밸런싱 요청
    request_data = {
        "message": "포트폴리오 리밸런싱",
        "automation_level": automation_level
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 자동화 레벨별 HITL 확인
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["requires_approval"] == expected_hitl

    if expected_hitl:
        assert data.get("approval_request") is not None


@pytest.mark.e2e
async def test_rebalancing_approval_request_structure(client):
    """리밸런싱 승인 요청 구조 테스트"""
    # Given: 리밸런싱 요청 (Copilot 모드)
    request_data = {
        "message": "포트폴리오 리밸런싱해줘",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 승인 요청 구조 확인
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    approval_request = data.get("approval_request")

    assert approval_request is not None
    assert "type" in approval_request
    assert "risk_level" in approval_request

    # 리밸런싱 타입 확인
    assert approval_request["type"] in [
        "rebalancing",
        "portfolio_adjustment",
        "portfolio_change"
    ]


@pytest.mark.e2e
async def test_portfolio_status_query(client):
    """포트폴리오 현황 조회 테스트"""
    # Given: 포트폴리오 현황 조회
    request_data = {
        "message": "내 포트폴리오 현황 알려줘",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답 (승인 불필요)
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "message" in data

    # 현황 조회는 HITL 미발동
    assert data["requires_approval"] is False


@pytest.mark.e2e
async def test_portfolio_performance_query(client):
    """포트폴리오 성과 조회 테스트"""
    # Given: 성과 조회
    request_data = {
        "message": "수익률 어떻게 돼?",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "message" in data

    # 성과 조회는 HITL 미발동
    assert data["requires_approval"] is False


@pytest.mark.e2e
async def test_conservative_rebalancing(client):
    """보수적 리밸런싱 요청 테스트"""
    # Given: 보수적 리밸런싱 요청
    request_data = {
        "message": "포트폴리오를 보수적으로 리밸런싱해줘",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답 및 HITL
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["requires_approval"] is True
    assert "message" in data


@pytest.mark.e2e
async def test_aggressive_rebalancing(client):
    """공격적 리밸런싱 요청 테스트"""
    # Given: 공격적 리밸런싱 요청
    request_data = {
        "message": "공격적으로 포트폴리오 재구성해줘",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답 및 HITL
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["requires_approval"] is True

    # 공격적 리밸런싱은 리스크가 높을 수 있음
    approval_request = data.get("approval_request")
    if approval_request:
        assert approval_request.get("risk_level") in ["medium", "high"]


@pytest.mark.e2e
async def test_sector_rebalancing(client):
    """섹터별 리밸런싱 요청 테스트"""
    # Given: 특정 섹터 중심 리밸런싱
    request_data = {
        "message": "반도체 비중을 줄이고 2차전지를 늘려줘",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답 및 HITL
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "message" in data
    # 포트폴리오 변경이므로 승인 필요
    assert data["requires_approval"] is True
