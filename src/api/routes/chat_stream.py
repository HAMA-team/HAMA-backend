"""
채팅 스트리밍 API (Server-Sent Events)

실시간으로 AI 사고 과정과 답변을 스트리밍
"""
import json
import logging
import uuid
from typing import Optional, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.agents.research.react_agent import create_research_agent
from src.agents.thinking_trace import collect_thinking_trace
from src.agents.aggregator import personalize_response
from src.agents.router import route_query
from src.services.user_profile_service import user_profile_service
from src.models.database import get_db_context

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatStreamRequest(BaseModel):
    """채팅 스트리밍 요청"""
    message: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    automation_level: int = Field(default=2, ge=1, le=3)


async def generate_chat_stream(
    message: str,
    user_id: str,
    conversation_id: str,
    automation_level: int
) -> AsyncGenerator[str, None]:
    """
    채팅 응답을 SSE 형식으로 스트리밍

    Args:
        message: 사용자 메시지
        user_id: 사용자 ID
        conversation_id: 대화 ID
        automation_level: 자동화 레벨

    Yields:
        SSE 형식 문자열
            event: thought | tool_call | tool_result | answer | error | done
            data: JSON 페이로드
    """
    logger.info(f"📡 [ChatStream] 시작: {message[:50]}...")

    try:
        # 1. 사용자 프로파일 로드
        async with get_db_context() as db:
            user_profile = await user_profile_service.get_user_profile(user_id, db)

        yield f"event: user_profile\ndata: {json.dumps({'profile': user_profile})}\n\n"

        # 2. Router 판단
        routing_decision = await route_query(
            query=message,
            user_profile=user_profile,
            conversation_history=[]
        )

        yield f"event: routing\ndata: {json.dumps(routing_decision.dict())}\n\n"

        # 3. Agent 생성
        agent = create_research_agent(
            depth_level=routing_decision.depth_level,
            user_profile=user_profile
        )

        # 4. 입력 구성
        from langchain_core.messages import HumanMessage

        input_state = {
            "messages": [HumanMessage(content=message)]
        }

        config = {
            "configurable": {
                "thread_id": conversation_id,
                "user_id": user_id
            }
        }

        # 5. Thinking Trace 스트리밍
        agent_result = None

        async for event in collect_thinking_trace(agent, input_state, config):
            event_type = event.get("type")
            content = event.get("content")

            # SSE 형식으로 전송
            if event_type == "thought":
                yield f"event: thought\ndata: {json.dumps({'content': content})}\n\n"

            elif event_type == "tool_call":
                yield f"event: tool_call\ndata: {json.dumps(content)}\n\n"

            elif event_type == "tool_result":
                yield f"event: tool_result\ndata: {json.dumps(content)}\n\n"

            elif event_type == "answer":
                # 최종 답변 (아직 개인화 전)
                agent_result = content

            elif event_type == "error":
                yield f"event: error\ndata: {json.dumps({'error': content})}\n\n"

        # 6. 답변 개인화
        if agent_result:
            personalized = await personalize_response(
                agent_results={"research": agent_result},
                user_profile=user_profile,
                routing_decision=routing_decision.dict()
            )

            final_response = personalized.get("response")

            yield f"event: answer\ndata: {json.dumps({'content': final_response})}\n\n"

        # 7. 완료
        yield f"event: done\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"

        logger.info("✅ [ChatStream] 완료")

    except Exception as e:
        logger.error(f"❌ [ChatStream] 에러: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


@router.post("/stream")
async def chat_stream(request: ChatStreamRequest):
    """
    채팅 스트리밍 API

    실시간으로 AI 사고 과정과 답변을 전송합니다.

    **응답 형식: Server-Sent Events (SSE)**

    **이벤트 타입:**
    - `user_profile`: 사용자 프로파일 로드 완료
    - `routing`: Router 판단 완료
    - `thought`: LLM 사고 과정
    - `tool_call`: 도구 호출 시작
    - `tool_result`: 도구 실행 결과
    - `answer`: 최종 답변 (개인화 완료)
    - `error`: 에러 발생
    - `done`: 스트리밍 완료

    **Frontend 사용 예시 (JavaScript):**
    ```javascript
    const eventSource = new EventSource('/api/chat/stream');

    eventSource.addEventListener('thought', (event) => {
        const data = JSON.parse(event.data);
        console.log('Thinking:', data.content);
    });

    eventSource.addEventListener('tool_call', (event) => {
        const data = JSON.parse(event.data);
        console.log('Tool Call:', data.tool, data.input);
    });

    eventSource.addEventListener('answer', (event) => {
        const data = JSON.parse(event.data);
        console.log('Answer:', data.content);
    });

    eventSource.addEventListener('done', (event) => {
        eventSource.close();
    });
    ```
    """
    user_id = request.user_id or str(uuid.uuid4())
    conversation_id = request.conversation_id or str(uuid.uuid4())

    return StreamingResponse(
        generate_chat_stream(
            message=request.message,
            user_id=user_id,
            conversation_id=conversation_id,
            automation_level=request.automation_level
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx 버퍼링 비활성화
        }
    )
