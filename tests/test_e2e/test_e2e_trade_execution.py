"""
E2E 테스트: 매매 실행 (HITL)

시나리오: "삼성전자 1000만원 매수"
- 의도 분석: trade_execution
- HITL 트리거: 자동화 레벨별로 다름
- approval_request 구조 확인
"""
import pytest
from fastapi import status


@pytest.mark.e2e
@pytest.mark.parametrize("automation_level,expected_hitl", [
    (1, False),  # Pilot: HITL 미발동 (자동 실행)
    (2, True),   # Copilot: HITL 발동 (승인 필요)
    (3, True),   # Advisor: HITL 발동 (승인 필수)
])
async def test_trade_execution_hitl_by_level(client, automation_level, expected_hitl):
    """자동화 레벨별 HITL 트리거 테스트"""
    # Given: 매매 실행 요청
    request_data = {
        "message": "삼성전자 1000만원 매수",
        "automation_level": automation_level
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # 기본 응답 구조 확인
    assert "message" in data
    assert "requires_approval" in data
    assert "metadata" in data

    # 의도 분석 결과 확인
    metadata = data["metadata"]
    assert "intent" in metadata

    # 매매 실행 의도여야 함
    assert metadata["intent"] in [
        "trade_execution",
        "buy_stock",
        "sell_stock",
        "order_placement"
    ]

    # 자동화 레벨별 HITL 트리거 확인
    assert data["requires_approval"] == expected_hitl

    # HITL 발동 시 approval_request 존재 확인
    if expected_hitl:
        assert data.get("approval_request") is not None
        approval_request = data["approval_request"]

        # approval_request 구조 검증
        assert "type" in approval_request
        assert "risk_level" in approval_request
        assert approval_request["type"] in [
            "trade_execution",
            "order_confirmation",
            "risk_warning"
        ]
    else:
        # HITL 미발동 시 approval_request 없음
        assert data.get("approval_request") is None


@pytest.mark.e2e
async def test_trade_execution_approval_request_structure(client):
    """매매 실행 승인 요청 구조 상세 테스트"""
    # Given: 매매 실행 요청 (Copilot 모드)
    request_data = {
        "message": "삼성전자 1000만원 매수해줘",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # HITL 트리거 확인
    assert data["requires_approval"] is True

    # approval_request 상세 구조 확인
    approval_request = data["approval_request"]
    assert approval_request is not None

    # 필수 필드 확인
    required_fields = ["type", "risk_level"]
    for field in required_fields:
        assert field in approval_request, f"Missing required field: {field}"

    # risk_level 값 검증
    assert approval_request["risk_level"] in ["low", "medium", "high"]


@pytest.mark.e2e
async def test_buy_order_request(client):
    """매수 주문 요청 테스트"""
    # Given: 매수 주문
    request_data = {
        "message": "SK하이닉스 500만원어치 사줘",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답 및 HITL 트리거
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["requires_approval"] is True
    assert "message" in data
    assert len(data["message"]) > 0


@pytest.mark.e2e
async def test_sell_order_request(client):
    """매도 주문 요청 테스트"""
    # Given: 매도 주문
    request_data = {
        "message": "NAVER 전량 매도",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답 및 HITL 트리거
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["requires_approval"] is True


@pytest.mark.e2e
async def test_high_risk_trade_warning(client):
    """고위험 거래 경고 테스트"""
    # Given: 고위험 거래 (큰 금액)
    request_data = {
        "message": "삼성전자 5억원 매수",
        "automation_level": 3
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답 및 HITL 트리거
    assert response.status_code == status.HTTP_200_OK

    data = response.json()

    # 고위험 거래는 반드시 승인 필요
    assert data["requires_approval"] is True

    approval_request = data.get("approval_request")
    if approval_request:
        # 리스크 레벨이 high일 가능성이 높음
        assert approval_request.get("risk_level") in ["medium", "high"]


@pytest.mark.e2e
async def test_multiple_stock_order(client):
    """복수 종목 주문 테스트"""
    # Given: 여러 종목 동시 주문
    request_data = {
        "message": "삼성전자 500만원, SK하이닉스 300만원 매수",
        "automation_level": 2
    }

    # When: Chat API 호출
    response = client.post("/v1/chat/", json=request_data)

    # Then: 성공 응답
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "message" in data
    # 복수 종목 주문도 HITL 트리거
    assert data["requires_approval"] is True
