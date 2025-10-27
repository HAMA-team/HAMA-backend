"""
Approval History 관련 비즈니스 로직
"""
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from src.models.agent import ApprovalRequest, UserDecision


def list_approval_history(
    db: Session,
    user_id: UUID,
    status: Optional[str] = None,
    request_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> Tuple[List[dict], int]:
    """
    승인 이력 목록 조회

    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        status: 필터링할 상태 (pending, approved, rejected, modified)
        request_type: 필터링할 요청 타입 (trade, rebalance, strategy 등)
        limit: 페이지 크기
        offset: 오프셋

    Returns:
        (이력 목록, 전체 개수)
    """
    # ApprovalRequest와 UserDecision 조인 쿼리
    query = db.query(
        ApprovalRequest,
        UserDecision
    ).outerjoin(
        UserDecision,
        ApprovalRequest.request_id == UserDecision.request_id
    ).filter(
        ApprovalRequest.user_id == user_id
    )

    # 상태 필터
    if status:
        if status in ["approved", "rejected", "modified"]:
            # 결정된 상태
            query = query.filter(UserDecision.decision == status)
        elif status == "pending":
            # 아직 결정되지 않음
            query = query.filter(UserDecision.decision_id.is_(None))

    # 요청 타입 필터
    if request_type:
        query = query.filter(ApprovalRequest.request_type == request_type)

    # 전체 개수
    total = query.count()

    # 최신순 정렬 및 페이징
    results = query.order_by(
        desc(ApprovalRequest.created_at)
    ).limit(limit).offset(offset).all()

    # 응답 데이터 구성
    history_items = []
    for approval_request, user_decision in results:
        # proposed_actions에서 요약 정보 추출
        proposed = approval_request.proposed_actions or {}

        item = {
            "request_id": approval_request.request_id,
            "request_type": approval_request.request_type,
            "request_title": approval_request.request_title,
            "status": user_decision.decision if user_decision else "pending",
            "decision": user_decision.decision if user_decision else None,
            "created_at": approval_request.created_at,
            "decided_at": user_decision.decided_at if user_decision else None,
            # 요약 정보
            "stock_code": proposed.get("stock_code"),
            "action": proposed.get("action"),
            "amount": proposed.get("total_amount"),
        }
        history_items.append(item)

    return history_items, total


def get_approval_detail(
    db: Session,
    request_id: UUID,
    user_id: UUID
) -> Optional[dict]:
    """
    승인 상세 정보 조회

    Args:
        db: 데이터베이스 세션
        request_id: 승인 요청 ID
        user_id: 사용자 ID

    Returns:
        상세 정보 딕셔너리 또는 None
    """
    # ApprovalRequest 조회
    approval_request = db.query(ApprovalRequest).filter(
        ApprovalRequest.request_id == request_id,
        ApprovalRequest.user_id == user_id
    ).first()

    if not approval_request:
        return None

    # 관련 UserDecision 조회
    user_decision = db.query(UserDecision).filter(
        UserDecision.request_id == request_id
    ).first()

    # 응답 데이터 구성
    detail = {
        # 기본 정보
        "request_id": approval_request.request_id,
        "user_id": approval_request.user_id,
        "request_type": approval_request.request_type,
        "request_title": approval_request.request_title,
        "request_description": approval_request.request_description,
        "status": user_decision.decision if user_decision else "pending",

        # 제안 내용
        "proposed_actions": approval_request.proposed_actions or {},

        # 영향 분석
        "impact_analysis": approval_request.impact_analysis,

        # 리스크 경고
        "risk_warnings": approval_request.risk_warnings or [],

        # 대안 제시
        "alternatives": approval_request.alternatives,

        # 타임스탬프
        "created_at": approval_request.created_at,
        "responded_at": approval_request.responded_at,
        "expires_at": approval_request.expires_at,
    }

    # 결정 정보 추가 (있을 경우)
    if user_decision:
        detail.update({
            "decision": user_decision.decision,
            "decided_at": user_decision.decided_at,
            "selected_option": user_decision.selected_option,
            "modifications": user_decision.modifications,
            "user_notes": user_decision.user_notes,
        })
    else:
        detail.update({
            "decision": None,
            "decided_at": None,
            "selected_option": None,
            "modifications": None,
            "user_notes": None,
        })

    return detail
