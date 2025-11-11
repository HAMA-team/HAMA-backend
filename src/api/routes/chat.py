"""
채팅 및 승인 관련 API 엔드포인트 모음
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any, Literal, cast
import uuid
import os
import logging

logger = logging.getLogger(__name__)

from src.agents.graph_master import build_graph
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.schema import Command
from src.services import chat_history_service
from src.services.hitl_interrupt_service import handle_hitl_interrupt
from src.services.user_profile_service import UserProfileService
from src.schemas.hitl_config import (
    HITLConfig,
    PRESET_COPILOT,
    level_to_config,
    config_to_level,
)
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
        default_factory=PRESET_COPILOT.model_copy,
        validation_alias=AliasChoices("hitl_config", "hitlConfig"),
        description="HITL 단계별 설정 (기본값: Copilot)",
    )
    automation_level: Optional[int] = Field(
        default=None,
        ge=1,
        le=3,
        validation_alias=AliasChoices("automation_level", "automationLevel"),
        description="[Deprecated] automation_level은 hitl_config로 대체되었습니다.",
    )

    @field_validator("message")
    @classmethod
    def validate_message_not_whitespace(cls, v: str) -> str:
        """메시지 검증: 공백만 있는 메시지 거부"""
        if not v.strip():
            raise ValueError("메시지는 공백만 포함할 수 없습니다")
        return v

    @model_validator(mode="after")
    def _apply_legacy_level(self) -> "ChatRequest":
        """
        legacy automation_level 입력이 존재할 경우 대응되는 프리셋으로 덮어쓴다.
        """
        if self.automation_level is not None:
            self.hitl_config = level_to_config(self.automation_level)
        return self


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
    hitl_config: HITLConfig = Field(default_factory=PRESET_COPILOT.model_copy)
    automation_level: Optional[int] = Field(
        default=None,
        description="[Deprecated] 호환성 유지를 위한 automation_level 필드",
    )
    message_count: int
    created_at: Optional[str] = None

    @model_validator(mode="after")
    def _populate_legacy_level(self) -> "ChatSessionSummary":
        if self.automation_level is None:
            self.automation_level = config_to_level(self.hitl_config)
        return self


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
        legacy_level = config_to_level(hitl_config)

        # Get user profile for dynamic worker selection
        user_profile_service = UserProfileService()
        user_profile = user_profile_service.get_user_profile(DEMO_USER_UUID, db)
        logger.info("📋 [Chat] UserProfile 로드 완료: preferred_depth=%s, expertise_level=%s",
                    user_profile.get("preferred_depth"), user_profile.get("expertise_level"))

        # Ensure session exists and store the incoming user message
        await chat_history_service.upsert_session(
            conversation_id=conversation_uuid,
            user_id=DEMO_USER_UUID,
            automation_level=legacy_level,
        )
        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="user",
            content=request.message,
        )

        # Build graph with automation level
        app = build_graph(automation_level=legacy_level)

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
            "automation_level": legacy_level,
            "user_profile": user_profile,  # Dynamic worker selection을 위한 사용자 프로파일
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
            "routing_decision": None,
            "personalization": None,
            "worker_action": None,
            "worker_params": None,
            "direct_answer": None,
            "clarification_needed": False,
            "clarification_message": None,
            "conversation_history": [],
        }

        # Run Langgraph
        result = await configured_app.ainvoke(initial_state)

        # Check for interrupt
        state = await configured_app.aget_state()

        if state.next:  # Interrupt 발생
            hitl_result = await handle_hitl_interrupt(
                state=state,
                conversation_uuid=conversation_uuid,
                conversation_id=conversation_id,
                user_id=DEMO_USER_UUID,
                db=db,
                automation_level=legacy_level,
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
                        "automation_level": legacy_level,
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

        if "strategy_agent" in details:
            strategy = details["strategy_agent"]
            message_parts.append(
                f"\n📈 **전략**\n"
                f"  - 의견: {strategy.get('action', 'N/A')}\n"
                f"  - 신뢰도: {strategy.get('confidence', 'N/A')}"
            )

        if "risk_agent" in details:
            risk = details["risk_agent"]
            warnings = risk.get("warnings", [])
            warning_text = ", ".join(warnings) if warnings else "없음"
            message_parts.append(
                f"\n⚠️ **리스크**\n"
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
            "automation_level": legacy_level,
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
            automation_level=legacy_level,
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
        "automation_level": session.automation_level,
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
                automation_level=session.automation_level or 2,
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
        legacy_level = session_row.automation_level if session_row else 2

        decision_metadata = {
            "decision": approval.decision,
            "user_notes": approval.user_notes,
            "modifications": approval.modifications,
        }

        await chat_history_service.upsert_session(
            conversation_id=conversation_uuid,
            user_id=DEMO_USER_UUID,
            automation_level=legacy_level,
        )
        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="user",
            content=f"승인 결정: {approval.decision}",
            metadata=decision_metadata,
        )

        # 메모리 체크포인터를 사용해 그래프 상태를 복구
        app = build_graph(automation_level=legacy_level)

        config: RunnableConfig = {
            "configurable": {
                "thread_id": conversation_id,
            }
        }

        configured_app = app.with_config(config)

        def _trade_summary(payload: Dict[str, Any]) -> str:
            summary_text = payload.get("summary")
            trade = payload.get("trade_result") or {}
            parts = [summary_text] if summary_text else []
            if trade:
                parts.append(
                    f"주문 {trade.get('order_id', 'N/A')} 상태 {trade.get('status', 'N/A')} "
                    f"체결가 {trade.get('price', 0)} 수량 {trade.get('quantity', 0)}"
                )
            return "\n".join(filter(None, parts)) or "처리가 완료되었습니다."

        # DB에 사용자 결정 저장 (request_id가 있는 경우)
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
            resume_value = {
                "approved": True,
                "user_id": str(DEMO_USER_UUID),
                "notes": approval.user_notes,
            }

            # 사용자 수정사항 적용 (modified인 경우)
            if approval.decision == "modified" and approval.modifications:
                # modifications를 resume_value에 병합
                resume_value["modifications"] = approval.modifications
                logger.info(f"✏️ 사용자 수정사항 적용: {approval.modifications}")

            resume_command: Command = cast(Command, {"resume": resume_value})
            result = await configured_app.ainvoke(resume_command)
            final_response = result.get("final_response", {})
            message_text = _trade_summary(final_response)

            await chat_history_service.append_message(
                conversation_id=conversation_uuid,
                role="assistant",
                content=message_text,
                metadata={"decision": "approved"},
            )
            await chat_history_service.upsert_session(
                conversation_id=conversation_uuid,
                user_id=DEMO_USER_UUID,
                automation_level=legacy_level,
                metadata={"decision": "approved"},
                summary=final_response.get("summary"),
            )

            return ApprovalResponse(
                status="approved",
                message="승인 완료 - 매매가 실행되었습니다.",
                conversation_id=conversation_id,
                result=final_response,
            )

        if approval.decision == "rejected":
            # LangGraph aupdate_state 시그니처: aupdate_state(config, values, as_node=None)
            await configured_app.aupdate_state(
                config,
                {
                    "final_response": {
                        "summary": "사용자가 거부함",
                        "cancelled": True,
                        "reason": approval.user_notes or "User rejected",
                    }
                }
            )

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
                automation_level=legacy_level,
                metadata={"decision": "rejected"},
                summary="사용자가 거부함",
            )

            return ApprovalResponse(
                status="rejected",
                message=message_text,
                conversation_id=conversation_id,
                result={"cancelled": True},
            )

        if approval.decision == "modified":
            resume_value = {
                "approved": True,
                "user_id": str(DEMO_USER_UUID),
                "modifications": approval.modifications,
                "notes": approval.user_notes,
            }

            resume_command: Command = cast(Command, {"resume": resume_value})
            result = await configured_app.ainvoke(resume_command)
            final_response = result.get("final_response", {})
            message_text = _trade_summary(final_response)

            await chat_history_service.append_message(
                conversation_id=conversation_uuid,
                role="assistant",
                content=message_text,
                metadata={"decision": "modified"},
            )
            await chat_history_service.upsert_session(
                conversation_id=conversation_uuid,
                user_id=DEMO_USER_UUID,
                automation_level=legacy_level,
                metadata={"decision": "modified"},
                summary=final_response.get("summary"),
            )

            return ApprovalResponse(
                status="modified",
                message="수정 후 승인 - 매매가 실행되었습니다.",
                conversation_id=conversation_id,
                result=final_response,
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
