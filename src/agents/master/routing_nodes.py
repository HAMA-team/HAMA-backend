"""
Supervisor 라우팅/워커/직접 답변 노드 구현

Router Agent의 Structured Output 프롬프트 결과를 활용하여
LangGraph 내에서 에이전트 호출 여부를 결정한다.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate

from src.agents.router.router_agent import route_query
from src.config.settings import settings
from src.schemas.graph_state import GraphState
from src.services.stock_data_service import stock_data_service
from src.utils.llm_factory import get_claude_llm
from src.utils.stock_name_extractor import extract_stock_names_from_query
from src.utils.text_utils import ensure_plain_text
from src.workers.market_data import get_stock_price, get_index_price

logger = logging.getLogger(__name__)


async def _resolve_stock_code_from_names(stock_names: Optional[List[str]]) -> Optional[str]:
    if not stock_names:
        return None
    for stock_name in stock_names:
        if not stock_name:
            continue
        for market in ("KOSPI", "KOSDAQ", "KONEX"):
            code = await stock_data_service.get_stock_by_name(stock_name, market=market)
            if code:
                logger.info("✅ [Routing] 종목 코드 찾기 성공: %s -> %s", stock_name, code)
                return code
    return None


async def _resolve_stock_code_from_query(query: str) -> Optional[str]:
    digit_match = re.search(r"\b(\d{6})\b", query)
    if digit_match:
        return digit_match.group(1)
    stock_names = await extract_stock_names_from_query(query)
    return await _resolve_stock_code_from_names(stock_names)


async def routing_node(state: GraphState) -> Dict[str, Any]:
    """Router 프롬프트를 Supervisor 진입 노드로 재사용한다."""

    raw_query = state.get("query")
    query = ensure_plain_text(raw_query).strip()

    if not query and state.get("messages"):
        last_message = state["messages"][-1]
        query = ensure_plain_text(getattr(last_message, "content", "")).strip()

    if not query:
        logger.warning("⚠️ [RoutingNode] 빈 쿼리 - Supervisor가 직접 처리")
        return {
            "agents_to_call": [],
            "direct_answer": "분석할 문장을 입력해 주세요.",
            "routing_decision": {"reasoning": "빈 질문 감지"},
            "clarification_needed": False,
        }

    user_profile = state.get("user_profile") or {}
    conversation_history = state.get("conversation_history") or []

    decision = await route_query(
        query=query,
        user_profile=user_profile,
        conversation_history=conversation_history,
    )

    worker_params = decision.worker_params.model_dump(exclude_none=True) if decision.worker_params else {}
    personalization = decision.personalization.model_dump(exclude_none=True)
    stock_name = decision.stock_names[0] if decision.stock_names else state.get("stock_name")

    update: Dict[str, Any] = {
        "routing_decision": decision.model_dump(exclude_none=True),
        "query": query,
        "depth_level": decision.depth_level,
        "personalization": personalization or None,
        "agents_to_call": list(dict.fromkeys(decision.agents_to_call)),
        "worker_action": decision.worker_action,
        "worker_params": worker_params or None,
        "direct_answer": decision.direct_answer,
        "supervisor_reasoning": decision.reasoning,
        "stock_name": stock_name,
        "clarification_needed": False,
        "clarification_message": None,
    }

    # Stock code 해석 (research/trading or worker stock_price)
    needs_stock_code = any(agent in {"research", "trading"} for agent in decision.agents_to_call) or decision.worker_action == "stock_price"
    stock_code = state.get("stock_code")
    if not stock_code and needs_stock_code:
        if worker_params.get("stock_code"):
            stock_code = worker_params["stock_code"]
        else:
            stock_code = await _resolve_stock_code_from_names(decision.stock_names)
        if not stock_code:
            stock_code = await _resolve_stock_code_from_query(query)

    if stock_code:
        update["stock_code"] = stock_code

    # 종목 코드가 필요한데 못 찾은 경우 clarification
    if needs_stock_code and not stock_code:
        clarification_message = (
            "어떤 종목을 분석할지 알려주세요. 예: '삼성전자' 또는 6자리 티커(005930)."
            if "trading" not in decision.agents_to_call
            else "매매를 진행할 종목명 또는 티커(예: 005930)를 알려주세요."
        )
        update["clarification_needed"] = True
        update["clarification_message"] = clarification_message
        update["agents_to_call"] = []
        update["worker_action"] = None

    return update


def determine_routing_path(state: GraphState) -> str:
    if state.get("clarification_needed"):
        return "clarification"
    if state.get("worker_action"):
        return "worker_dispatch"
    if state.get("direct_answer"):
        return "direct_answer"
    return "supervisor"


async def worker_dispatch_node(state: GraphState) -> Dict[str, Any]:
    action = state.get("worker_action")
    if not action:
        return {}

    params = state.get("worker_params") or {}
    worker_result: Dict[str, Any] = {}

    if action == "stock_price":
        stock_code = params.get("stock_code") or state.get("stock_code")
        stock_name = params.get("stock_name") or state.get("stock_name")

        if not stock_code and stock_name:
            stock_code = await _resolve_stock_code_from_names([stock_name])

        if not stock_code:
            worker_result = {
                "error": "종목 코드를 찾지 못했습니다.",
                "message": "죄송합니다. 종목 코드를 찾을 수 없어 현재가를 제공할 수 없습니다.",
            }
        else:
            worker_result = await get_stock_price(stock_code, stock_name)

    elif action == "index_price":
        index_name = params.get("index_name") or "코스피"
        worker_result = await get_index_price(index_name)

    else:
        worker_result = {
            "error": f"지원되지 않는 worker_action: {action}",
            "message": "요청한 데이터를 처리할 수 없습니다.",
        }

    worker_message_raw = worker_result.get("message", "데이터를 확인했습니다.")
    worker_message = await _render_worker_response(worker_message_raw, state)

    return {
        "agent_results": {
            "worker": {
                "action": action,
                "params": params,
                "result": worker_result,
            }
        },
        "final_response": {"message": worker_message},
        "messages": [AIMessage(content=worker_message)],
        "direct_answer": worker_message,
        "worker_action": None,
    }


async def _render_worker_response(message: str, state: GraphState) -> str:
    """
    워커 결과를 친근한 응답으로 재작성한다.
    """
    recent_context = ""
    history = state.get("conversation_history") or []
    if history:
        recent_messages = history[-2:]
        for msg in recent_messages:
            prefix = "사용자" if msg["role"] == "user" else "AI"
            recent_context += f"{prefix}: {msg['content']}\n"

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "당신은 투자 비서를 대신해 데이터 조회 결과를 친근하게 전달하는 역할입니다. "
                "필요 시 간단한 해석을 덧붙이되, 허위 사실은 추가하지 마세요.",
            ),
            ("human", "최근 대화:\n{recent_context}\n\n원본 메시지:\n{message}"),
        ]
    )

    llm = get_claude_llm(
        temperature=0.4,
        max_tokens=400,
    )

    rendered = await (prompt | llm).ainvoke(
        {
            "recent_context": recent_context or "최근 대화 없음",
            "message": message,
        }
    )
    return rendered.content


async def direct_answer_node(state: GraphState) -> Dict[str, Any]:
    answer = state.get("direct_answer")
    if not answer:
        return {}
    return {
        "messages": [AIMessage(content=answer)],
        "final_response": {"message": answer},
    }


async def clarification_node(state: GraphState) -> Dict[str, Any]:
    clarification_message = state.get("clarification_message") or "추가 정보가 필요합니다."
    return {
        "messages": [AIMessage(content=clarification_message)],
        "final_response": {"message": clarification_message},
        "clarification_needed": None,
    }
