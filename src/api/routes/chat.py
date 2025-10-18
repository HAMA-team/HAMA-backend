"""
채팅 및 승인 관련 API 엔드포인트 모음
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
import os

from src.agents.graph_master import build_graph
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessage
from src.services import chat_history_service
from src.config.settings import settings

router = APIRouter()

DEFAULT_USER_UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "user_001")


def _is_test_mode() -> bool:
    env_value = os.getenv("ENV", settings.ENV or "").lower()
    return env_value == "test" or not settings.ANTHROPIC_API_KEY


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
    message: str
    conversation_id: Optional[str] = None
    automation_level: int = Field(default=2, ge=1, le=3, description="자동화 레벨: 1=Pilot, 2=Copilot, 3=Advisor")


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


async def _mock_chat_response(
    conversation_uuid: uuid.UUID,
    request: ChatRequest,
) -> ChatResponse:
    conversation_id = str(conversation_uuid)
    message_lower = request.message.lower()

    is_trade_request = any(keyword in message_lower for keyword in ("매수", "매도", "sell", "buy"))

    if is_trade_request:
        approval_request = {
            "type": "trade_approval",
            "thread_id": conversation_id,
            "pending_node": "mock_trading_node",
            "interrupt_data": {"summary": "모의 투자 승인 필요"},
            "message": "모의 매매 주문을 승인하시겠습니까?",
        }
        assistant_message = (
            "🔔 현재 환경은 테스트 모드입니다.\n"
            "모의 매매 요청이 접수되었으며 승인이 필요합니다."
        )
        message_metadata = {
            "intent": "trade_execution",
            "agents_called": ["mock_trading_agent"],
            "hitl_required": True,
            "automation_level": request.automation_level,
        }
        requires_approval = True
    else:
        approval_request = None
        assistant_message = (
            "📋 테스트 응답입니다.\n"
            f"요청하신 메시지: {request.message}"
        )
        message_metadata = {
            "intent": "general_inquiry",
            "agents_called": ["mock_general_agent"],
            "hitl_required": False,
            "automation_level": request.automation_level,
        }
        requires_approval = False

    await chat_history_service.append_message(
        conversation_id=conversation_uuid,
        role="assistant",
        content=assistant_message,
        metadata=message_metadata,
    )
    await chat_history_service.upsert_session(
        conversation_id=conversation_uuid,
        user_id=DEFAULT_USER_UUID,
        automation_level=request.automation_level,
        metadata=message_metadata,
        summary=assistant_message.split("\n")[0],
        last_agent=message_metadata["agents_called"][-1],
    )

    return ChatResponse(
        message=assistant_message,
        conversation_id=conversation_id,
        requires_approval=requires_approval,
        approval_request=approval_request,
        metadata=message_metadata,
    )


async def _mock_approval_response(approval: "ApprovalRequest") -> "ApprovalResponse":
    conversation_uuid = _ensure_uuid(approval.thread_id)
    conversation_id = str(conversation_uuid)
    decision = approval.decision

    if decision == "approved":
        summary = "모의 매매가 승인되었습니다."
        result = {
            "summary": summary,
            "status": "filled",
            "automation_level": approval.automation_level,
        }
        message_text = "승인 완료 - 모의 매매가 실행되었습니다."
    elif decision == "modified":
        summary = "모의 매매가 수정 후 승인되었습니다."
        result = {
            "summary": summary,
            "status": "modified",
            "modifications": approval.modifications,
            "automation_level": approval.automation_level,
        }
        message_text = "수정 후 승인 - 모의 매매가 실행되었습니다."
    elif decision == "rejected":
        summary = "사용자가 모의 매매를 거부했습니다."
        result = {"cancelled": True}
        message_text = "승인 거부 - 모의 매매가 취소되었습니다."
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision: {decision}"
        )

    metadata = {"decision": decision}

    await chat_history_service.append_message(
        conversation_id=conversation_uuid,
        role="assistant",
        content=message_text,
        metadata=metadata,
    )
    await chat_history_service.upsert_session(
        conversation_id=conversation_uuid,
        user_id=DEFAULT_USER_UUID,
        automation_level=approval.automation_level,
        metadata=metadata,
        summary=summary,
        last_agent="mock_trading_agent",
    )

    return ApprovalResponse(
        status=decision,
        message=message_text,
        conversation_id=conversation_id,
        result=result,
    )


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
            user_id=DEFAULT_USER_UUID,
            automation_level=request.automation_level,
        )
        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="user",
            content=request.message,
        )

        if _is_test_mode():
            return await _mock_chat_response(conversation_uuid, request)

        # Build graph with automation level
        app = build_graph(automation_level=request.automation_level)

        # Config for checkpointer
        config = {
            "configurable": {
                "thread_id": conversation_id,
            }
        }

        # Initial state - Langgraph 표준: messages 사용
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "user_id": str(DEFAULT_USER_UUID),
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
        result = await app.ainvoke(initial_state, config=config)

        # Check for interrupt
        state = await app.aget_state(config)

        if state.next:  # Interrupt 발생 (다음 노드가 있음)
            interrupts = state.tasks
            interrupt_info = None

            if interrupts:
                interrupt_task = interrupts[0]
                interrupt_info = interrupt_task.interrupts[0] if interrupt_task.interrupts else None

            approval_request = {
                "type": "trade_approval",
                "thread_id": conversation_id,
                "pending_node": state.next[0] if state.next else None,
                "interrupt_data": interrupt_info.value if interrupt_info else {},
                "message": "매매 주문을 승인하시겠습니까?",
            }
            message_text = "🔔 사용자 승인이 필요합니다."

            await chat_history_service.append_message(
                conversation_id=conversation_uuid,
                role="assistant",
                content=message_text,
                metadata={"requires_approval": True, "approval_request": approval_request},
            )
            await chat_history_service.upsert_session(
                conversation_id=conversation_uuid,
                user_id=DEFAULT_USER_UUID,
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
            user_id=DEFAULT_USER_UUID,
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
    summaries = await chat_history_service.list_sessions(limit=limit)

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
            user_id=DEFAULT_USER_UUID,
            automation_level=approval.automation_level,
        )
        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="user",
            content=f"승인 결정: {approval.decision}",
            metadata=decision_metadata,
        )

        if _is_test_mode():
            return await _mock_approval_response(approval)

        app = build_graph(automation_level=approval.automation_level)

        config = {
            "configurable": {
                "thread_id": conversation_id,
            }
        }

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
                "user_id": str(DEFAULT_USER_UUID),
                "notes": approval.user_notes,
            }

            result = await app.ainvoke(Command(resume=resume_value), config=config)
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
                user_id=DEFAULT_USER_UUID,
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
            await app.aupdate_state(
                config,
                {
                    "final_response": {
                        "summary": "사용자가 거부함",
                        "cancelled": True,
                        "reason": approval.user_notes or "User rejected",
                    }
                },
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
                user_id=DEFAULT_USER_UUID,
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
                "user_id": str(DEFAULT_USER_UUID),
                "modifications": approval.modifications,
                "notes": approval.user_notes,
            }

            result = await app.ainvoke(Command(resume=resume_value), config=config)
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
                user_id=DEFAULT_USER_UUID,
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
