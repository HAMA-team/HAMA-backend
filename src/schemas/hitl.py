"""
HITL (Human-in-the-Loop) 승인 관련 스키마

Frontend PRD v3.0 요구사항에 맞는 데이터 구조 정의
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal, List

# TODO 이거 왜 mock 데이터 위주로 들어가있지? 이거 수정 필요함.
class Alternative(BaseModel):
    """HITL 대안 제시"""
    suggestion: str = Field(..., description="대안 설명")
    adjusted_quantity: int = Field(..., description="조정된 수량")
    adjusted_amount: int = Field(..., description="조정된 금액 (원)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "suggestion": "매수 금액을 500만원으로 조정 (비중 34%)",
                "adjusted_quantity": 65,
                "adjusted_amount": 5000000
            }
        }
    )


class PortfolioPreview(BaseModel):
    """예상 포트폴리오 미리보기 (원 그래프용)"""
    stock_name: str = Field(..., description="종목명 또는 '현금'")
    weight: float = Field(..., description="비중 (0~1)", ge=0, le=1)
    color: str = Field(..., description="Hex color code (예: #3B82F6)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stock_name": "삼성전자",
                "weight": 0.43,
                "color": "#EF4444"
            }
        }
    )


class ExpectedPortfolioPreview(BaseModel):
    """예상 포트폴리오 before/after 비교"""
    current: List[PortfolioPreview] = Field(
        ...,
        description="현재 포트폴리오 구성"
    )
    after_approval: List[PortfolioPreview] = Field(
        ...,
        description="승인 후 예상 포트폴리오 구성"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current": [
                    {"stock_name": "삼성전자", "weight": 0.25, "color": "#3B82F6"},
                    {"stock_name": "SK하이닉스", "weight": 0.15, "color": "#10B981"},
                    {"stock_name": "현금", "weight": 0.60, "color": "#6B7280"}
                ],
                "after_approval": [
                    {"stock_name": "삼성전자", "weight": 0.43, "color": "#EF4444"},
                    {"stock_name": "SK하이닉스", "weight": 0.10, "color": "#10B981"},
                    {"stock_name": "현금", "weight": 0.47, "color": "#6B7280"}
                ]
            }
        }
    )


class ApprovalRequest(BaseModel):
    """
    HITL 승인 요청 데이터

    Frontend ApprovalPanelProps와 일치하는 구조
    """
    action: Literal["buy", "sell"] = Field(..., description="매매 유형")
    stock_code: str = Field(..., description="종목 코드")
    stock_name: str = Field(..., description="종목명")
    quantity: int = Field(..., description="수량", gt=0)
    price: int = Field(..., description="가격 (원)", gt=0)
    total_amount: int = Field(..., description="총 금액 (원)", gt=0)

    # 리스크 정보
    current_weight: float = Field(
        ...,
        description="현재 포트폴리오 비중 (0~1)",
        ge=0,
        le=1
    )
    expected_weight: float = Field(
        ...,
        description="매수 후 예상 비중 (0~1)",
        ge=0,
        le=1
    )
    risk_warning: Optional[str] = Field(
        None,
        description="리스크 경고 메시지"
    )

    # 대안 제시
    alternatives: Optional[List[Alternative]] = Field(
        None,
        description="권장 대안 목록"
    )

    # 예상 포트폴리오 (Phase 1: Optional, Phase 2: Required)
    expected_portfolio_preview: Optional[ExpectedPortfolioPreview] = Field(
        None,
        description="예상 포트폴리오 미리보기 (원 그래프용)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action": "buy",
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "quantity": 131,
                "price": 76300,
                "total_amount": 10000000,
                "current_weight": 0.25,
                "expected_weight": 0.43,
                "risk_warning": "⚠️ 단일 종목 40% 이상 시 평균 수익률 -6.8%",
                "alternatives": [
                    {
                        "suggestion": "매수 금액을 500만원으로 조정 (비중 34%)",
                        "adjusted_quantity": 65,
                        "adjusted_amount": 5000000
                    },
                    {
                        "suggestion": "같은 섹터 SK하이닉스로 분산",
                        "adjusted_quantity": 35,
                        "adjusted_amount": 5000000
                    }
                ],
                "expected_portfolio_preview": {
                    "current": [
                        {"stock_name": "삼성전자", "weight": 0.25, "color": "#3B82F6"},
                        {"stock_name": "SK하이닉스", "weight": 0.15, "color": "#10B981"},
                        {"stock_name": "현금", "weight": 0.60, "color": "#6B7280"}
                    ],
                    "after_approval": [
                        {"stock_name": "삼성전자", "weight": 0.43, "color": "#EF4444"},
                        {"stock_name": "SK하이닉스", "weight": 0.10, "color": "#10B981"},
                        {"stock_name": "현금", "weight": 0.47, "color": "#6B7280"}
                    ]
                }
            }
        }
    )


class ThinkingStep(BaseModel):
    """AI 사고 과정 단계"""
    agent: str = Field(..., description="에이전트 이름 (예: research, strategy, risk)")
    description: str = Field(..., description="단계 설명")
    timestamp: str = Field(..., description="타임스탬프 (ISO 8601)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "agent": "research",
                "description": "데이터 수집 중...",
                "timestamp": "2025-10-26T10:00:00Z"
            }
        }
    )


class ChatResponse(BaseModel):
    """
    Chat API 응답

    Frontend 요구사항:
    - requires_approval: HITL 필요 여부
    - approval_request: 승인 요청 데이터 (ApprovalRequest 구조)
    - thinking: AI 사고 과정 (접기/펼치기용)
    """
    message: str = Field(..., description="AI 답변 (Markdown)")
    conversation_id: str = Field(..., description="대화 ID (UUID)")

    # Thinking Trace (US-1.2)
    thinking: Optional[List[ThinkingStep]] = Field(
        None,
        description="AI 사고 과정 단계별 내역"
    )

    # HITL (US-2.1)
    requires_approval: bool = Field(
        False,
        description="승인 필요 여부"
    )
    approval_request: Optional[ApprovalRequest] = Field(
        None,
        description="승인 요청 데이터 (requires_approval=True일 때)"
    )

    # 메타데이터
    timestamp: str = Field(..., description="응답 시각 (ISO 8601)")
    metadata: Optional[dict] = Field(None, description="추가 메타데이터")

    model_config = ConfigDict(
        json_schema_extra={
            "example_normal": {
                "message": "## 삼성전자 분석 결과\n\n...",
                "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                "thinking": [
                    {
                        "agent": "research",
                        "description": "데이터 수집 중...",
                        "timestamp": "2025-10-26T10:00:00Z"
                    },
                    {
                        "agent": "strategy",
                        "description": "전략 분석 중...",
                        "timestamp": "2025-10-26T10:00:05Z"
                    }
                ],
                "requires_approval": False,
                "timestamp": "2025-10-26T10:00:10Z",
                "metadata": {
                    "intent": "stock_analysis",
                    "agents_called": ["research", "strategy"]
                }
            },
            "example_hitl": {
                "message": "삼성전자 1000만원 매수를 제안합니다",
                "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                "requires_approval": True,
                "approval_request": {
                    "action": "buy",
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 131,
                    "price": 76300,
                    "total_amount": 10000000,
                    "current_weight": 0.25,
                    "expected_weight": 0.43,
                    "risk_warning": "⚠️ 단일 종목 40% 이상 시 평균 수익률 -6.8%",
                    "alternatives": [
                        {
                            "suggestion": "매수 금액을 500만원으로 조정",
                            "adjusted_quantity": 65,
                            "adjusted_amount": 5000000
                        }
                    ]
                },
                "timestamp": "2025-10-26T10:00:10Z"
            }
        }
    )


class ApprovalDecision(BaseModel):
    """승인 결정"""
    thread_id: str = Field(..., description="대화 스레드 ID")
    decision: Literal["approved", "rejected", "modified"] = Field(
        ...,
        description="승인 결정"
    )
    modifications: Optional[dict] = Field(
        None,
        description="수정 내용 (decision=modified일 때)"
    )
    user_notes: Optional[str] = Field(
        None,
        description="사용자 메모"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "thread_id": "550e8400-e29b-41d4-a716-446655440000",
                "decision": "approved"
            }
        }
    )


class ApprovalResponse(BaseModel):
    """승인 처리 응답"""
    status: str = Field(..., description="처리 상태")
    message: str = Field(..., description="처리 결과 메시지")
    conversation_id: str = Field(..., description="대화 ID")
    result: Optional[dict] = Field(None, description="실행 결과 상세")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "approved",
                "message": "✅ 승인 완료 - 매수 주문이 실행되었습니다",
                "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
                "result": {
                    "order_id": "ORD-20251026-001",
                    "status": "filled",
                    "price": 76300,
                    "quantity": 131
                }
            }
        }
    )
