"""
HITL(휴먼 인 더 루프) 인터럽트 처리를 공통화한 헬퍼.

/chat, /multi_agent_stream 모두 같은 로직으로 ApprovalRequest를 생성하고
DB에 저장하며, 채팅 히스토리에도 동일하게 기록한다.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.schemas.hitl import ApprovalRequest as HITLApprovalRequest
from src.schemas.hitl_config import HITLConfig, config_to_level
from src.services import chat_history_service, portfolio_service
from src.services.portfolio_preview_service import (
    calculate_portfolio_preview,
    calculate_weight_change,
)
from src.models.agent import ApprovalRequest as ApprovalRequestModel
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _save_approval_request_to_db(
    *,
    db: Session,
    user_id: uuid.UUID,
    request_type: str,
    approval_data: dict,
    hitl_config: HITLConfig,
) -> Optional[uuid.UUID]:
    """
    ApprovalRequest를 DB에 저장하고 request_id를 반환한다.
    """
    try:
        if request_type == "trade_approval":
            stock_name = approval_data.get("stock_name", approval_data.get("stock_code", ""))
            action = approval_data.get("action", "거래")
            request_title = f"{stock_name} {action} 승인 요청"
        elif request_type == "rebalance_approval":
            request_title = "포트폴리오 리밸런싱 승인 요청"
        else:
            request_title = "승인 요청"

        proposed_actions = approval_data.copy()
        risk_warnings = []
        if approval_data.get("risk_warning"):
            risk_warnings.append(approval_data["risk_warning"])

        approval_request = ApprovalRequestModel(
            user_id=user_id,
            request_type=request_type,
            request_title=request_title,
            request_description=approval_data.get("message"),
            proposed_actions=proposed_actions,
            risk_warnings=risk_warnings or None,
            alternatives=approval_data.get("alternatives"),
            status="pending",
            triggering_agent=approval_data.get("type", request_type).split("_")[0],
            automation_level=config_to_level(hitl_config),
            urgency="normal",
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )

        db.add(approval_request)
        db.commit()
        db.refresh(approval_request)

        logger.info("✅ ApprovalRequest 저장 완료: %s", approval_request.request_id)
        return approval_request.request_id

    except Exception as exc:
        logger.exception("❌ ApprovalRequest 저장 실패: %s", exc)
        db.rollback()
        return None


async def handle_hitl_interrupt(
    *,
    state: Any,
    conversation_uuid: uuid.UUID,
    conversation_id: str,
    user_id: uuid.UUID,
    db: Session,
    automation_level: int,
    hitl_config: HITLConfig,
) -> Optional[Dict[str, Any]]:
    """
    LangGraph Interrupt 발생 시 ApprovalRequest 생성·저장·히스토리 기록을 공통 처리한다.
    """
    pending_nodes = getattr(state, "next", None)
    if not pending_nodes:
        return None

    tasks = getattr(state, "tasks", [])
    interrupt_info = None
    if tasks:
        first_task = tasks[0]
        interrupts = getattr(first_task, "interrupts", None)
        if interrupts:
            interrupt_info = interrupts[0]

    interrupt_data = interrupt_info.value if interrupt_info else {}
    interrupt_type = interrupt_data.get("type") or interrupt_data.get("intent") or "trade_approval"

    approval_request: Dict[str, Any] = {
        "type": interrupt_type,
        "thread_id": conversation_id,
        "pending_node": pending_nodes[0] if pending_nodes else None,
        "message": interrupt_data.get("message", "사용자 승인이 필요합니다."),
    }

    if interrupt_type == "trade_approval" or interrupt_data.get("action") in {"buy", "sell"}:
        try:
            snapshot = await portfolio_service.get_portfolio_snapshot()
            portfolio_data = snapshot.portfolio_data if snapshot else {}
            holdings = portfolio_data.get("holdings", []) if portfolio_data else []
            total_value = float(portfolio_data.get("total_value", 0) or 0)
            cash = float(portfolio_data.get("cash_balance", 0) or 0)

            current_weight, expected_weight = await calculate_weight_change(
                current_holdings=holdings,
                new_order=interrupt_data,
                total_value=total_value,
                cash=cash,
            )

            portfolio_preview = await calculate_portfolio_preview(
                current_holdings=holdings,
                new_order=interrupt_data,
                total_value=total_value,
                cash=cash,
            )

            risk_warning = None
            if expected_weight > 0.4:
                risk_warning = f"⚠️ 단일 종목 {expected_weight*100:.1f}% 집중 - 분산 투자를 권장합니다"

            approval_request = HITLApprovalRequest(
                action=interrupt_data.get("action", "buy"),
                stock_code=interrupt_data.get("stock_code", ""),
                stock_name=interrupt_data.get("stock_name", ""),
                quantity=interrupt_data.get("quantity", 0),
                price=interrupt_data.get("price", 0),
                total_amount=interrupt_data.get("total_amount", 0),
                current_weight=current_weight,
                expected_weight=expected_weight,
                risk_warning=risk_warning,
                alternatives=None,
                expected_portfolio_preview=portfolio_preview.dict() if portfolio_preview else None,
            ).model_dump()

            approval_request["type"] = "trade_approval"
            approval_request["message"] = interrupt_data.get("message", "매매 주문을 승인하시겠습니까?")
            approval_request["pending_node"] = pending_nodes[0] if pending_nodes else None

        except Exception as exc:  # pragma: no cover - 포트폴리오 계산 실패 시 로깅 후 진행
            logger.warning("⚠️ 매매 승인 데이터 계산 실패: %s", exc)

    elif interrupt_type == "rebalance_approval":
        approval_request.update(
            {
                "order_id": interrupt_data.get("order_id"),
                "rebalancing_needed": interrupt_data.get("rebalancing_needed", False),
                "trades_required": interrupt_data.get("trades_required", []),
                "proposed_allocation": interrupt_data.get("proposed_allocation", []),
                "expected_return": interrupt_data.get("expected_return"),
                "expected_volatility": interrupt_data.get("expected_volatility"),
                "sharpe_ratio": interrupt_data.get("sharpe_ratio"),
                "constraint_violations": interrupt_data.get("constraint_violations", []),
                "market_condition": interrupt_data.get("market_condition", "중립장"),
            }
        )

    request_id = _save_approval_request_to_db(
        db=db,
        user_id=user_id,
        request_type=approval_request.get("type", interrupt_type),
        approval_data=approval_request,
        hitl_config=hitl_config,
    )
    if request_id:
        approval_request["request_id"] = str(request_id)

    message_text = "🔔 사용자 승인이 필요합니다."

    await chat_history_service.append_message(
        conversation_id=conversation_uuid,
        role="assistant",
        content=message_text,
        metadata={"requires_approval": True, "approval_request": approval_request},
    )
    await chat_history_service.upsert_session(
        conversation_id=conversation_uuid,
        user_id=user_id,
        metadata={"interrupted": True},
    )

    return {
        "message": message_text,
        "approval_request": approval_request,
        "interrupt_type": approval_request.get("type", interrupt_type),
    }
