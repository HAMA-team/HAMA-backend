"""
Chat API endpoints - Main interface for user interaction
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid

from src.agents.graph_master import run_graph, build_graph
from langgraph.types import Command

router = APIRouter()


class ChatMessage(BaseModel):
    """Chat message schema"""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Chat request schema"""
    message: str
    conversation_id: Optional[str] = None
    automation_level: int = Field(default=2, ge=1, le=3, description="자동화 레벨: 1=Pilot, 2=Copilot, 3=Advisor")


class ChatResponse(BaseModel):
    """Chat response schema"""
    message: str
    conversation_id: str
    requires_approval: bool = False
    approval_request: Optional[dict] = None
    metadata: Optional[dict] = None


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint - Routes user queries to appropriate agents

    Flow:
    1. Master Agent receives query
    2. Master Agent routes to appropriate sub-agents
    3. Sub-agents process and return results
    4. Master Agent aggregates results
    5. HITL check and response generation
    6. Interrupt 확인 및 승인 요청
    """
    try:
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or str(uuid.uuid4())

        # Build graph with automation level
        app = build_graph(automation_level=request.automation_level)

        # Config for checkpointer
        config = {
            "configurable": {
                "thread_id": conversation_id,
            }
        }

        # Initial state
        initial_state = {
            "query": request.message,
            "request_id": conversation_id,
            "automation_level": request.automation_level,
            "intent": None,
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

        # Run LangGraph
        result = await app.ainvoke(initial_state, config=config)

        # Check for interrupt
        state = await app.aget_state(config)

        if state.next:  # Interrupt 발생 (다음 노드가 있음)
            # Interrupt 정보 추출
            interrupts = state.tasks
            interrupt_info = None

            if interrupts:
                # 첫 번째 interrupt 정보 사용
                interrupt_task = interrupts[0]
                interrupt_info = interrupt_task.interrupts[0] if interrupt_task.interrupts else None

            return ChatResponse(
                message="🔔 사용자 승인이 필요합니다.",
                conversation_id=conversation_id,
                requires_approval=True,
                approval_request={
                    "type": "trade_approval",
                    "thread_id": conversation_id,
                    "pending_node": state.next[0] if state.next else None,
                    "interrupt_data": interrupt_info.value if interrupt_info else {},
                    "message": "매매 주문을 승인하시겠습니까?"
                },
                metadata={
                    "interrupted": True,
                    "automation_level": request.automation_level,
                }
            )

        # No interrupt - 정상 완료
        data = result.get("final_response", {})

        # Get summary and details
        summary = data.get("summary", "분석 완료")
        details = data.get("details", {})

        # Build detailed message
        message_parts = [f"📊 분석 결과\n\n{summary}\n"]

        # Add details if available
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
            message_parts.append(
                f"\n⚠️ **리스크**\n"
                f"  - 수준: {risk.get('risk_level', 'N/A')}\n"
                f"  - 경고: {', '.join(risk.get('warnings', []))}"
            )

        # 매매 실행 결과 포함
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
            # 의도에 따라 적절한 타입 설정
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

        return ChatResponse(
            message=message,
            conversation_id=conversation_id,
            requires_approval=hitl_required,
            approval_request=approval_request,
            metadata={
                "intent": data.get("intent"),
                "agents_called": data.get("agents_called", []),
                "automation_level": request.automation_level,
                "langgraph_enabled": True,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


@router.get("/history/{conversation_id}")
async def get_chat_history(conversation_id: str):
    """Get chat history for a conversation"""
    # TODO: Implement chat history retrieval
    return {
        "conversation_id": conversation_id,
        "messages": [],
        "created_at": None,
    }


@router.delete("/history/{conversation_id}")
async def delete_chat_history(conversation_id: str):
    """Delete chat history"""
    # TODO: Implement chat history deletion
    return {"status": "deleted", "conversation_id": conversation_id}


# ==================== Approval Endpoint ====================

class ApprovalRequest(BaseModel):
    """Approval request schema"""
    thread_id: str = Field(description="대화 스레드 ID")
    decision: str = Field(description="승인 결정: approved, rejected, modified")
    automation_level: int = Field(default=2, ge=1, le=3)
    modifications: Optional[dict] = None
    user_notes: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Approval response schema"""
    status: str
    message: str
    conversation_id: str
    result: Optional[dict] = None


@router.post("/approve", response_model=ApprovalResponse)
async def approve_action(approval: ApprovalRequest):
    """
    승인/거부 처리 엔드포인트

    Flow:
    1. thread_id로 중단된 그래프 상태 조회
    2. 승인 여부에 따라 Command(resume=...) 전달
    3. 그래프 재개 및 결과 반환
    """
    try:
        # Build graph
        app = build_graph(automation_level=approval.automation_level)

        # Config
        config = {
            "configurable": {
                "thread_id": approval.thread_id,
            }
        }

        if approval.decision == "approved":
            # 승인 - 그래프 재개
            resume_value = {
                "approved": True,
                "user_id": "user_001",  # TODO: 실제 사용자 ID
                "notes": approval.user_notes
            }

            # Command로 재개
            result = await app.ainvoke(Command(resume=resume_value), config=config)

            # 최종 응답 추출
            final_response = result.get("final_response", {})

            return ApprovalResponse(
                status="approved",
                message="승인 완료 - 매매가 실행되었습니다.",
                conversation_id=approval.thread_id,
                result=final_response
            )

        elif approval.decision == "rejected":
            # 거부 - 그래프 상태 업데이트 후 종료
            await app.aupdate_state(
                config,
                {
                    "final_response": {
                        "summary": "사용자가 거부함",
                        "cancelled": True,
                        "reason": approval.user_notes or "User rejected"
                    }
                }
            )

            return ApprovalResponse(
                status="rejected",
                message="승인 거부 - 매매가 취소되었습니다.",
                conversation_id=approval.thread_id,
                result={"cancelled": True}
            )

        elif approval.decision == "modified":
            # 수정 후 승인
            resume_value = {
                "approved": True,
                "user_id": "user_001",
                "modifications": approval.modifications,
                "notes": approval.user_notes
            }

            result = await app.ainvoke(Command(resume=resume_value), config=config)
            final_response = result.get("final_response", {})

            return ApprovalResponse(
                status="modified",
                message="수정 후 승인 - 매매가 실행되었습니다.",
                conversation_id=approval.thread_id,
                result=final_response
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid decision: {approval.decision}"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Approval processing error: {str(e)}"
        )