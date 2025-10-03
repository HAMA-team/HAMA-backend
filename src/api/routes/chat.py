"""
Chat API endpoints - Main interface for user interaction
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid

from src.agents.graph_master import run_graph

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
    """
    try:
        # Generate conversation ID if not provided
        conversation_id = request.conversation_id or str(uuid.uuid4())

        # Run LangGraph
        result = await run_graph(
            query=request.message,
            automation_level=request.automation_level,
            request_id=conversation_id
        )

        # Extract data
        data = result or {}

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