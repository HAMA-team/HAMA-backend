"""
Approval History 관련 Pydantic 스키마
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


class ApprovalHistoryItem(BaseModel):
    """승인 이력 목록 아이템"""
    request_id: UUID
    request_type: str
    request_title: str
    status: str  # pending, approved, rejected, modified
    decision: Optional[str] = None  # approved, rejected, modified
    created_at: datetime
    decided_at: Optional[datetime] = None

    # 요약 정보
    stock_code: Optional[str] = None
    action: Optional[str] = None  # buy, sell
    amount: Optional[int] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "request_type": "trade",
                "request_title": "삼성전자 매수 승인 요청",
                "status": "approved",
                "decision": "approved",
                "created_at": "2025-10-26T10:00:00Z",
                "decided_at": "2025-10-26T10:05:00Z",
                "stock_code": "005930",
                "action": "buy",
                "amount": 10000000
            }
        }


class ApprovalHistoryListResponse(BaseModel):
    """승인 이력 목록 응답"""
    items: List[ApprovalHistoryItem]
    total: int
    limit: int
    offset: int

    class Config:
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "request_id": "550e8400-e29b-41d4-a716-446655440000",
                        "request_type": "trade",
                        "request_title": "삼성전자 매수 승인 요청",
                        "status": "approved",
                        "decision": "approved",
                        "created_at": "2025-10-26T10:00:00Z",
                        "decided_at": "2025-10-26T10:05:00Z",
                        "stock_code": "005930",
                        "action": "buy",
                        "amount": 10000000
                    }
                ],
                "total": 42,
                "limit": 20,
                "offset": 0
            }
        }


class ApprovalDetailResponse(BaseModel):
    """승인 상세 정보 응답"""
    # 기본 정보
    request_id: UUID
    user_id: UUID
    request_type: str
    request_title: str
    request_description: Optional[str]
    status: str

    # 제안 내용
    proposed_actions: Dict[str, Any]

    # 영향 분석
    impact_analysis: Optional[Dict[str, Any]]

    # 리스크 경고
    risk_warnings: Optional[List[str]]

    # 대안 제시
    alternatives: Optional[Dict[str, Any]]

    # 타임스탬프
    created_at: datetime
    responded_at: Optional[datetime]
    expires_at: Optional[datetime]

    # 결정 정보 (있을 경우)
    decision: Optional[str] = None
    decided_at: Optional[datetime] = None
    selected_option: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None
    user_notes: Optional[str] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "660e8400-e29b-41d4-a716-446655440001",
                "request_type": "trade",
                "request_title": "삼성전자 매수 승인 요청",
                "request_description": "AI가 분석한 매수 기회입니다.",
                "status": "approved",
                "proposed_actions": {
                    "action": "buy",
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 131,
                    "price": 76300,
                    "total_amount": 10000000
                },
                "impact_analysis": {
                    "current_weight": 0.25,
                    "expected_weight": 0.43,
                    "expected_return": 0.12
                },
                "risk_warnings": ["단일 종목 집중도가 40%를 초과합니다"],
                "alternatives": {
                    "option1": {"description": "수량을 50% 줄여서 매수"},
                    "option2": {"description": "다른 종목으로 분산"}
                },
                "created_at": "2025-10-26T10:00:00Z",
                "responded_at": "2025-10-26T10:05:00Z",
                "expires_at": "2025-10-26T12:00:00Z",
                "decision": "approved",
                "decided_at": "2025-10-26T10:05:00Z",
                "selected_option": "original",
                "modifications": None,
                "user_notes": "분석 결과가 합리적임"
            }
        }
