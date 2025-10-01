"""
Chat API endpoints - Main interface for user interaction
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()


class ChatMessage(BaseModel):
    """Chat message schema"""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Chat request schema"""
    message: str
    conversation_id: Optional[str] = None
    automation_level: int = 2  # 1: Pilot, 2: Copilot, 3: Advisor


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
    # TODO: Implement actual master agent logic
    # For now, return mock response

    mock_response = {
        "message": f"[MOCK] Received: {request.message}\n\n"
                   f"Automation Level: {request.automation_level}\n"
                   f"TODO: Master Agent will process this request.",
        "conversation_id": request.conversation_id or "conv_mock_001",
        "requires_approval": False,
        "metadata": {
            "agents_called": ["mock"],
            "processing_time_ms": 0,
        }
    }

    return ChatResponse(**mock_response)


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