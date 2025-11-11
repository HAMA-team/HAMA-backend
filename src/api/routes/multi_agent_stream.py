from __future__ import annotations

"""
멀티 에이전트 실행을 실시간으로 스트리밍
Master Agent → 서브 에이전트들의 협업 과정을 시각화
"""
import json
import logging
import uuid
from typing import AsyncGenerator, Optional, List, Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from src.agents.graph_master import build_graph
from src.services.user_profile_service import user_profile_service
from src.services import chat_history_service
from src.services.hitl_interrupt_service import handle_hitl_interrupt
from src.models.database import get_db_context
from src.utils.hitl_compat import automation_level_to_hitl_config
from src.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class MultiAgentStreamRequest(BaseModel):
    """멀티 에이전트 스트리밍 요청"""
    message: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    automation_level: int = Field(default=2, ge=1, le=3)
    stream_thinking: bool = Field(default=True, description="LLM 사고 과정 실시간 스트리밍 활성화 (ChatGPT식)")


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _event_agent_name(event: dict) -> Optional[str]:
    metadata = event.get("metadata") or {}
    node = metadata.get("langgraph_node")
    if node and node != "LangGraph":
        return node
    name = event.get("name")
    if name and name != "LangGraph":
        return name
    return None


def _normalize_output(raw_output: Any) -> dict:
    """LangGraph 이벤트 output을 dict로 정규화해 다운스트림 로직을 보호."""
    if raw_output is None:
        return {}
    if isinstance(raw_output, dict):
        return raw_output
    if hasattr(raw_output, "model_dump"):
        try:
            return raw_output.model_dump()
        except Exception:
            pass
    if hasattr(raw_output, "dict"):
        try:
            return raw_output.dict()
        except Exception:
            pass
    content = getattr(raw_output, "content", None)
    if isinstance(content, dict):
        return content
    if content is not None:
        return {"message": content}
    return {}


def _event_to_sse_chunks(event: dict, stream_thinking: bool) -> List[str]:
    chunks: List[str] = []
    event_type = event.get("event")
    agent = _event_agent_name(event)

    if event_type == "on_chain_start" and agent:
        if agent == "routing":
            chunks.append(_sse("master_routing", {"status": "analyzing"}))
        elif agent == "worker_dispatch":
            chunks.append(_sse("worker_start", {"agent": "worker"}))
        else:
            chunks.append(_sse("agent_start", {"agent": agent}))

    elif event_type == "on_chain_end" and agent:
        output = _normalize_output(event.get("data", {}).get("output"))
        if agent == "routing":
            chunks.append(
                _sse(
                    "master_routing",
                    {
                        "agents": output.get("agents_to_call", []),
                        "depth_level": output.get("depth_level"),
                        "worker_action": output.get("worker_action"),
                    },
                )
            )
        elif agent == "worker_dispatch":
            chunks.append(
                _sse(
                    "worker_complete",
                    {"result": output.get("final_response", {}), "agent": "worker"},
                )
            )
        elif agent == "clarification":
            chunks.append(
                _sse(
                    "master_complete",
                    {"message": output.get("final_response", {}).get("message")},
                )
            )
        else:
            chunks.append(_sse("agent_complete", {"agent": agent}))

    elif event_type == "on_chat_model_start" and agent:
        model = event.get("name") or event.get("data", {}).get("name")
        chunks.append(_sse("agent_llm_start", {"agent": agent, "model": model}))

    elif event_type == "on_chat_model_stream" and stream_thinking:
        chunk = event.get("data", {}).get("chunk")
        if chunk:
            content = chunk.get("content") if isinstance(chunk, dict) else str(chunk)
            if content:
                chunks.append(_sse("agent_thinking", {"agent": agent, "content": content}))

    elif event_type == "on_chat_model_end" and agent:
        chunks.append(_sse("agent_llm_end", {"agent": agent}))

    return chunks


def _extract_final_message(state_values: dict) -> str:
    final_response = state_values.get("final_response") or {}
    if isinstance(final_response, dict):
        message = final_response.get("message")
        if isinstance(message, str) and message.strip():
            return message

    messages = state_values.get("messages") or []
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
            if text.strip():
                return text

    return "분석이 완료되었습니다."


async def stream_multi_agent_execution(
    message: str,
    user_id: str,
    conversation_id: str,
    automation_level: int,
    stream_thinking: bool = True
) -> AsyncGenerator[str, None]:
    """LangGraph Supervisor 실행을 SSE로 래핑"""
    try:
        yield _sse("master_start", {"message": "분석을 시작합니다..."})

        with get_db_context() as db:
            user_profile = user_profile_service.get_user_profile(user_id, db)

        yield _sse("user_profile", {"profile_loaded": True})

        conversation_uuid = uuid.UUID(conversation_id)
        demo_user_uuid = settings.demo_user_uuid
        hitl_config = automation_level_to_hitl_config(automation_level)

        await chat_history_service.upsert_session(
            conversation_id=conversation_uuid,
            user_id=demo_user_uuid,
            automation_level=automation_level,
            metadata={"hitl_preset": hitl_config.preset},
        )
        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="user",
            content=message,
        )

        conversation_history: list[dict] = []
        try:
            history_data = await chat_history_service.get_history(conversation_id=conversation_uuid, limit=10)
            if history_data and "messages" in history_data:
                messages = history_data["messages"][:-1]
                conversation_history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in messages[-6:]
                ]
        except Exception as history_error:  # pragma: no cover - 히스토리 조회 실패는 치명적이지 않음
            logger.warning("⚠️ [MultiAgentStream] 대화 히스토리 로드 실패: %s", history_error)

        app = build_graph(automation_level=automation_level)
        config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}
        configured_app = app.with_config(config)

        initial_state = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id or str(demo_user_uuid),
            "conversation_id": conversation_id,
            "hitl_config": hitl_config.model_dump(),
            "automation_level": automation_level,
            "user_profile": user_profile,
            "intent": None,
            "query": message,
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
            "conversation_history": conversation_history,
        }

        async for event in configured_app.astream_events(initial_state, version="v2"):
            for chunk in _event_to_sse_chunks(event, stream_thinking):
                yield chunk

        state = await configured_app.aget_state()
        pending_nodes = getattr(state, "next", None)

        if pending_nodes:
            logger.info("⚠️ [MultiAgentStream] Interrupt 감지: next=%s", pending_nodes)
            with get_db_context() as db:
                hitl_result = await handle_hitl_interrupt(
                    state=state,
                    conversation_uuid=conversation_uuid,
                    conversation_id=conversation_id,
                    user_id=demo_user_uuid,
                    db=db,
                    automation_level=automation_level,
                    hitl_config=hitl_config,
                )

            if hitl_result:
                yield _sse(
                    "hitl_interrupt",
                    {
                        "pending_nodes": pending_nodes,
                        "approval_request": hitl_result["approval_request"],
                        "message": hitl_result["message"],
                    },
                )
                yield _sse(
                    "master_complete",
                    {"message": hitl_result["message"], "conversation_id": conversation_id},
                )
                yield _sse("done", {"conversation_id": conversation_id})
                return
            else:  # pragma: no cover - 예외적인 실패
                logger.warning("⚠️ [MultiAgentStream] HITL 헬퍼 실행 실패 - 기본 이벤트만 전송")
                yield _sse(
                    "hitl_interrupt",
                    {
                        "pending_nodes": pending_nodes,
                        "tasks": [getattr(task, "__dict__", str(task)) for task in getattr(state, "tasks", [])],
                    },
                )

        values = getattr(state, "values", {})
        final_message = _extract_final_message(values)

        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="assistant",
            content=final_message,
            metadata={"source": "graph"},
        )

        yield _sse("master_complete", {"message": final_message, "conversation_id": conversation_id})
        yield _sse("done", {"conversation_id": conversation_id})

    except Exception as exc:  # pragma: no cover - SSE 경로 오류 처리
        logger.exception("❌ [MultiAgentStream] 실행 실패: %s", exc)
        error_message = f"죄송합니다. 그래프 실행 중 오류가 발생했습니다: {exc}"
        yield _sse("error", {"error": str(exc), "message": error_message})
        yield _sse("done", {"conversation_id": conversation_id})


@router.post("/multi-stream")
async def multi_agent_stream(request: MultiAgentStreamRequest):
    """
    멀티 에이전트 실행을 실시간으로 스트리밍

    **Master Agent가 여러 서브 에이전트를 조율하는 과정을 시각화**

    **응답 형식: Server-Sent Events (SSE)**

    **이벤트 타입:**
    - `master_start`: Master Agent 시작
    - `master_routing`: 어떤 에이전트들을 호출할지 결정
    - `agent_start`: 서브 에이전트 시작
    - `agent_node`: 에이전트 내부 노드 실행 상태
    - `agent_llm_start`: LLM 호출 시작
    - `agent_llm_end`: LLM 호출 완료
    - `agent_complete`: 서브 에이전트 완료
    - `master_aggregating`: Master가 결과 집계 중
    - `master_complete`: 전체 완료
    - `error`: 에러 발생
    - `done`: 스트리밍 종료

    **Frontend 사용 예시 (React):**
    ```javascript
    const [agentStatus, setAgentStatus] = useState({});

    const eventSource = new EventSource('/api/v1/chat/multi-stream', {
        method: 'POST',
        body: JSON.stringify({
            message: '삼성전자 분석해줘',
            user_id: 'user123'
        })
    });

    eventSource.addEventListener('master_routing', (event) => {
        const data = JSON.parse(event.data);
        console.log('호출할 에이전트:', data.agents);
        // UI에 표시: Research, Strategy, Risk 에이전트 활성화
    });

    eventSource.addEventListener('agent_start', (event) => {
        const data = JSON.parse(event.data);
        setAgentStatus(prev => ({
            ...prev,
            [data.agent]: 'running'
        }));
        // UI: Research Agent 카드에 "실행 중" 표시
    });

    eventSource.addEventListener('agent_node', (event) => {
        const data = JSON.parse(event.data);
        console.log(`${data.agent} - ${data.node}: ${data.status}`);
        // UI: "데이터 수집 중...", "Bull 분석 중..." 등 표시
    });

    eventSource.addEventListener('agent_complete', (event) => {
        const data = JSON.parse(event.data);
        setAgentStatus(prev => ({
            ...prev,
            [data.agent]: 'complete'
        }));
        console.log('결과:', data.result);
        // UI: Research Agent 카드에 "완료" + 결과 요약 표시
    });

    eventSource.addEventListener('master_complete', (event) => {
        const data = JSON.parse(event.data);
        console.log('최종 답변:', data.message);
        // UI: 최종 답변 표시
    });

    eventSource.addEventListener('done', (event) => {
        eventSource.close();
    });
    ```

    **Frontend UI 예시:**
    ```
    [Master Agent]
    ├─ 📊 Research Agent ✅
    │   ├─ planner ✅
    │   ├─ data_worker ✅
    │   ├─ bull_worker ✅
    │   ├─ bear_worker ✅
    │   ├─ insight_worker ✅
    │   └─ synthesis ✅
    │   결과: SELL, 목표가 90,000원
    │
    ├─ 🎯 Strategy Agent ✅
    │   └─ 전략: MOMENTUM
    │
    └─ ⚠️ Risk Agent ✅
        └─ 리스크: MEDIUM

    최종 답변: 현재 삼성전자는 SELL 추천입니다...
    ```
    """
    user_id = request.user_id or str(uuid.uuid4())
    conversation_id = request.conversation_id or str(uuid.uuid4())

    return StreamingResponse(
        stream_multi_agent_execution(
            message=request.message,
            user_id=user_id,
            conversation_id=conversation_id,
            automation_level=request.automation_level,
            stream_thinking=request.stream_thinking
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/sessions")
async def get_chat_sessions(
    limit: int = 20,
    offset: int = 0,
):
    """
    대화 세션 목록 조회

    Args:
        limit: 조회할 세션 수 (기본값: 20)
        offset: 건너뛸 세션 수 (기본값: 0)

    Returns:
        {
            "sessions": [
                {
                    "conversation_id": "uuid",
                    "title": "첫 메시지 내용",
                    "last_message": "마지막 메시지",
                    "created_at": "2025-01-09T10:00:00",
                    "updated_at": "2025-01-09T10:30:00",
                    "message_count": 10
                }
            ],
            "total": 100,
            "limit": 20,
            "offset": 0
        }
    """
    try:
        # Demo 사용자 UUID
        demo_user_uuid = settings.demo_user_uuid

        # 세션 목록 조회 (전체 조회 후 offset 적용)
        all_sessions = await chat_history_service.list_sessions(
            user_id=demo_user_uuid,
            limit=limit + offset  # offset만큼 더 가져옴
        )

        # offset 적용하여 슬라이싱
        sessions_slice = all_sessions[offset:offset + limit]

        # API 응답 형식으로 포맷팅
        formatted_sessions = []
        for session_data in sessions_slice:
            first_msg = session_data.get("first_user_message")
            last_msg = session_data.get("last_message")
            chat_session = session_data.get("session")

            formatted_sessions.append({
                "conversation_id": str(session_data["conversation_id"]),
                "title": first_msg.content[:50] if first_msg and first_msg.content else "새 대화",
                "last_message": last_msg.content[:100] if last_msg and last_msg.content else "",
                "created_at": chat_session.created_at.isoformat() if chat_session and hasattr(chat_session, "created_at") else None,
                "updated_at": chat_session.last_message_at.isoformat() if chat_session and hasattr(chat_session, "last_message_at") and chat_session.last_message_at else None,
                "message_count": session_data.get("message_count", 0)
            })

        return {
            "sessions": formatted_sessions,
            "total": len(all_sessions),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"❌ [ChatSessions] 세션 목록 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        return {
            "sessions": [],
            "total": 0,
            "limit": limit,
            "offset": offset
        }


@router.get("/sessions/{conversation_id}")
async def get_chat_session(conversation_id: str):
    """
    특정 대화 세션의 메시지 조회

    Args:
        conversation_id: 대화 ID (UUID)

    Returns:
        {
            "conversation_id": "uuid",
            "messages": [
                {
                    "role": "user",
                    "content": "안녕하세요",
                    "created_at": "2025-01-09T10:00:00"
                },
                {
                    "role": "assistant",
                    "content": "안녕하세요! 무엇을 도와드릴까요?",
                    "created_at": "2025-01-09T10:00:05"
                }
            ]
        }
    """
    try:
        conversation_uuid = uuid.UUID(conversation_id)
        history = await chat_history_service.get_history(
            conversation_id=conversation_uuid,
            limit=100  # 최근 100개 메시지
        )

        if not history:
            return {
                "conversation_id": conversation_id,
                "messages": []
            }

        # 메시지 포맷팅
        messages = []
        for msg in history.get("messages", []):
            messages.append({
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if hasattr(msg, "created_at") else None
            })

        return {
            "conversation_id": conversation_id,
            "messages": messages
        }

    except ValueError:
        logger.error(f"❌ [ChatSession] 잘못된 UUID 형식: {conversation_id}")
        return {
            "conversation_id": conversation_id,
            "messages": [],
            "error": "Invalid conversation ID format"
        }
    except Exception as e:
        logger.error(f"❌ [ChatSession] 세션 조회 실패: {e}")
        return {
            "conversation_id": conversation_id,
            "messages": [],
            "error": str(e)
        }


@router.delete("/sessions/{conversation_id}")
async def delete_chat_session(conversation_id: str):
    """
    대화 세션 삭제

    Args:
        conversation_id: 대화 ID (UUID)

    Returns:
        {
            "success": true,
            "conversation_id": "uuid",
            "message": "세션이 삭제되었습니다."
        }
    """
    try:
        conversation_uuid = uuid.UUID(conversation_id)

        # 세션 삭제 (delete_history 사용)
        await chat_history_service.delete_history(conversation_id=conversation_uuid)

        return {
            "success": True,
            "conversation_id": conversation_id,
            "message": "세션이 삭제되었습니다."
        }

    except ValueError:
        logger.error(f"❌ [DeleteSession] 잘못된 UUID 형식: {conversation_id}")
        return {
            "success": False,
            "conversation_id": conversation_id,
            "error": "Invalid conversation ID format"
        }
    except Exception as e:
        logger.error(f"❌ [DeleteSession] 세션 삭제 실패: {e}")
        return {
            "success": False,
            "conversation_id": conversation_id,
            "error": str(e)
        }
