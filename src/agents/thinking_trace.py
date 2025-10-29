"""
Thinking Trace - AI 사고 과정 추적

LangGraph의 astream_events를 사용하여 에이전트의 도구 호출과 사고 과정 수집
"""
import logging
from typing import AsyncGenerator, Dict, Any, List

logger = logging.getLogger(__name__)


async def collect_thinking_trace(
    agent,
    input_state: Dict[str, Any],
    config: Dict[str, Any]
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    에이전트 실행 중 사고 과정을 스트리밍으로 수집

    Args:
        agent: LangGraph agent (서브그래프 또는 create_react_agent)
        input_state: 에이전트 입력 상태
        config: 실행 설정

    Yields:
        사고 과정 이벤트
            - type: "thought" | "tool_call" | "tool_result" | "answer"
            - content: 이벤트 내용
            - timestamp: 타임스탬프
    """
    logger.info("🧠 [ThinkingTrace] 사고 과정 수집 시작")

    try:
        async for event in agent.astream_events(input_state, config, version="v2"):
            event_type = event.get("event")
            event_name = event.get("name", "")
            event_data = event.get("data", {})

            # 1. LLM 사고 과정 (on_chat_model_stream)
            if event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield {
                        "type": "thought",
                        "content": chunk.content,
                        "metadata": {
                            "model": event_name
                        }
                    }

            # 2. 도구 호출 시작 (on_tool_start)
            elif event_type == "on_tool_start":
                tool_name = event_name
                tool_input = event_data.get("input", {})

                yield {
                    "type": "tool_call",
                    "content": {
                        "tool": tool_name,
                        "input": tool_input
                    },
                    "metadata": {
                        "run_id": event.get("run_id")
                    }
                }

                logger.info(f"🔧 [Tool Call] {tool_name}")

            # 3. 도구 실행 결과 (on_tool_end)
            elif event_type == "on_tool_end":
                tool_name = event_name
                tool_output = event_data.get("output")

                yield {
                    "type": "tool_result",
                    "content": {
                        "tool": tool_name,
                        "output": tool_output
                    },
                    "metadata": {
                        "run_id": event.get("run_id")
                    }
                }

                logger.info(f"✅ [Tool Result] {tool_name}")

            # 4. 최종 답변 (on_chain_end with agent name)
            elif event_type == "on_chain_end" and "agent" in event_name.lower():
                final_output = event_data.get("output")

                if final_output:
                    yield {
                        "type": "answer",
                        "content": final_output,
                        "metadata": {
                            "agent": event_name
                        }
                    }

                    logger.info("📝 [Answer] 최종 답변 생성")

    except Exception as e:
        logger.error(f"❌ [ThinkingTrace] 에러: {e}")
        yield {
            "type": "error",
            "content": str(e)
        }


async def collect_thinking_trace_list(
    agent,
    input_state: Dict[str, Any],
    config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    사고 과정을 리스트로 수집 (non-streaming)

    Args:
        agent: LangGraph agent (서브그래프 또는 create_react_agent)
        input_state: 에이전트 입력 상태
        config: 실행 설정

    Returns:
        사고 과정 이벤트 리스트
    """
    trace_events = []

    async for event in collect_thinking_trace(agent, input_state, config):
        trace_events.append(event)

    logger.info(f"✅ [ThinkingTrace] 수집 완료: {len(trace_events)}개 이벤트")

    return trace_events


def format_thinking_trace_for_display(trace_events: List[Dict[str, Any]]) -> str:
    """
    사고 과정을 사용자 친화적인 형식으로 포맷팅

    Args:
        trace_events: 사고 과정 이벤트 리스트

    Returns:
        포맷팅된 Markdown 문자열
    """
    output_lines = ["## 🧠 AI 사고 과정\n"]

    step_number = 1

    for event in trace_events:
        event_type = event.get("type")
        content = event.get("content")

        if event_type == "thought":
            # 사고 과정 (실시간 스트리밍에서는 누적)
            output_lines.append(f"{content}")

        elif event_type == "tool_call":
            # 도구 호출
            tool_name = content.get("tool")
            tool_input = content.get("input", {})

            output_lines.append(f"\n**Step {step_number}: {tool_name} 호출**\n")
            output_lines.append(f"- 입력: `{tool_input}`\n")
            step_number += 1

        elif event_type == "tool_result":
            # 도구 결과
            tool_name = content.get("tool")
            tool_output = content.get("output")

            output_lines.append(f"- 결과: {tool_output}\n")

        elif event_type == "answer":
            # 최종 답변
            output_lines.append(f"\n---\n\n## 📝 최종 답변\n\n{content}\n")

        elif event_type == "error":
            # 에러
            output_lines.append(f"\n❌ 에러: {content}\n")

    return "".join(output_lines)
