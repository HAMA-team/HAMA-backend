from __future__ import annotations

"""
멀티 에이전트 실행을 실시간으로 스트리밍
Master Agent → 서브 에이전트들의 협업 과정을 시각화
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional, List, Any, Dict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from src.services.user_profile_service import user_profile_service
from src.services import chat_history_service
from src.services.hitl_interrupt_service import handle_hitl_interrupt
from src.models.database import get_db_context
from src.schemas.hitl_config import HITLConfig
from src.schemas.reasoning import (
    ReasoningActor,
    ReasoningEvent,
    ReasoningPhase,
    ReasoningStatus,
)
from src.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

HITL_APPROVAL_TIMEOUT_SECONDS = 300
HITL_APPROVAL_POLL_INTERVAL_SECONDS = 1.0


class MultiAgentStreamRequest(BaseModel):
    """멀티 에이전트 스트리밍 요청"""
    message: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    hitl_config: HITLConfig = Field(default_factory=HITLConfig)
    intervention_required: bool = Field(
        default=True,
        description="분석/전략 단계부터 HITL 필요 여부 (기본적으로 분석도 승인을 기다림)",
    )
    stream_thinking: bool = Field(default=True, description="LLM 사고 과정 실시간 스트리밍 활성화 (ChatGPT식)")


def _serialize_for_json(data: Any) -> Any:
    """
    LangChain 객체를 JSON 직렬화 가능한 형태로 변환

    ToolMessage, AIMessage 등 LangChain 객체를 재귀적으로 딕셔너리로 변환합니다.
    """
    if data is None:
        return None

    # Pydantic 모델 (BaseMessage 등)
    if hasattr(data, "model_dump"):
        try:
            return data.model_dump()
        except Exception:
            pass

    if hasattr(data, "dict"):
        try:
            return data.dict()
        except Exception:
            pass

    # 리스트 처리 (재귀적으로)
    if isinstance(data, list):
        return [_serialize_for_json(item) for item in data]

    # 딕셔너리 처리 (재귀적으로)
    if isinstance(data, dict):
        return {key: _serialize_for_json(value) for key, value in data.items()}

    # 기본 타입 (str, int, float, bool, None)
    if isinstance(data, (str, int, float, bool, type(None))):
        return data

    # 나머지는 문자열로 변환 (fallback)
    try:
        return str(data)
    except Exception:
        return None


def _normalize_metadata(metadata: Any) -> Dict[str, Any]:
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str):
        try:
            decoded = json.loads(metadata)
            if isinstance(decoded, dict):
                return decoded
        except json.JSONDecodeError:
            pass
    return {}


async def _await_approved_response(
    conversation_uuid: uuid.UUID,
    interrupt_time: datetime,
    timeout_seconds: float = HITL_APPROVAL_TIMEOUT_SECONDS,
    poll_interval: float = HITL_APPROVAL_POLL_INTERVAL_SECONDS,
) -> tuple[str, Dict[str, Any]] | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        history = await chat_history_service.get_history(
            conversation_id=conversation_uuid, limit=8
        )
        messages = history.get("messages") or []
        for message in reversed(messages):
            if getattr(message, "role", None) != "assistant":
                continue
            created_at = getattr(message, "created_at", None)
            if created_at and created_at <= interrupt_time:
                continue
            metadata = _normalize_metadata(getattr(message, "message_metadata", None))
            if metadata.get("decision"):
                text = getattr(message, "content", "") or ""
                if text.strip():
                    return text, metadata
        await asyncio.sleep(poll_interval)
    return None


def _sse(event: str, payload: dict) -> str:
    # payload를 JSON 직렬화 가능하도록 변환
    serializable_payload = _serialize_for_json(payload)
    return f"event: {event}\ndata: {json.dumps(serializable_payload, ensure_ascii=False)}\n\n"


def _event_agent_name(event: dict) -> Optional[str]:
    """
    LangGraph 이벤트에서 Agent 이름을 추출합니다.

    SubGraph 실행 시 부모 Agent 이름을 추출하는 로직 포함.
    """
    metadata = event.get("metadata") or {}

    # 1. langgraph_triggers에서 부모 노드 추적 (SubGraph 추적용)
    triggers = metadata.get("langgraph_triggers") or []
    if triggers:
        # triggers 예시: ["supervisor_node", "Research_Agent"]
        # 마지막 trigger가 SubGraph 이름일 가능성 높음
        for trigger in reversed(triggers):
            # "_agent" 또는 "_subgraph"가 포함되어 있으면 SubGraph로 간주
            if "_agent" in trigger.lower() or "_subgraph" in trigger.lower():
                return trigger
            # "supervisor", "master" 같은 키워드 제외
            if trigger.lower() not in ["supervisor", "master", "langgraph", "supervisor_node"]:
                return trigger

    # 2. langgraph_node에서 SubGraph 이름 추출
    node = metadata.get("langgraph_node")
    if node and node != "LangGraph":
        # 노드 이름에 "__"가 있으면 SubGraph 이름 추출
        # 예: "Research_Agent__planner" → "Research_Agent"
        if "__" in node:
            subgraph_name = node.split("__")[0]
            return subgraph_name
        return node

    # 3. event name 확인 (fallback)
    name = event.get("name")
    if name and name != "LangGraph":
        return name

    return None


def _extract_lineage(metadata: Dict[str, Any], agent: Optional[str]) -> List[str]:
    lineage: List[str] = []
    triggers = metadata.get("langgraph_triggers")
    if isinstance(triggers, list):
        lineage = [str(trigger) for trigger in triggers if trigger]
    node = metadata.get("langgraph_node")
    if node and node not in lineage:
        lineage.append(str(node))
    if agent and agent not in lineage:
        lineage.append(agent)
    return lineage


def _infer_phase(event_label: str, node: Optional[str], agent: Optional[str]) -> ReasoningPhase:
    label = (event_label or "").lower()
    node_lower = (node or "").lower()
    agent_lower = (agent or "").lower() if agent else ""

    direct_mapping = {
        "master_start": ReasoningPhase.SUPERVISION,
        "master_routing": ReasoningPhase.ROUTING,
        "master_complete": ReasoningPhase.FINALIZATION,
        "worker_start": ReasoningPhase.AGENT_EXECUTION,
        "worker_complete": ReasoningPhase.FINALIZATION,
        "hitl_interrupt": ReasoningPhase.HITL,
        "done": ReasoningPhase.FINALIZATION,
        "error": ReasoningPhase.SYSTEM,
        "user_profile": ReasoningPhase.SYSTEM,
    }
    if label in direct_mapping:
        return direct_mapping[label]
    if label.startswith("agent_llm") or label == "agent_thinking":
        return ReasoningPhase.LLM
    if label.startswith("tools_"):
        return ReasoningPhase.TOOL

    if node_lower:
        if any(keyword in node_lower for keyword in ("plan", "route", "clarify", "decision")):
            return ReasoningPhase.PLANNING
        if any(keyword in node_lower for keyword in ("data", "fetch", "collect", "search", "crawl", "ingest")):
            return ReasoningPhase.DATA_COLLECTION
    if agent_lower and "supervisor" in agent_lower:
        return ReasoningPhase.SUPERVISION
    return ReasoningPhase.AGENT_EXECUTION


def _infer_actor(event_label: str) -> ReasoningActor:
    label = (event_label or "").lower()
    if label.startswith("master") or label == "hitl_interrupt":
        return ReasoningActor.SUPERVISOR
    if label.startswith("tools_"):
        return ReasoningActor.TOOL
    if label.startswith("agent_llm") or label == "agent_thinking":
        return ReasoningActor.LLM
    if label in {"error", "done", "user_profile"}:
        return ReasoningActor.SYSTEM
    return ReasoningActor.AGENT


class ReasoningEventBuilder:
    """Utility to enrich SSE payloads with normalized reasoning metadata."""

    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self._sequence = 0

    def _sequence_id(self) -> str:
        self._sequence += 1
        return f"{self.conversation_id}:{self._sequence:05d}"

    def _build_metadata(self, metadata: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        if metadata:
            if metadata.get("langgraph_node"):
                result["langgraph_node"] = metadata["langgraph_node"]
            if metadata.get("langgraph_step") is not None:
                result["langgraph_step"] = metadata.get("langgraph_step")
            if metadata.get("langgraph_triggers"):
                result["langgraph_triggers"] = metadata.get("langgraph_triggers")
            if metadata.get("langgraph_checkpoint_id"):
                result["langgraph_checkpoint_id"] = metadata.get("langgraph_checkpoint_id")
        if extra:
            result.update(extra)
        return result

    def attach(
        self,
        event_label: str,
        payload: Dict[str, Any],
        *,
        metadata: Optional[Dict[str, Any]],
        agent: Optional[str],
        node: Optional[str],
        status: ReasoningStatus,
        message: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata = metadata or {}
        lineage = _extract_lineage(metadata, agent)
        reasoning_event = ReasoningEvent(
            event_id=self._sequence_id(),
            sequence_index=self._sequence,
            conversation_id=self.conversation_id,
            event_label=event_label,
            phase=_infer_phase(event_label, node, agent),
            status=status,
            actor=_infer_actor(event_label),
            agent=agent,
            node=node,
            step=metadata.get("langgraph_step"),
            depth=max(len(lineage) - 1, 0),
            lineage=lineage,
            message=message,
            metadata=self._build_metadata(metadata, extra_metadata),
        )
        payload["reasoning_event"] = reasoning_event.model_dump()
        return payload

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


def _event_to_sse_chunks(
    event: dict,
    stream_thinking: bool,
    reasoning_builder: ReasoningEventBuilder,
) -> List[str]:
    chunks: List[str] = []
    event_type = event.get("event")
    agent = _event_agent_name(event)

    # 메타데이터 추출
    metadata = event.get("metadata") or {}
    node_name = metadata.get("langgraph_node")
    step = metadata.get("langgraph_step")

    # 툴/체인 이름
    name = event.get("name")

    # ==================== Chain 이벤트 ====================
    if event_type == "on_chain_start" and agent:
        if agent == "routing":
            payload = reasoning_builder.attach(
                "master_routing",
                {"status": "analyzing"},
                metadata=metadata,
                agent="supervisor",
                node=node_name,
                status=ReasoningStatus.INFO,
                message="다음 에이전트를 라우팅 중입니다.",
            )
            chunks.append(_sse("master_routing", payload))
        elif agent == "worker_dispatch":
            payload = reasoning_builder.attach(
                "worker_start",
                {"agent": "worker"},
                metadata=metadata,
                agent="worker_dispatch",
                node=node_name,
                status=ReasoningStatus.START,
                message="워커 에이전트 실행 시작",
            )
            chunks.append(_sse("worker_start", payload))
        else:
            payload = reasoning_builder.attach(
                "agent_start",
                {"agent": agent, "node": node_name, "step": step},
                metadata=metadata,
                agent=agent,
                node=node_name,
                status=ReasoningStatus.START,
                message=f"{agent} 실행 시작",
            )
            chunks.append(_sse("agent_start", payload))

    elif event_type == "on_chain_end" and agent:
        output = _normalize_output(event.get("data", {}).get("output"))
        if agent == "routing":
            payload = reasoning_builder.attach(
                "master_routing",
                {
                    "agents": output.get("agents_to_call", []),
                    "depth_level": output.get("depth_level"),
                    "worker_action": output.get("worker_action"),
                },
                metadata=metadata,
                agent="supervisor",
                node=node_name,
                status=ReasoningStatus.COMPLETE,
                message="에이전트 라우팅이 완료되었습니다.",
            )
            chunks.append(_sse("master_routing", payload))
        elif agent == "worker_dispatch":
            payload = reasoning_builder.attach(
                "worker_complete",
                {"result": output.get("final_response", {}), "agent": "worker"},
                metadata=metadata,
                agent="worker_dispatch",
                node=node_name,
                status=ReasoningStatus.COMPLETE,
                message="워커 에이전트 실행이 완료되었습니다.",
            )
            chunks.append(_sse("worker_complete", payload))
        elif agent == "clarification":
            payload = reasoning_builder.attach(
                "master_complete",
                {"message": output.get("final_response", {}).get("message")},
                metadata=metadata,
                agent="supervisor",
                node=node_name,
                status=ReasoningStatus.COMPLETE,
                message="사용자 확인 응답 생성 완료",
            )
            chunks.append(_sse("master_complete", payload))
        else:
            payload = reasoning_builder.attach(
                "agent_complete",
                {"agent": agent, "node": node_name, "step": step},
                metadata=metadata,
                agent=agent,
                node=node_name,
                status=ReasoningStatus.COMPLETE,
                message=f"{agent} 작업 완료",
            )
            chunks.append(_sse("agent_complete", payload))

    # ==================== LLM 이벤트 ====================
    elif event_type == "on_chat_model_start" and agent:
        model = event.get("name") or event.get("data", {}).get("name")
        payload = reasoning_builder.attach(
            "agent_llm_start",
            {"agent": agent, "node": node_name, "model": model},
            metadata=metadata,
            agent=agent,
            node=node_name,
            status=ReasoningStatus.START,
            message=f"{model or 'LLM'} 분석 시작",
            extra_metadata={"model": model},
        )
        chunks.append(_sse("agent_llm_start", payload))

    elif event_type == "on_chat_model_stream" and stream_thinking:
        chunk = event.get("data", {}).get("chunk")
        if chunk:
            content = chunk.get("content") if isinstance(chunk, dict) else str(chunk)
            if content:
                preview = content if len(content) <= 160 else f"{content[:160]}..."
                payload = reasoning_builder.attach(
                    "agent_thinking",
                    {"agent": agent, "node": node_name, "content": content},
                    metadata=metadata,
                    agent=agent,
                    node=node_name,
                    status=ReasoningStatus.IN_PROGRESS,
                    message=preview,
                )
                chunks.append(_sse("agent_thinking", payload))

    elif event_type == "on_chat_model_end" and agent:
        payload = reasoning_builder.attach(
            "agent_llm_end",
            {"agent": agent, "node": node_name},
            metadata=metadata,
            agent=agent,
            node=node_name,
            status=ReasoningStatus.COMPLETE,
            message="LLM 분석 완료",
        )
        chunks.append(_sse("agent_llm_end", payload))

    # ==================== 툴 이벤트 (새로 추가) ====================
    elif event_type == "on_tool_start":
        tool_name = name or "unknown_tool"
        input_data = event.get("data", {}).get("input")
        payload = reasoning_builder.attach(
            "tools_start",
            {"tool": tool_name, "agent": agent, "node": node_name, "input": input_data},
            metadata=metadata,
            agent=agent,
            node=node_name,
            status=ReasoningStatus.START,
            message=f"{tool_name} 툴 실행 시작",
            extra_metadata={"tool": tool_name},
        )
        chunks.append(_sse("tools_start", payload))

    elif event_type == "on_tool_end":
        tool_name = name or "unknown_tool"
        output_data = event.get("data", {}).get("output")

        # 툴 출력 데이터 요약 (너무 크면 프론트엔드 성능 저하)
        # output이 문자열이고 길면 앞부분만 전송
        output_summary = output_data
        if isinstance(output_data, str) and len(output_data) > 500:
            output_summary = output_data[:500] + "... (truncated)"
        elif isinstance(output_data, dict):
            # 딕셔너리는 그대로 전송 (직렬화는 _sse에서 처리)
            output_summary = output_data
        elif isinstance(output_data, list) and len(output_data) > 10:
            # 리스트가 너무 길면 첫 10개만
            output_summary = output_data[:10]

        payload = reasoning_builder.attach(
            "tools_complete",
            {
                "tool": tool_name,
                "agent": agent,
                "node": node_name,
                "status": "complete",
                "output": output_summary,
            },
            metadata=metadata,
            agent=agent,
            node=node_name,
            status=ReasoningStatus.COMPLETE,
            message=f"{tool_name} 툴 실행 완료",
            extra_metadata={"tool": tool_name},
        )
        chunks.append(_sse("tools_complete", payload))

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
    hitl_config: HITLConfig,
    intervention_required: bool,
    stream_thinking: bool = True
) -> AsyncGenerator[str, None]:
    """LangGraph Supervisor 실행을 SSE로 래핑"""
    reasoning_builder = ReasoningEventBuilder(conversation_id)
    try:
        yield _sse(
            "master_start",
            reasoning_builder.attach(
                "master_start",
                {"message": "분석을 시작합니다..."},
                metadata={},
                agent="supervisor",
                node=None,
                status=ReasoningStatus.START,
                message="분석 파이프라인 초기화",
            ),
        )

        with get_db_context() as db:
            user_profile = user_profile_service.get_user_profile(user_id, db)

        yield _sse(
            "user_profile",
            reasoning_builder.attach(
                "user_profile",
                {"profile_loaded": True},
                metadata={},
                agent="system",
                node=None,
                status=ReasoningStatus.INFO,
                message="사용자 프로필 로드 완료",
            ),
        )

        conversation_uuid = uuid.UUID(conversation_id)
        demo_user_uuid = settings.demo_user_uuid

        await chat_history_service.upsert_session(
            conversation_id=conversation_uuid,
            user_id=demo_user_uuid,
            metadata={
                "intervention_required": intervention_required,
                "hitl_config": hitl_config.model_dump(),
            },
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

        # 비동기 checkpointer 사용 (astream_events를 위해 필수)
        from src.utils.checkpointer_factory import get_checkpointer
        from src.subgraphs.graph_master import build_supervisor

        checkpointer = await get_checkpointer()
        supervisor_workflow = build_supervisor(intervention_required=intervention_required)
        app = supervisor_workflow.compile(checkpointer=checkpointer)

        config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}
        configured_app = app.with_config(config)

        initial_state = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id or str(demo_user_uuid),
            "conversation_id": conversation_id,
            "hitl_config": hitl_config.model_dump(),
            "intervention_required": intervention_required,
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
            "hitl_interrupted": False,
            "trade_order_id": None,
            "trade_result": None,
            "summary": None,
            "final_response": None,
            "conversation_history": conversation_history,
        }

        async for event in configured_app.astream_events(initial_state, version="v2"):
            for chunk in _event_to_sse_chunks(event, stream_thinking, reasoning_builder):
                yield chunk

        state = await configured_app.aget_state(config)
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
                    intervention_required=intervention_required,
                    hitl_config=hitl_config,
                )

            if hitl_result:
                yield _sse(
                    "hitl_interrupt",
                    reasoning_builder.attach(
                        "hitl_interrupt",
                        {
                            "pending_nodes": pending_nodes,
                            "approval_request": hitl_result["approval_request"],
                            "message": hitl_result["message"],
                        },
                        metadata={},
                        agent="supervisor",
                        node=None,
                        status=ReasoningStatus.INFO,
                        message="HITL 승인이 필요합니다.",
                    ),
                )

                interrupt_time = datetime.utcnow()
                approved_payload = await _await_approved_response(
                    conversation_uuid=conversation_uuid,
                    interrupt_time=interrupt_time,
                )

                if approved_payload:
                    final_message_text, final_metadata = approved_payload
                else:
                    logger.warning(
                        "⚠️ [MultiAgentStream] 승인 결과 누락 - 타임아웃: %s",
                        conversation_id,
                    )
                    final_message_text = "승인 결과가 아직 등록되지 않았습니다."
                    final_metadata = {}

                yield _sse(
                    "master_complete",
                    reasoning_builder.attach(
                        "master_complete",
                        {"message": final_message_text, "conversation_id": conversation_id},
                        metadata={},
                        agent="supervisor",
                        node=None,
                        status=ReasoningStatus.COMPLETE,
                        message="최종 응답 생성 완료",
                        extra_metadata={"final_message_metadata": final_metadata},
                    ),
                )
                yield _sse(
                    "done",
                    reasoning_builder.attach(
                        "done",
                        {"conversation_id": conversation_id},
                        metadata={},
                        agent="system",
                        node=None,
                        status=ReasoningStatus.COMPLETE,
                        message="스트리밍 종료",
                    ),
                )
                return
            else:  # pragma: no cover - 예외적인 실패
                logger.warning("⚠️ [MultiAgentStream] HITL 헬퍼 실행 실패 - 기본 이벤트만 전송")
                yield _sse(
                    "hitl_interrupt",
                    reasoning_builder.attach(
                        "hitl_interrupt",
                        {
                            "pending_nodes": pending_nodes,
                            "tasks": [getattr(task, "__dict__", str(task)) for task in getattr(state, "tasks", [])],
                        },
                        metadata={},
                        agent="supervisor",
                        node=None,
                        status=ReasoningStatus.INFO,
                        message="HITL 처리 중 오류",
                    ),
                )

        values = getattr(state, "values", {})
        final_message = _extract_final_message(values)

        await chat_history_service.append_message(
            conversation_id=conversation_uuid,
            role="assistant",
            content=final_message,
            metadata={"source": "graph"},
        )

        yield _sse(
            "master_complete",
            reasoning_builder.attach(
                "master_complete",
                {"message": final_message, "conversation_id": conversation_id},
                metadata={},
                agent="supervisor",
                node=None,
                status=ReasoningStatus.COMPLETE,
                message="최종 응답 생성 완료",
            ),
        )
        yield _sse(
            "done",
            reasoning_builder.attach(
                "done",
                {"conversation_id": conversation_id},
                metadata={},
                agent="system",
                node=None,
                status=ReasoningStatus.COMPLETE,
                message="스트리밍 종료",
            ),
        )

    except Exception as exc:  # pragma: no cover - SSE 경로 오류 처리
        logger.exception("❌ [MultiAgentStream] 실행 실패: %s", exc)
        error_message = f"죄송합니다. 그래프 실행 중 오류가 발생했습니다: {exc}"
        yield _sse(
            "error",
            reasoning_builder.attach(
                "error",
                {"error": str(exc), "message": error_message},
                metadata={},
                agent="system",
                node=None,
                status=ReasoningStatus.ERROR,
                message="그래프 실행 중 오류 발생",
            ),
        )
        yield _sse(
            "done",
            reasoning_builder.attach(
                "done",
                {"conversation_id": conversation_id},
                metadata={},
                agent="system",
                node=None,
                status=ReasoningStatus.COMPLETE,
                message="스트리밍 종료",
            ),
        )


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
        - `agent`: 에이전트 이름 (예: "Research_Agent", "Quantitative_Agent")
        - `node`: 노드 이름 (예: "planner", "data_worker")
        - `step`: 스텝 번호
    - `agent_llm_start`: LLM 호출 시작
        - `agent`: 에이전트 이름
        - `node`: 노드 이름
        - `model`: 모델 이름 (예: "gpt-4o")
    - `agent_thinking`: LLM 응답 스트리밍 (stream_thinking=True일 때)
        - `agent`: 에이전트 이름
        - `node`: 노드 이름
        - `content`: 생성된 텍스트 조각
    - `agent_llm_end`: LLM 호출 완료
        - `agent`: 에이전트 이름
        - `node`: 노드 이름
    - `tools_start`: 툴 실행 시작
        - `tool`: 툴 이름 (예: "get_current_price", "get_financial_data")
        - `agent`: 에이전트 이름
        - `node`: 노드 이름
        - `input`: 툴 입력 데이터
    - `tools_complete`: 툴 실행 완료
        - `tool`: 툴 이름
        - `agent`: 에이전트 이름
        - `node`: 노드 이름
        - `status`: "complete"
        - `output`: 툴 출력 데이터
    - `agent_complete`: 서브 에이전트 완료
        - `agent`: 에이전트 이름
        - `node`: 노드 이름
        - `step`: 스텝 번호
    - `master_complete`: 전체 완료
    - `hitl_interrupt`: HITL 승인 요청
    - `error`: 에러 발생
    - `done`: 스트리밍 종료

    **reasoning_event 메타데이터**

    모든 SSE payload에는 `reasoning_event` 객체가 포함되며,
    `phase`, `status`, `depth`, `lineage`, `message` 등을 통해
    프론트엔드가 사고 과정을 보다 직관적으로 시각화할 수 있습니다.
    ```json
    {
      "event": "agent_start",
      "reasoning_event": {
        "event_label": "agent_start",
        "phase": "planning",
        "status": "start",
        "actor": "agent",
        "agent": "Research_Agent",
        "node": "planner",
        "depth": 1,
        "lineage": ["supervisor_node", "Research_Agent"],
        "message": "Research_Agent 실행 시작"
      }
    }
    ```

    **Frontend 사용 예시 (React):**
    ```javascript
    const [agentStatus, setAgentStatus] = useState({});
    const [currentTools, setCurrentTools] = useState([]);

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
        // UI에 표시: Research, Quantitative 에이전트 활성화
    });

    eventSource.addEventListener('agent_start', (event) => {
        const data = JSON.parse(event.data);
        console.log(`[${data.agent}] ${data.node} 노드 시작 (Step ${data.step})`);
        setAgentStatus(prev => ({
            ...prev,
            [data.agent]: 'running'
        }));
        // UI: Research Agent 카드에 "실행 중 - planner" 표시
    });

    eventSource.addEventListener('tools_start', (event) => {
        const data = JSON.parse(event.data);
        console.log(`[${data.agent}/${data.node}] 툴 실행: ${data.tool}`);
        setCurrentTools(prev => [...prev, data.tool]);
        // UI: "get_financial_data 실행 중..." 표시
    });

    eventSource.addEventListener('tools_complete', (event) => {
        const data = JSON.parse(event.data);
        console.log(`[${data.agent}/${data.node}] 툴 완료: ${data.tool}`);
        setCurrentTools(prev => prev.filter(t => t !== data.tool));
        // UI: "get_financial_data 완료 ✓" 표시
    });

    eventSource.addEventListener('agent_llm_start', (event) => {
        const data = JSON.parse(event.data);
        console.log(`[${data.agent}/${data.node}] LLM 호출: ${data.model}`);
        // UI: "AI 분석 중... (gpt-4o)" 표시
    });

    eventSource.addEventListener('agent_thinking', (event) => {
        const data = JSON.parse(event.data);
        // 실시간 LLM 응답 스트리밍 (ChatGPT처럼)
        appendThinkingContent(data.agent, data.node, data.content);
    });

    eventSource.addEventListener('agent_complete', (event) => {
        const data = JSON.parse(event.data);
        console.log(`[${data.agent}] 완료 (Step ${data.step})`);
        setAgentStatus(prev => ({
            ...prev,
            [data.agent]: 'complete'
        }));
        // UI: Research Agent 카드에 "완료 ✓" 표시
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
    [Supervisor] 분석 시작...
    ├─ [Routing] Research Agent 선택 ✓
    │
    ├─ 📊 [Research Agent] 실행 중...
    │   ├─ [planner] 분석 계획 수립 중... ✓
    │   ├─ [data_worker] 데이터 수집 중...
    │   │   ├─ [get_financial_data] 재무 데이터 조회 중... ✓
    │   │   └─ [get_price_data] 가격 데이터 조회 중... ✓
    │   ├─ [bull_worker] 긍정 시나리오 분석 (LLM) ✓
    │   ├─ [bear_worker] 부정 시나리오 분석 (LLM) ✓
    │   └─ [synthesis] 종합 분석 (LLM) ✓
    │   → 결과: SELL, 목표가 90,000원
    │
    ├─ 📈 [Quantitative Agent] 실행 중...
    │   ├─ [financial_analyzer] 재무 분석 중...
    │   │   └─ [calculate_ratios] PER, PBR 계산 중... ✓
    │   └─ [valuation] 밸류에이션 (LLM) ✓
    │   → 결과: 고평가 (PER 25.3)
    │
    └─ [Supervisor] 최종 응답 생성 중... ✓

    ✅ 완료: 현재 삼성전자는 고평가 구간으로 SELL 추천입니다...
    ```
    """
    user_id = request.user_id or str(uuid.uuid4())
    conversation_id = request.conversation_id or str(uuid.uuid4())

    return StreamingResponse(
        stream_multi_agent_execution(
            message=request.message,
            user_id=user_id,
            conversation_id=conversation_id,
            hitl_config=request.hitl_config,
            intervention_required=request.intervention_required,
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
