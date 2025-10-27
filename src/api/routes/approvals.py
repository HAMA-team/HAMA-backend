"""
Approval History 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
import logging

from src.models.database import get_db
from src.schemas.approval import (
    ApprovalHistoryItem,
    ApprovalHistoryListResponse,
    ApprovalDetailResponse
)
from src.services import approval_service
from src.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Demo 사용자 UUID
DEMO_USER_UUID = settings.demo_user_uuid


@router.get("/", response_model=ApprovalHistoryListResponse)
async def list_approval_history(
    status: Optional[str] = Query(None, description="필터링할 상태 (pending, approved, rejected, modified)"),
    request_type: Optional[str] = Query(None, description="필터링할 요청 타입 (trade, rebalance, strategy 등)"),
    limit: int = Query(20, ge=1, le=100, description="페이지 크기"),
    offset: int = Query(0, ge=0, description="오프셋"),
    db: Session = Depends(get_db)
):
    """
    승인 이력 목록 조회

    **Query Parameters:**
    - `status` (선택): 상태별 필터링
      - `pending`: 대기 중
      - `approved`: 승인됨
      - `rejected`: 거부됨
      - `modified`: 수정 후 승인
    - `request_type` (선택): 요청 타입별 필터링 (예: `trade`, `rebalance`)
    - `limit`: 페이지 크기 (기본값: 20, 최대: 100)
    - `offset`: 오프셋 (기본값: 0)

    **Response:**
    ```json
    {
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
    ```

    **사용 예:**
    - 모든 이력: `GET /approvals`
    - 대기 중만: `GET /approvals?status=pending`
    - 승인됨만: `GET /approvals?status=approved`
    - 매매 요청만: `GET /approvals?request_type=trade`
    - 2페이지: `GET /approvals?limit=20&offset=20`
    """
    try:
        items, total = approval_service.list_approval_history(
            db=db,
            user_id=DEMO_USER_UUID,
            status=status,
            request_type=request_type,
            limit=limit,
            offset=offset
        )

        # ApprovalHistoryItem으로 변환
        history_items = [ApprovalHistoryItem(**item) for item in items]

        return ApprovalHistoryListResponse(
            items=history_items,
            total=total,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Failed to list approval history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list approval history: {str(e)}"
        )


@router.get("/{request_id}", response_model=ApprovalDetailResponse)
async def get_approval_detail(
    request_id: UUID,
    db: Session = Depends(get_db)
):
    """
    승인 상세 정보 조회

    **Path Parameters:**
    - `request_id`: 승인 요청 UUID

    **Response:**
    ```json
    {
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
        "alternatives": {...},
        "created_at": "2025-10-26T10:00:00Z",
        "responded_at": "2025-10-26T10:05:00Z",
        "expires_at": "2025-10-26T12:00:00Z",
        "decision": "approved",
        "decided_at": "2025-10-26T10:05:00Z",
        "selected_option": "original",
        "modifications": null,
        "user_notes": "분석 결과가 합리적임"
    }
    ```

    **에러:**
    - `404`: 승인 요청이 존재하지 않음
    """
    detail = approval_service.get_approval_detail(
        db=db,
        request_id=request_id,
        user_id=DEMO_USER_UUID
    )

    if not detail:
        raise HTTPException(
            status_code=404,
            detail=f"Approval request not found: {request_id}"
        )

    return ApprovalDetailResponse(**detail)
