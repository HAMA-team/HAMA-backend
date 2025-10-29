"""
General Agent 노드 함수들 (Deep Agent 스타일)
"""
import json
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage

from src.config.settings import settings
from src.services.search_service import web_search_service
from src.utils.llm_factory import get_llm
from src.utils.json_parser import safe_json_parse

from .state import GeneralState

logger = logging.getLogger(__name__)

ALLOWED_WORKERS = {"search", "analysis", "insight"}

DEFAULT_PLAN = {
    "plan_summary": "검색 → 사실 정리 → 핵심 인사이트 도출",
    "tasks": [
        {
            "id": "task_1",
            "worker": "search",
            "description": "질문과 관련된 최신 웹 정보를 수집한다.",
        },
        {
            "id": "task_2",
            "worker": "analysis",
            "description": "검색 내용을 구조화하고 핵심 사실을 요약한다.",
        },
        {
            "id": "task_3",
            "worker": "insight",
            "description": "사용자에게 유용한 인사이트와 추가 참고 포인트를 정리한다.",
        },
    ],
}


def _sanitize_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not tasks:
        return deepcopy(DEFAULT_PLAN["tasks"])

    sanitized: List[Dict[str, Any]] = []
    for idx, task in enumerate(tasks, start=1):
        worker_raw = str(task.get("worker", "")).lower()

        if worker_raw not in ALLOWED_WORKERS:
            if "search" in worker_raw or "lookup" in worker_raw:
                worker = "search"
            elif "analysis" in worker_raw or "reason" in worker_raw:
                worker = "analysis"
            else:
                worker = "insight"
        else:
            worker = worker_raw

        sanitized.append(
            {
                "id": task.get("id") or f"task_{idx}",
                "worker": worker,
                "description": task.get("description") or task.get("objective") or "조사 작업",
            }
        )

    workers = {task["worker"] for task in sanitized}
    if not workers.issuperset(ALLOWED_WORKERS):
        return deepcopy(DEFAULT_PLAN["tasks"])

    return sanitized


def _task_complete(
    state: GeneralState,
    task: Optional[Dict[str, Any]],
    summary: str,
    extra: Dict[str, Any],
) -> GeneralState:
    completed = list(state.get("completed_tasks") or [])
    notes = list(state.get("task_notes") or [])

    if task:
        completed.append({**task, "status": "done", "summary": summary})
    if summary:
        notes.append(summary)

    update: GeneralState = {
        "completed_tasks": completed,
        "task_notes": notes,
        "current_task": None,
    }
    update.update(extra)
    return update


async def planner_node(state: GeneralState) -> GeneralState:
    query = (state.get("query") or "").strip()

    llm = get_llm(temperature=0, max_tokens=1200)
    prompt = f"""
당신은 투자 교육 및 시장 동향 질문에 답하는 General Agent의 플래너입니다.
사용자 질문: {query or '질문이 비어있습니다.'}

JSON 형식으로만 답변하세요:
{{
  "plan_summary": "한 문장 요약",
  "tasks": [
    {{"id": "task_1", "worker": "search", "description": "..."}},
    {{"id": "task_2", "worker": "analysis", "description": "..."}},
    {{"id": "task_3", "worker": "insight", "description": "..."}}
  ]
}}
worker 값은 반드시 search, analysis, insight 중 하나여야 합니다.
"""

    plan = None
    try:
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        plan = safe_json_parse(content, "General/Planner")
    except Exception as exc:
        logger.warning("⚠️ [General/Planner] 계획 생성 실패, 기본 계획 사용: %s", exc)

    if not isinstance(plan, dict):
        plan = deepcopy(DEFAULT_PLAN)

    sanitized_tasks = _sanitize_tasks(plan.get("tasks", []))
    plan["tasks"] = sanitized_tasks

    plan_message_lines = [
        "🗺️ 조사 계획을 수립했습니다.",
        plan.get("plan_summary") or DEFAULT_PLAN["plan_summary"],
    ]
    for task in sanitized_tasks:
        plan_message_lines.append(f"- ({task['worker']}) {task['description']}")

    plan_message = AIMessage(content="\n".join(plan_message_lines))

    return {
        "plan": plan,
        "pending_tasks": deepcopy(sanitized_tasks),
        "completed_tasks": [],
        "current_task": None,
        "task_notes": [],
        "messages": [plan_message],
    }


def task_router_node(state: GeneralState) -> GeneralState:
    pending = list(state.get("pending_tasks") or [])
    if not pending:
        return {"current_task": None, "pending_tasks": []}

    task = pending.pop(0)
    logger.info("🧭 [General/Router] 다음 작업: %s (%s)", task["id"], task["worker"])
    return {
        "current_task": task,
        "pending_tasks": pending,
    }


async def search_worker_node(state: GeneralState) -> GeneralState:
    task = state.get("current_task")
    query = (state.get("query") or "").strip()

    if not query:
        message = AIMessage(content="질문이 비어 있어 웹 검색을 건너뜁니다.")
        return _task_complete(
            state,
            task,
            "검색 스킵 (빈 질문)",
            {"search_results": [], "messages": [message]},
        )

    logger.info("🌐 [General/Search] 웹 검색 실행: %s", query)
    results = await web_search_service.search(query)

    if results:
        preview_lines = [f"- {item['title']} ({item['url']})" for item in results[:3]]
        summary = f"웹 검색 {len(results)}건 확보"
        message = AIMessage(
            content="웹 검색 결과:\n" + "\n".join(preview_lines)
        )
    else:
        summary = "웹 검색 결과 없음"
        message = AIMessage(
            content="웹 검색에서 유의미한 결과를 찾지 못했습니다. 내부 지식으로 답변을 준비하겠습니다."
        )

    return _task_complete(
        state,
        task,
        summary,
        {
            "search_results": results,
            "messages": [message],
        },
    )


async def analysis_worker_node(state: GeneralState) -> GeneralState:
    if state.get("error"):
        return state

    task = state.get("current_task")
    query = (state.get("query") or "").strip()
    results = state.get("search_results") or []

    llm = get_llm(temperature=0.2, max_tokens=1500)
    prompt = f"""당신은 금융 교육 전문가입니다. 아래 검색 결과를 분석해 핵심 사실을 정리하세요.

질문: {query}
검색 결과:
{json.dumps(results[:6], ensure_ascii=False, indent=2)}

JSON 형식으로 답변하세요:
{{
  "key_points": ["핵심 사실 3~5개"],
  "definitions": ["관련 용어 설명"],
  "data_points": ["숫자/통계 정보"],
  "caveats": ["주의할 점"]
}}
"""

    try:
        response = await llm.ainvoke(prompt)
        analysis = safe_json_parse(response.content, "General/Analysis")
        if not isinstance(analysis, dict):
            analysis = {}
    except Exception as exc:
        logger.error("❌ [General/Analysis] LLM 분석 실패: %s", exc)
        return {
            "error": str(exc),
            "current_task": None,
            "messages": [AIMessage(content=f"분석 중 오류가 발생했습니다: {exc}")],
        }

    summary = "검색 기반 핵심 사실 정리"
    preview = ", ".join((analysis.get("key_points") or [])[:2])
    message = AIMessage(
        content="핵심 사실 요약:\n" + (preview or "검색 기반 핵심 사실을 정리했습니다.")
    )

    return _task_complete(
        state,
        task,
        summary,
        {
            "analysis": analysis,
            "messages": [message],
        },
    )


async def insight_worker_node(state: GeneralState) -> GeneralState:
    if state.get("error"):
        return state

    task = state.get("current_task")
    query = (state.get("query") or "").strip()
    analysis = state.get("analysis") or {}

    llm = get_llm(temperature=0.3, max_tokens=1200)
    prompt = f"""다음 질문과 분석을 참고하여 사용자가 이해하기 쉬운 인사이트와 후속 질문을 제안하세요.

질문: {query}
핵심 분석:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

JSON 형식으로 답변하세요:
{{
  "insights": ["핵심 인사이트 2~3개"],
  "follow_up_questions": ["사용자에게 유용할 추가 질문"]
}}
"""

    try:
        response = await llm.ainvoke(prompt)
        insight = safe_json_parse(response.content, "General/Insight")
        if not isinstance(insight, dict):
            insight = {}
    except Exception as exc:
        logger.error("❌ [General/Insight] LLM 실패: %s", exc)
        return {
            "error": str(exc),
            "current_task": None,
            "messages": [AIMessage(content=f"인사이트 생성 중 오류: {exc}")],
        }

    summary = "인사이트 및 후속 질문 정리"
    insight_lines = insight.get("insights") or []
    message = AIMessage(
        content="추가 인사이트:\n" + "\n".join(f"- {line}" for line in insight_lines[:3])
    )

    return _task_complete(
        state,
        task,
        summary,
        {
            "insight_summary": insight,
            "messages": [message],
        },
    )


async def synthesis_node(state: GeneralState) -> GeneralState:
    if state.get("error"):
        return state

    logger.info("🧩 [General/Synthesis] 최종 답변 생성")

    query = (state.get("query") or "").strip()
    results = state.get("search_results") or []
    analysis = state.get("analysis") or {}
    insight = state.get("insight_summary") or {}

    llm = get_llm(temperature=0.2, max_tokens=1600)
    prompt = f"""당신은 투자 교육 전문가입니다. 아래 자료를 토대로 사용자 질문에 답하세요.

질문: {query}

검색 결과:
{json.dumps(results[:5], ensure_ascii=False, indent=2)}

핵심 분석:
{json.dumps(analysis, ensure_ascii=False, indent=2)}

추가 인사이트:
{json.dumps(insight, ensure_ascii=False, indent=2)}

답변 가이드:
- 개념은 쉬운 문장으로 설명하세요.
- 검색 결과에서 얻은 구체적인 수치나 사실을 포함하세요.
- 참고한 자료는 번호로 표기하지 말고 문장 안에서 출처 이름이나 링크를 자연스럽게 언급하세요.
- 마지막에는 1-2개의 후속 질문을 제안하세요.
"""

    try:
        response = await llm.ainvoke(prompt)
        answer = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        logger.error("❌ [General/Synthesis] 최종 답변 실패: %s", exc)
        return {
            "error": str(exc),
            "messages": [AIMessage(content=f"최종 답변 생성 중 오류: {exc}")],
        }

    top_sources: List[Dict[str, Any]] = []
    for item in results[:3]:
        top_sources.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("snippet"),
            }
        )

    message = AIMessage(content=answer)

    completed = list(state.get("completed_tasks") or [])
    completed.append(
        {
            "id": "synthesis",
            "worker": "synthesis",
            "description": "최종 답변 생성",
            "status": "done",
            "summary": "사용자 응답 작성",
        }
    )

    return {
        "answer": answer,
        "sources": top_sources,
        "messages": [message],
        "completed_tasks": completed,
        "task_notes": list(state.get("task_notes") or []) + ["최종 답변 작성"],
        "agent_results": {
            "general": {
                "answer": answer,
                "sources": top_sources,
            }
        },
    }
