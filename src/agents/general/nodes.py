"""
ReAct 기반 General Agent 래퍼 노드
"""
from typing import List

from langchain_core.messages import AIMessage, BaseMessage

from src.utils.json_parser import safe_json_parse

from .state import GeneralState
from .react_agent import create_general_react_agent

# Lazy 초기화를 피하기 위해 모듈 로드 시점에 생성
_react_agent = create_general_react_agent()


def _extract_final_response(messages: List[BaseMessage]) -> tuple[str, list, str | None]:
    """
    ReAct 최종 메시지에서 answer/sources/confidence 추출
    """
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            # LLM이 JSON 형식을 반환하지 않을 수 있으므로 예외 처리
            try:
                parsed = safe_json_parse(message.content, "General/Final")
                if isinstance(parsed, dict) and parsed.get("answer"):
                    answer = str(parsed.get("answer", "")).strip()
                    sources = parsed.get("sources") or []
                    confidence = parsed.get("confidence")
                    return answer, sources, confidence
            except ValueError:
                # JSON 파싱 실패 시 일반 텍스트로 처리
                pass

            # JSON이 아니거나 파싱 실패한 경우 원본 텍스트 반환
            return message.content.strip(), [], None
    return "", [], None


async def react_node(state: GeneralState) -> GeneralState:
    """
    단일 ReAct 에이전트를 실행하고 결과를 GraphState에 맞게 정규화합니다.
    """
    incoming_messages = state.get("messages") or []
    query = state.get("query")

    # ReAct 에이전트 실행
    result = await _react_agent.ainvoke({"messages": incoming_messages})
    final_messages: List[BaseMessage] = result.get("messages", [])

    answer, sources, confidence = _extract_final_response(final_messages)

    agent_payload = {
        "answer": answer,
        "sources": sources,
    }
    if confidence:
        agent_payload["confidence"] = confidence
    if query:
        agent_payload["query"] = query

    return {
        "messages": final_messages,
        "agent_results": {
            "general": agent_payload,
        },
    }

