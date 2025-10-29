"""
채팅 및 승인 관련 API 엔드포인트 모음
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, cast
import uuid
import os
import logging

logger = logging.getLogger(__name__)

from src.agents.graph_master import build_graph
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph_sdk.schema import Command
from src.services import chat_history_service, portfolio_service
from src.services.portfolio_preview_service import (
    calculate_portfolio_preview,
    calculate_weight_change
)
from src.schemas.hitl import ApprovalRequest as HITLApprovalRequest
from src.config.settings import settings

router = APIRouter()

DEMO_USER_UUID = settings.demo_user_uuid


def _ensure_uuid(value: Optional[str]) -> uuid.UUID:
    """Validate or generate a conversation UUID."""
    if value:
        try:
            return uuid.UUID(str(value))
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
    message: str = Field(..., min_length=1, description="사용자 메시지 (비어있으면 안 됨)")
    conversation_id: Optional[str] = None
    automation_level: int = Field(default=2, ge=1, le=3, description="자동화 레벨: 1=Pilot, 2=Copilot, 3=Advisor")

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
    automation_level: int
    message_count: int
    created_at: Optional[str] = None


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
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

        # Ensure session exists and store the incoming user message
        await chat_history_service.upsert_session(
            conversation_id=conversation_uuid,
            user_id=DEMO_USER_UUID,
            automation_level=request.automation_level,
        )
        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="user",
            content=request.message,
        )

        # Build graph with automation level
        app = build_graph(automation_level=request.automation_level)

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
            "automation_level": request.automation_level,
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
        }

        # Run Langgraph
        result = await configured_app.ainvoke(initial_state)

        # Check for interrupt
        state = await configured_app.aget_state()

        if state.next:  # Interrupt 발생 (다음 노드가 있음)
            interrupts = state.tasks
            interrupt_info = None

            if interrupts:
                interrupt_task = interrupts[0]
                interrupt_info = interrupt_task.interrupts[0] if interrupt_task.interrupts else None

            # Interrupt 데이터 파싱
            interrupt_data = interrupt_info.value if interrupt_info else {}

            # 기본 approval_request (기존 형식)
            approval_request = {
                "type": "trade_approval",
                "thread_id": conversation_id,
                "pending_node": state.next[0] if state.next else None,
                "interrupt_data": interrupt_data,
                "message": "매매 주문을 승인하시겠습니까?",
            }

            # 매매 주문인 경우 상세 정보 계산
            if interrupt_data and interrupt_data.get("action") in ["buy", "sell"]:
                try:
                    # 포트폴리오 조회
                    snapshot = await portfolio_service.get_portfolio_snapshot()

                    if snapshot and snapshot.portfolio_data:
                        portfolio_data = snapshot.portfolio_data
                        holdings = portfolio_data.get("holdings", [])
                        total_value = float(portfolio_data.get("total_value", 0))
                        cash = float(portfolio_data.get("cash_balance", 0))

                        # 현재/예상 비중 계산
                        current_weight, expected_weight = await calculate_weight_change(
                            current_holdings=holdings,
                            new_order=interrupt_data,
                            total_value=total_value,
                            cash=cash
                        )

                        # 예상 포트폴리오 미리보기
                        portfolio_preview = await calculate_portfolio_preview(
                            current_holdings=holdings,
                            new_order=interrupt_data,
                            total_value=total_value,
                            cash=cash
                        )

                        # 리스크 경고 생성
                        risk_warning = None
                        if expected_weight > 0.4:
                            risk_warning = f"⚠️ 단일 종목 {expected_weight*100:.1f}% 집중 - 분산 투자를 권장합니다"

                        # HITLApprovalRequest 구조로 변환
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
                        alternatives=None,  # TODO: Risk Agent에서 생성
                            expected_portfolio_preview=portfolio_preview.dict() if portfolio_preview else None
                        ).dict()

                except Exception as e:
                    logger.warning(f"HITL 상세 정보 계산 실패: {e}")
                    # 실패 시 기본 형식 유지

            message_text = "🔔 사용자 승인이 필요합니다."

            await chat_history_service.append_message(
                conversation_id=conversation_uuid,
                role="assistant",
                content=message_text,
                metadata={"requires_approval": True, "approval_request": approval_request},
            )
            await chat_history_service.upsert_session(
                conversation_id=conversation_uuid,
                user_id=DEMO_USER_UUID,
                automation_level=request.automation_level,
                metadata={"interrupted": True},
            )

            return ChatResponse(
                message=message_text,
                conversation_id=conversation_id,
                requires_approval=True,
                approval_request=approval_request,
                metadata={
                    "interrupted": True,
                    "automation_level": request.automation_level,
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
            "automation_level": request.automation_level,
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
            automation_level=request.automation_level,
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

class ApprovalRequest(BaseModel):
    """승인 요청 스키마"""
    thread_id: str = Field(description="대화 스레드 ID")
    decision: str = Field(description="승인 결정: approved, rejected, modified")
    automation_level: int = Field(default=2, ge=1, le=3)
    modifications: Optional[dict] = None
    user_notes: Optional[str] = None


class ApprovalResponse(BaseModel):
    """승인 응답 스키마"""
    status: str
    message: str
    conversation_id: str
    result: Optional[dict] = None


@router.post("/approve", response_model=ApprovalResponse)
async def approve_action(approval: ApprovalRequest):
    """
    승인 혹은 거부 결정을 처리하는 엔드포인트입니다.

    처리 흐름:
    1. thread_id를 통해 중단된 그래프 상태를 조회합니다.
    2. 결정 값에 따라 Command(resume=...)를 전달합니다.
    3. 그래프를 재개하고 최종 결과를 반환합니다.
    """
    try:
        conversation_uuid = _ensure_uuid(approval.thread_id)
        conversation_id = str(conversation_uuid)

        decision_metadata = {
            "decision": approval.decision,
            "user_notes": approval.user_notes,
            "modifications": approval.modifications,
        }

        await chat_history_service.upsert_session(
            conversation_id=conversation_uuid,
            user_id=DEMO_USER_UUID,
            automation_level=approval.automation_level,
        )
        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="user",
            content=f"승인 결정: {approval.decision}",
            metadata=decision_metadata,
        )

        app = build_graph(automation_level=approval.automation_level)

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

        if approval.decision == "approved":
            resume_value = {
                "approved": True,
                "user_id": str(DEMO_USER_UUID),
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
                metadata={"decision": "approved"},
            )
            await chat_history_service.upsert_session(
                conversation_id=conversation_uuid,
                user_id=DEMO_USER_UUID,
                automation_level=approval.automation_level,
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
            await configured_app.aupdate_state(
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
                automation_level=approval.automation_level,
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
                automation_level=approval.automation_level,
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
        raise HTTPException(
            status_code=500,
            detail=f"Approval processing error: {str(e)}",
        )
