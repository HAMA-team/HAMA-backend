"""
채팅 및 승인 관련 API 엔드포인트 모음
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any, Literal
import uuid
import os
import logging

logger = logging.getLogger(__name__)

from src.subgraphs.graph_master import build_graph
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from src.services import chat_history_service
from src.services.hitl_interrupt_service import handle_hitl_interrupt
from src.services.user_profile_service import UserProfileService
from src.schemas.hitl_config import HITLConfig
from src.config.settings import settings
from src.models.database import get_db
from fastapi import Depends
from sqlalchemy.orm import Session
from src.models.agent import ApprovalRequest as ApprovalRequestModel, UserDecision
from datetime import datetime, timedelta
from src.models.chat import ChatSession

router = APIRouter()

DEMO_USER_UUID = settings.demo_user_uuid


def _ensure_uuid(value: Optional[str]) -> uuid.UUID:
    """Validate or generate a conversation UUID."""
    if value:
        value_str = str(value).strip()
        if not value_str:
            return uuid.uuid4()
        try:
            return uuid.UUID(value_str)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="conversation_id must be a valid UUID",
            ) from exc
    return uuid.uuid4()


def _serialize_datetime(dt) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


class ChatMessage(BaseModel):
    """채팅 메시지 스키마"""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """채팅 요청 스키마"""

    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(..., min_length=1, description="사용자 메시지 (비어있으면 안 됨)")
    conversation_id: Optional[str] = Field(
        default=None,
        alias="conversation_id",
        validation_alias=AliasChoices("conversation_id", "conversationId"),
    )
    hitl_config: HITLConfig = Field(
        default_factory=HITLConfig,
        validation_alias=AliasChoices("hitl_config", "hitlConfig"),
        description="HITL 단계별 설정",
    )
    intervention_required: bool = Field(
        default=True,
        validation_alias=AliasChoices("intervention_required", "interventionRequired"),
        description="분석/전략 단계부터 HITL 필요 여부 (기본적으로 분석/전략도 승인 대기)",
    )

    @field_validator("message")
    @classmethod
    def validate_message_not_whitespace(cls, v: str) -> str:
        """메시지 검증: 공백만 있는 메시지 거부"""
        if not v.strip():
            raise ValueError("메시지는 공백만 포함할 수 없습니다")
        return v


class ChatResponse(BaseModel):
    """채팅 응답 스키마"""
    message: str
    conversation_id: str
    requires_approval: bool = False
    approval_request: Optional[dict] = None
    metadata: Optional[dict] = None


class ChatSessionSummary(BaseModel):
    """채팅 세션 요약 스키마"""
    conversation_id: str
    title: str
    last_message: Optional[str] = None
    last_message_at: Optional[str] = None
    hitl_config: HITLConfig = Field(default_factory=HITLConfig)
    message_count: int
    created_at: Optional[str] = None


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    메인 채팅 엔드포인트입니다.

    처리 흐름:
    1. 마스터 에이전트가 질의를 수신합니다.
    2. 적절한 서브 에이전트를 선택해 작업을 분배합니다.
    3. 서브 에이전트가 결과를 생성합니다.
    4. 마스터 에이전트가 결과를 통합합니다.
    5. HITL 조건을 확인하고 응답을 생성합니다.
    6. 중단 지점이 있는 경우 승인 요청을 반환합니다.
    """
    try:
        conversation_uuid = _ensure_uuid(request.conversation_id)
        conversation_id = str(conversation_uuid)

        hitl_config = request.hitl_config
        intervention_required = request.intervention_required

        # Get user profile for dynamic worker selection
        user_profile_service = UserProfileService()
        user_profile = user_profile_service.get_user_profile(DEMO_USER_UUID, db)
        logger.info("📋 [Chat] UserProfile 로드 완료: preferred_depth=%s, expertise_level=%s",
                    user_profile.get("preferred_depth"), user_profile.get("expertise_level"))

        # Ensure session exists and store the incintervention_requiredoming user message
        await chat_history_service.upsert_session(
            conversation_id=conversation_uuid,
            user_id=DEMO_USER_UUID,
            metadata={
                "intervention_required": intervention_required,
                "hitl_config": hitl_config.model_dump(),
            },
        )
        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="user",
            content=request.message,
        )

        # Build graph with intervention_required
        app = await build_graph(intervention_required=intervention_required)

        # Config for checkpointer
        config: RunnableConfig = {
            "configurable": {
                "thread_id": conversation_id,
            }
        }

        configured_app = app.with_config(config)

        # Initial state - Langgraph 표준: messages 사용
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "user_id": str(DEMO_USER_UUID),
            "conversation_id": conversation_id,
            "hitl_config": hitl_config.model_dump(),
            "intervention_required": intervention_required,
            "user_profile": user_profile,
            "intent": None,
            "query": request.message,
            "agent_results": {},
            "agents_to_call": [],
            "agents_called": [],
            "risk_level": None,
            "hitl_required": False,
            "trade_prepared": False,
            "trade_approved": False,
            "trade_executed": False,
            "trade_order_id": None,
            "trade_result": None,
            "summary": None,
            "final_response": None,
            "user_pending_approval": False,
            "user_decision": None,
        }

        # Run Langgraph
        result = await configured_app.ainvoke(initial_state)

        # Check for interrupt
        state = await configured_app.aget_state(config)

        if state.next:  # Interrupt 발생
            hitl_result = await handle_hitl_interrupt(
                state=state,
                conversation_uuid=conversation_uuid,
                conversation_id=conversation_id,
                user_id=DEMO_USER_UUID,
                db=db,
                intervention_required=intervention_required,
                hitl_config=hitl_config,
            )

            if hitl_result:
                return ChatResponse(
                    message=hitl_result["message"],
                    conversation_id=conversation_id,
                    requires_approval=True,
                    approval_request=hitl_result["approval_request"],
                    metadata={
                        "interrupted": True,
                        "intervention_required": intervention_required,
                    },
                )

        # No interrupt - 정상 완료
        data = result.get("final_response", {})

        # Langgraph 표준: messages에서 AI 응답 추출
        ai_messages = [msg for msg in result.get("messages", []) if isinstance(msg, AIMessage)]
        last_ai_message = ai_messages[-1] if ai_messages else None

        # Get summary and details (하위 호환성)
        summary = data.get("summary") or (last_ai_message.content if last_ai_message else "분석 완료")
        details = data.get("details", {})

        # Build detailed message
        message_parts = [f"📊 분석 결과\n\n{summary}\n"]

        if "research_agent" in details:
            research = details["research_agent"]
            message_parts.append(
                f"\n🔍 **리서치**\n"
                f"  - 종목: {research.get('stock_name', 'N/A')}\n"
                f"  - 평가: {research.get('rating', 'N/A')}/5\n"
                f"  - 추천: {research.get('recommendation', 'N/A')}"
            )

        # Quantitative Agent (전략 + 리스크 통합)
        if "quantitative_agent" in details:
            quant = details["quantitative_agent"]

            # 전략 정보 (strategy_synthesis 또는 buy_decision)
            if quant.get("strategy_synthesis") or quant.get("buy_analysis"):
                strategy = quant.get("strategy_synthesis", quant.get("buy_analysis", {}))
                message_parts.append(
                    f"\n📈 **정량 분석**\n"
                    f"  - 매수 점수: {strategy.get('buy_score', 'N/A')}/10\n"
                    f"  - 투자 의견: {strategy.get('action', 'N/A')}"
                )

            # 리스크 정보 (risk_reward)
            if quant.get("risk_reward"):
                risk = quant.get("risk_reward", {})
                message_parts.append(
                    f"\n⚠️ **리스크/목표가**\n"
                    f"  - 손절가: {risk.get('stop_loss_price', 'N/A'):,}원\n"
                    f"  - 목표가: {risk.get('target_price_1', 'N/A'):,}원"
                )

        # 하위 호환성 (deprecated - quantitative_agent로 통합됨)
        if "strategy_agent" in details:
            strategy = details["strategy_agent"]
            message_parts.append(
                f"\n📈 **전략** (deprecated)\n"
                f"  - 의견: {strategy.get('action', 'N/A')}\n"
                f"  - 신뢰도: {strategy.get('confidence', 'N/A')}"
            )

        if "risk_agent" in details:
            risk = details["risk_agent"]
            warnings = risk.get("warnings", [])
            warning_text = ", ".join(warnings) if warnings else "없음"
            message_parts.append(
                f"\n⚠️ **리스크** (deprecated)\n"
                f"  - 수준: {risk.get('risk_level', 'N/A')}\n"
                f"  - 경고: {warning_text}"
            )

        if data.get("trade_result"):
            trade = data["trade_result"]
            message_parts.append(
                f"\n💰 **매매 실행 완료**\n"
                f"  - 주문 번호: {trade.get('order_id', 'N/A')}\n"
                f"  - 상태: {trade.get('status', 'N/A')}\n"
                f"  - 체결가: {trade.get('price', 0):,}원\n"
                f"  - 수량: {trade.get('quantity', 0)}주\n"
                f"  - 총액: {trade.get('total', 0):,}원"
            )

        message = "\n".join(message_parts)

        # Build approval request if needed
        approval_request = None
        hitl_required = data.get("hitl_required", False)
        intent = data.get("intent")

        if hitl_required:
            approval_type_map = {
                "trade_execution": "trade_execution",
                "rebalancing": "rebalancing",
                "portfolio_adjustment": "portfolio_adjustment",
                "portfolio_evaluation": "portfolio_change",
            }

            approval_type = approval_type_map.get(intent, "approval_needed")

            approval_request = {
                "type": approval_type,
                "intent": intent,
                "risk_level": data.get("risk_level"),
                "message": "이 작업은 승인이 필요합니다.",
            }

        message_metadata = {
            "intent": intent,
            "agents_called": data.get("agents_called", []),
            "hitl_required": hitl_required,
            "intervention_required": intervention_required,
        }

        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="assistant",
            content=message,
            metadata=message_metadata,
        )
        await chat_history_service.upsert_session(
            conversation_id=conversation_uuid,
            user_id=DEMO_USER_UUID,
            metadata=message_metadata,
            summary=data.get("summary"),
            last_agent=(data.get("agents_called") or [None])[-1] if data.get("agents_called") else None,
        )

        return ChatResponse(
            message=message,
            conversation_id=conversation_id,
            requires_approval=hitl_required,
            approval_request=approval_request,
            metadata=message_metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


@router.get("/history/{conversation_id}")
async def get_chat_history(conversation_id: str, limit: int = Query(100, ge=1, le=500)):
    """특정 대화의 메시지 히스토리를 조회합니다."""
    conversation_uuid = _ensure_uuid(conversation_id)
    history = await chat_history_service.get_history(conversation_id=conversation_uuid, limit=limit)

    if not history:
        raise HTTPException(status_code=404, detail="Conversation not found")

    session = history["session"]
    messages = history["messages"]

    return {
        "conversation_id": str(session.conversation_id),
        "user_id": str(session.user_id),
        "summary": session.summary,
        "metadata": session.session_metadata,
        "created_at": _serialize_datetime(session.created_at),
        "updated_at": _serialize_datetime(session.updated_at),
        "last_message_at": _serialize_datetime(session.last_message_at),
        "messages": [
            {
                "message_id": str(message.message_id),
                "role": message.role,
                "content": message.content,
                "metadata": message.message_metadata,
                "agent_id": message.agent_id,
                "created_at": _serialize_datetime(message.created_at),
            }
            for message in messages
        ],
    }


@router.delete("/history/{conversation_id}")
async def delete_chat_history(conversation_id: str):
    """특정 대화 히스토리를 영구 삭제합니다."""
    conversation_uuid = _ensure_uuid(conversation_id)
    await chat_history_service.delete_history(conversation_id=conversation_uuid)
    return {"status": "deleted", "conversation_id": conversation_id}


@router.get("/sessions", response_model=List[ChatSessionSummary])
async def list_chat_sessions(limit: int = Query(50, ge=1, le=100)):
    """최근 활동 순으로 정렬된 채팅 세션 목록을 반환합니다."""
    summaries = await chat_history_service.list_sessions(user_id=DEMO_USER_UUID, limit=limit)

    response: List[ChatSessionSummary] = []
    for summary in summaries:
        session = summary["session"]
        first_user_message = summary.get("first_user_message")
        last_message = summary.get("last_message")
        message_count = summary.get("message_count") or 0

        raw_title = session.summary
        if not raw_title and first_user_message and first_user_message.content:
            raw_title = first_user_message.content.strip()
        if not raw_title:
            raw_title = "새 대화"

        title = raw_title[:50]
        last_message_text = None
        if last_message and last_message.content:
            last_message_text = last_message.content.strip()[:100]

        last_message_at = (
            last_message.created_at if last_message else session.last_message_at or session.updated_at
        )

        response.append(
            ChatSessionSummary(
                conversation_id=str(session.conversation_id),
                title=title,
                last_message=last_message_text,
                last_message_at=_serialize_datetime(last_message_at),
                message_count=message_count,
                created_at=_serialize_datetime(session.created_at),
            )
        )

    return response


# ==================== Approval Endpoint ====================

def _save_user_decision_to_db(
    db: Session,
    request_id: uuid.UUID,
    user_id: uuid.UUID,
    decision: str,
    modifications: Optional[dict] = None,
    user_notes: Optional[str] = None
) -> bool:
    """
    사용자 결정을 DB에 저장하고 ApprovalRequest 상태를 업데이트합니다.

    Args:
        db: DB 세션
        request_id: ApprovalRequest ID
        user_id: 사용자 ID
        decision: 결정 (approved, rejected, modified)
        modifications: 사용자 수정 사항
        user_notes: 사용자 노트

    Returns:
        성공 여부
    """
    try:
        # 1. UserDecision 레코드 생성
        user_decision = UserDecision(
            request_id=request_id,
            user_id=user_id,
            decision=decision,
            modifications=modifications,
            user_notes=user_notes,
        )
        db.add(user_decision)

        # 2. ApprovalRequest 상태 업데이트
        approval_request = db.query(ApprovalRequestModel).filter(
            ApprovalRequestModel.request_id == request_id
        ).first()

        if approval_request:
            # 상태 매핑: approved -> approved, rejected -> rejected, modified -> approved
            new_status = "approved" if decision in ["approved", "modified"] else "rejected"
            approval_request.status = new_status
            approval_request.responded_at = datetime.utcnow()

            # 수정 사항이 있으면 proposed_actions 업데이트
            if modifications and decision == "modified":
                # 원본 proposed_actions에 수정사항 병합
                original_actions = approval_request.proposed_actions or {}
                approval_request.proposed_actions = {**original_actions, **modifications}

        db.commit()
        logger.info(f"✅ UserDecision 저장 완료: request_id={request_id}, decision={decision}")
        return True

    except Exception as e:
        logger.error(f"❌ UserDecision 저장 실패: {e}")
        db.rollback()
        return False


def _get_approval_request_context(
    db: Session,
    request_id: Optional[str],
) -> tuple[str, Optional[dict]]:
    """
    ApprovalRequest 정보를 조회해 request_type과 proposed_actions를 반환한다.

    Returns:
        (request_type, proposed_actions)
    """
    if not request_id:
        return "trade_approval", None

    try:
        request_uuid = uuid.UUID(request_id)
    except ValueError:
        logger.warning("Invalid request_id format: %s", request_id)
        return "trade_approval", None

    approval_request = (
        db.query(ApprovalRequestModel)
        .filter(ApprovalRequestModel.request_id == request_uuid)
        .first()
    )

    if not approval_request:
        return "trade_approval", None

    request_type = approval_request.request_type or "trade_approval"
    proposed_actions = approval_request.proposed_actions
    return request_type, proposed_actions


def _build_resume_value(
    *,
    approval_type: str,
    user_id: uuid.UUID,
    user_notes: Optional[str],
    modifications: Optional[dict],
    decision: str = "approved",
) -> dict:
    """
    LangGraph resume payload를 approval_type에 맞춰 생성한다.

    ⚠️ LangGraph SubGraph에서 interrupt() 반환값은 작동하지 않으므로,
    resume_value의 필드들이 State에 병합되어야 한다.
    """
    resume_value: dict = {
        "user_id": str(user_id),
        "notes": user_notes,
    }

    if approval_type == "research_plan_approval":
        resume_value["analysis_plan_approved"] = True
    elif approval_type == "rebalance_approval":
        resume_value["rebalance_approved"] = True
    else:  # trade_approval 및 기타 기본값
        # ⚠️ State 플래그로 사용자 응답을 판단하는 방식으로 변경
        resume_value["user_pending_approval"] = True  # 승인 대기 중이었음을 표시
        resume_value["user_decision"] = decision  # "approved" or "rejected"
        resume_value["trade_approved"] = (decision == "approved")

    if modifications:
        resume_value["user_modifications"] = modifications

    return resume_value


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_quantity(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{int(round(value)):,}주"


def _format_quantity_delta(value: Optional[float]) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{int(round(value)):,}주"


def _format_currency(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{int(round(value)):,}원"


def _format_currency_delta(value: Optional[float]) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{int(round(value)):,}원"


def _format_percent(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"{value * 100:.1f}%"


def _format_percent_delta(value: Optional[float]) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value * 100:.1f}%"


def _parse_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.replace(",", "").strip()
        if not normalized:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


def _extract_holding(portfolio: Optional[Dict[str, Any]], stock_code: Optional[str]) -> Optional[Dict[str, Any]]:
    if not portfolio or not stock_code:
        return None
    code = stock_code.upper()
    for holding in portfolio.get("holdings", []) or []:
        holding_code = (holding.get("stock_code") or "").upper()
        if holding_code == code:
            return holding
    return None


def _build_portfolio_effect(
    *,
    stock_code: Optional[str],
    stock_name: Optional[str],
    portfolio_before: Optional[Dict[str, Any]],
    portfolio_after: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not stock_code:
        return None

    before_holding = _extract_holding(portfolio_before, stock_code)
    after_holding = _extract_holding(portfolio_after, stock_code)

    before_qty = _safe_float(before_holding.get("quantity")) if before_holding else 0.0
    after_qty = _safe_float(after_holding.get("quantity")) if after_holding else 0.0
    before_avg = _safe_float(before_holding.get("average_price")) if before_holding else None
    after_avg = _safe_float(after_holding.get("average_price")) if after_holding else before_avg
    before_weight = _safe_float(before_holding.get("weight")) if before_holding else 0.0
    after_weight = _safe_float(after_holding.get("weight")) if after_holding else 0.0

    diff_qty = (after_qty or 0.0) - (before_qty or 0.0)
    diff_avg = (after_avg - before_avg) if (after_avg is not None and before_avg is not None) else None
    diff_weight = (after_weight or 0.0) - (before_weight or 0.0)

    table_lines = [
        "|구분|보유 수량|평균 단가|포트폴리오 비중|",
        "|---|---|---|---|",
        f"|승인 전|{_format_quantity(before_qty)}|{_format_currency(before_avg)}|{_format_percent(before_weight)}|",
        f"|승인 후|{_format_quantity(after_qty)}|{_format_currency(after_avg)}|{_format_percent(after_weight)}|",
    ]
    table_lines.append(
        f"|증감|{_format_quantity_delta(diff_qty)}|{_format_currency_delta(diff_avg)}|{_format_percent_delta(diff_weight)}|"
    )
    table_markdown = "\n".join(table_lines)

    cash_before = _safe_float((portfolio_before or {}).get("cash_balance"))
    cash_after = _safe_float((portfolio_after or {}).get("cash_balance"))
    cash_effect = None
    if cash_before is not None or cash_after is not None:
        diff_cash = None
        if cash_before is not None and cash_after is not None:
            diff_cash = cash_after - cash_before
        cash_effect = {
            "before": cash_before,
            "after": cash_after,
            "diff": diff_cash,
        }

    portfolio_effect = {
        "stock_code": stock_code,
        "stock_name": stock_name or stock_code,
        "before": {
            "quantity": before_qty,
            "average_price": before_avg,
            "weight": before_weight,
        },
        "after": {
            "quantity": after_qty,
            "average_price": after_avg,
            "weight": after_weight,
        },
        "diff": {
            "quantity": diff_qty,
            "average_price": diff_avg,
            "weight": diff_weight,
        },
        "table_markdown": table_markdown,
    }

    if cash_effect:
        portfolio_effect["cash"] = cash_effect

    return portfolio_effect


def _build_risk_effect(
    *,
    risk_before: Optional[Dict[str, Any]],
    risk_after: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not risk_before and not risk_after:
        return None

    metrics = [
        "portfolio_volatility",
        "var_95",
        "sharpe_ratio",
        "max_drawdown_estimate",
    ]
    effect: Dict[str, Dict[str, Optional[float]]] = {}
    for key in metrics:
        before_val = _safe_float((risk_before or {}).get(key))
        after_val = _safe_float((risk_after or {}).get(key))
        diff_val = None
        if before_val is not None and after_val is not None:
            diff_val = after_val - before_val
        effect[key] = {
            "before": before_val,
            "after": after_val,
            "diff": diff_val,
        }

    return effect


def _build_trade_execution_payload(
    *,
    resume_result: Dict[str, Any],
    state_values: Dict[str, Any],
    approval_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    approval_data = approval_data or {}
    trade_result = (
        (resume_result or {}).get("trade_result")
        or state_values.get("trade_result")
        or {}
    )

    stock_code = (
        state_values.get("stock_code")
        or approval_data.get("stock_code")
        or trade_result.get("stock_code")
    )
    stock_name = (
        state_values.get("stock_name")
        or approval_data.get("stock_name")
        or trade_result.get("stock_name")
        or stock_code
    )
    trade_action = (state_values.get("trade_action") or approval_data.get("action") or "buy").lower()
    action_label = "매수" if trade_action == "buy" else "매도"
    executed_qty = (
        trade_result.get("quantity")
        or state_values.get("trade_quantity")
        or approval_data.get("quantity")
    )
    executed_price = (
        trade_result.get("price")
        or state_values.get("trade_price")
        or approval_data.get("price")
    )

    summary_text = None
    if executed_qty and executed_price:
        total_amount = int(round(float(executed_qty) * float(executed_price)))
        summary_text = (
            f"✅ {stock_name or stock_code} {action_label} 완료 - "
            f"{int(executed_qty):,}주 @ {int(executed_price):,}원 (총 {total_amount:,}원)"
        )
    elif stock_name:
        summary_text = f"✅ {stock_name} {action_label}가 완료되었습니다."
    else:
        summary_text = "✅ 매매가 실행되었습니다."

    portfolio_effect = _build_portfolio_effect(
        stock_code=stock_code,
        stock_name=stock_name,
        portfolio_before=state_values.get("portfolio_before") or approval_data.get("portfolio_before"),
        portfolio_after=state_values.get("portfolio_after") or approval_data.get("portfolio_after"),
    )

    risk_effect = _build_risk_effect(
        risk_before=state_values.get("risk_before") or approval_data.get("risk_before"),
        risk_after=state_values.get("risk_after") or approval_data.get("risk_after"),
    )

    payload: Dict[str, Any] = {
        "summary": summary_text,
    }
    if trade_result:
        payload["trade_result"] = trade_result
    if portfolio_effect:
        payload["portfolio_effect"] = portfolio_effect
    if risk_effect:
        payload["risk_effect"] = risk_effect

    return payload


def _build_generic_final_response(
    *,
    resume_result: Dict[str, Any],
    state_values: Dict[str, Any],
) -> Dict[str, Any]:
    summary_text = (
        resume_result.get("summary")
        or state_values.get("summary")
        or "처리가 완료되었습니다."
    )
    details = resume_result.get("details") or state_values.get("agent_results")

    payload: Dict[str, Any] = {"summary": summary_text}
    if details:
        payload["details"] = details
    return payload


def _build_final_response_payload(
    *,
    request_type: str,
    resume_result: Dict[str, Any],
    state_values: Dict[str, Any],
    approval_data: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if request_type == "trade_approval":
        return _build_trade_execution_payload(
            resume_result=resume_result,
            state_values=state_values,
            approval_data=approval_data,
        )

    return _build_generic_final_response(
        resume_result=resume_result,
        state_values=state_values,
    )


class ApprovalRequest(BaseModel):
    """승인 요청 스키마"""

    thread_id: str = Field(description="대화 스레드 ID")
    decision: Literal["approved", "rejected", "modified"] = Field(
        description="승인 결정"
    )
    request_id: Optional[str] = Field(
        default=None, description="DB에 저장된 ApprovalRequest ID"
    )
    modifications: Optional[dict] = None
    user_input: Optional[str] = Field(
        default=None,
        description="사용자가 입력한 자유 텍스트 (modify 시 추가 요청사항)"
    )
    user_notes: Optional[str] = None


class ApprovalResponse(BaseModel):
    """승인 응답 스키마"""
    status: str
    message: str
    conversation_id: str
    result: Optional[dict] = None


@router.post("/approve", response_model=ApprovalResponse)
async def approve_action(
    approval: ApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    승인 혹은 거부 결정을 처리하는 엔드포인트입니다.

    처리 흐름:
    1. thread_id를 통해 중단된 그래프 상태를 조회합니다.
    2. 사용자 결정을 DB에 저장합니다.
    3. 결정 값에 따라 Command(resume=...)를 전달합니다.
    4. 그래프를 재개하고 최종 결과를 반환합니다.
    """
    try:
        conversation_uuid = _ensure_uuid(approval.thread_id)
        conversation_id = str(conversation_uuid)

        session_row = (
            db.query(ChatSession)
            .filter(ChatSession.conversation_id == conversation_uuid)
            .first()
        )
        # intervention_required/hitl_config는 session_metadata에서 복원하거나 기본값 사용
        intervention_required = False
        hitl_config = HITLConfig()
        if session_row and session_row.session_metadata:
            intervention_required = session_row.session_metadata.get("intervention_required", False)
            hitl_meta = session_row.session_metadata.get("hitl_config")
            if hitl_meta:
                hitl_config = HITLConfig(**hitl_meta)

        decision_metadata = {
            "decision": approval.decision,
            "user_notes": approval.user_notes,
            "modifications": approval.modifications,
        }

        await chat_history_service.upsert_session(
            conversation_id=conversation_uuid,
            user_id=DEMO_USER_UUID,
        )
        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="user",
            content=f"승인 결정: {approval.decision}",
            metadata=decision_metadata,
        )

        # 메모리 체크포인터를 사용해 그래프 상태를 복구
        app = await build_graph(intervention_required=intervention_required)

        config: RunnableConfig = {
            "configurable": {
                "thread_id": conversation_id,
            }
        }

        configured_app = app.with_config(config)

        def _trade_summary(payload: Dict[str, Any]) -> str:
            summary_text = payload.get("summary")
            trade = payload.get("trade_result") or {}
            portfolio_effect = payload.get("portfolio_effect") or {}
            risk_effect = payload.get("risk_effect") or {}

            parts: List[str] = []
            if summary_text:
                parts.append(summary_text)

            table_markdown = portfolio_effect.get("table_markdown")
            if table_markdown:
                parts.append(table_markdown)

            cash_effect = portfolio_effect.get("cash") if portfolio_effect else None
            if cash_effect and (
                cash_effect.get("before") is not None or cash_effect.get("after") is not None
            ):
                parts.append(
                    "💵 현금 잔액: "
                    f"{_format_currency(cash_effect.get('before'))} → "
                    f"{_format_currency(cash_effect.get('after'))} "
                    f"({_format_currency_delta(cash_effect.get('diff'))})"
                )

            if risk_effect:
                risk_parts: List[str] = []
                vol = risk_effect.get("portfolio_volatility")
                if vol and (vol.get("before") is not None or vol.get("after") is not None):
                    risk_parts.append(
                        f"변동성 {_format_percent(vol.get('before'))} → {_format_percent(vol.get('after'))}"
                    )
                var95 = risk_effect.get("var_95")
                if var95 and (var95.get("before") is not None or var95.get("after") is not None):
                    risk_parts.append(
                        f"VaR95 {_format_percent(var95.get('before'))} → {_format_percent(var95.get('after'))}"
                    )
                sharpe = risk_effect.get("sharpe_ratio")
                if sharpe and (sharpe.get("before") is not None or sharpe.get("after") is not None):
                    sharpe_before = sharpe.get("before")
                    sharpe_after = sharpe.get("after")
                    before_text = f"{sharpe_before:.2f}" if sharpe_before is not None else "-"
                    after_text = f"{sharpe_after:.2f}" if sharpe_after is not None else "-"
                    risk_parts.append(f"샤프 {before_text} → {after_text}")
                if risk_parts:
                    parts.append("⚖️ 리스크 변화: " + ", ".join(risk_parts))

            if trade:
                order_id = trade.get("order_id", "N/A")
                status = trade.get("status", "완료")
                price = trade.get("price")
                quantity = trade.get("quantity")
                order_line = (
                    f"🧾 주문 {order_id} | 상태 {status} | "
                    f"체결가 {_format_currency(price)} | 수량 {_format_quantity(quantity)}"
                )
                parts.append(order_line)

            return "\n\n".join(filter(None, parts)) or "처리가 완료되었습니다."

        # DB에 사용자 결정 저장 (request_id가 있는 경우)
        request_type, approval_context = _get_approval_request_context(
            db, approval.request_id
        )

        if approval.request_id:
            try:
                request_uuid = uuid.UUID(approval.request_id)
                _save_user_decision_to_db(
                    db=db,
                    request_id=request_uuid,
                    user_id=DEMO_USER_UUID,
                    decision=approval.decision,
                    modifications=approval.modifications,
                    user_notes=approval.user_notes
                )
            except ValueError as e:
                logger.warning(f"Invalid request_id: {approval.request_id}, {e}")

        # 승인 또는 수정된 승인 처리
        if approval.decision in ["approved", "modified"]:
            combined_modifications: Optional[dict] = approval.modifications.copy() if approval.modifications else None
            if approval.user_input:
                if not combined_modifications:
                    combined_modifications = {}
                combined_modifications["user_input"] = approval.user_input

            if combined_modifications:
                logger.info("✏️ 사용자 수정사항 전달: %s", combined_modifications)

            # Resume value 준비
            # ⚠️ LangGraph 베스트 프랙티스:
            # - aupdate_state를 호출하면 안 됨 (새로운 체크포인트 생성으로 interrupt 정보 손실)
            # - resume value를 통해 모든 필요한 정보를 전달
            # - 중단된 노드가 resume value를 처리하며 state 업데이트
            resume_value = _build_resume_value(
                approval_type=request_type,
                user_id=DEMO_USER_UUID,
                user_notes=approval.user_notes,
                modifications=combined_modifications,
                decision="modified" if approval.decision == "modified" else "approved",
            )

            logger.info("📋 [Approve] Resume value 상세: %s", resume_value)

            # ⚠️ LangGraph interrupt/resume 패턴 - SubGraph 올바른 구현
            # SubGraph에서 interrupt()의 반환값이 직접 노드로 전달되지 않음
            # 대신 aupdate_state()를 사용하여 state를 먼저 업데이트한 후,
            # ainvoke()로 그래프를 계속 진행시켜야 함

            logger.info(
                "▶️ [Approve] State 업데이트 시작: approval_type=%s, trade_approved=%s, has_modifications=%s",
                request_type,
                resume_value.get("trade_approved"),
                bool(resume_value.get("user_modifications")),
            )

            # Step 1: State 업데이트 (Master graph의 state에 resume_value 병합)
            await configured_app.aupdate_state(config, resume_value)
            logger.info("✅ State 업데이트 완료")

            # Step 2: SubGraph의 interrupt를 올바르게 처리
            # ⚠️ 중요: astream(None)은 Master만 진행하고 SubGraph의 interrupt를 처리하지 못함
            # ainvoke(None)을 사용하면 SubGraph의 interrupt 상태까지 함께 처리됨
            result = {}
            try:
                result = await configured_app.ainvoke(None, config=config)
                logger.info("✅ [Approve] ainvoke로 SubGraph interrupt 처리 완료")
            except Exception as e:
                logger.warning("⚠️ [Approve] ainvoke 실행 중 오류: %s", e)
                # 폴백: astream 사용
                async for event in configured_app.astream(None, config=config):
                    if "final_state" in event:
                        result = event.get("final_state", {})
                    elif isinstance(event, dict):
                        for node_name, node_result in event.items():
                            if isinstance(node_result, dict) and "messages" in node_result:
                                result.update(node_result)

            state_after_resume = await configured_app.aget_state(config)
            state_values = getattr(state_after_resume, "values", {}) if state_after_resume else {}

            logger.info(
                "📊 [Approve] Graph 완료: trade_prepared=%s, trade_executed=%s",
                state_values.get("trade_prepared"),
                state_values.get("trade_executed"),
            )

            if getattr(state_after_resume, "next", None):
                hitl_result = await handle_hitl_interrupt(
                    state=state_after_resume,
                    conversation_uuid=conversation_uuid,
                    conversation_id=conversation_id,
                    user_id=DEMO_USER_UUID,
                    db=db,
                    intervention_required=intervention_required,
                    hitl_config=hitl_config,
                )
                if hitl_result:
                    return ApprovalResponse(
                        status="pending",
                        message=hitl_result["message"],
                        conversation_id=conversation_id,
                        result={
                            "requires_approval": True,
                            "approval_request": hitl_result["approval_request"],
                        },
                    )

            final_response = result.get("final_response") or {}
            if not final_response:
                final_response = _build_final_response_payload(
                    request_type=request_type,
                    resume_result=result,
                    state_values=state_values,
                    approval_data=approval_context,
                )
            message_text = _trade_summary(final_response)

            await chat_history_service.append_message(
                conversation_id=conversation_uuid,
                role="assistant",
                content=message_text,
                metadata={"decision": approval.decision},
            )
            await chat_history_service.upsert_session(
                conversation_id=conversation_uuid,
                user_id=DEMO_USER_UUID,
                metadata={"decision": approval.decision},
                summary=final_response.get("summary"),
            )

            response_status = "modified" if approval.decision == "modified" else "approved"
            response_message = (
                "수정 후 승인 - 매매가 실행되었습니다."
                if approval.decision == "modified"
                else "승인 완료 - 매매가 실행되었습니다."
            )
            return ApprovalResponse(
                status=response_status,
                message=response_message,
                conversation_id=conversation_id,
                result=final_response,
            )

        if approval.decision == "rejected":
            # Rejection의 경우도 aupdate_state + ainvoke 사용
            resume_value = _build_resume_value(
                approval_type=request_type,
                user_id=DEMO_USER_UUID,
                user_notes=approval.user_notes,
                modifications=None,
                decision="rejected",
            )

            logger.info("▶️ [Approve] 거부 - State 업데이트 시작")

            # Step 1: State 업데이트
            await configured_app.aupdate_state(config, resume_value)
            logger.info("✅ State 업데이트 완료")

            # Step 2: 그래프 계속 실행
            await configured_app.ainvoke(None, config=config)
            logger.info("✅ [Approve] 거부 처리 완료")

            message_text = "승인 거부 - 매매가 취소되었습니다."
            await chat_history_service.append_message(
                conversation_id=conversation_uuid,
                role="assistant",
                content=message_text,
                metadata={"decision": "rejected"},
            )
            await chat_history_service.upsert_session(
                conversation_id=conversation_uuid,
                user_id=DEMO_USER_UUID,
                metadata={"decision": "rejected"},
                summary="사용자가 거부함",
            )

            return ApprovalResponse(
                status="rejected",
                message=message_text,
                conversation_id=conversation_id,
                result={"cancelled": True},
            )

        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision: {approval.decision}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [Approve] 승인 처리 실패: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Approval processing error: {str(e) or type(e).__name__}",
        )
