"""
Research Agent 노드 함수들 (Deep Agent 스타일)
"""
import asyncio
import json
import logging
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage

from src.config.settings import settings
from src.utils.llm_factory import get_llm
from src.utils.json_parser import safe_json_parse
from src.utils.indicators import calculate_all_indicators
from src.services.stock_data_service import stock_data_service
from src.services.dart_service import dart_service

from .state import ResearchState

logger = logging.getLogger(__name__)

ALLOWED_WORKERS = {"data", "bull", "bear", "insight", "macro"}

DEFAULT_PLAN = {
    "plan_summary": "데이터 수집 → 거시경제 분석 → 강세·약세 분석 → 핵심 시사점 도출",
    "tasks": [
        {
            "id": "task_1",
            "worker": "data",
            "description": "필요한 시세, 재무, 수급 데이터를 확보한다.",
        },
        {
            "id": "task_2",
            "worker": "macro",
            "description": "거시경제 환경(금리, 물가, 환율)을 분석한다.",
        },
        {
            "id": "task_3",
            "worker": "bull",
            "description": "강세 관점에서 투자 논리를 정리한다.",
        },
        {
            "id": "task_4",
            "worker": "bear",
            "description": "약세 관점에서 리스크 요인을 정리한다.",
        },
        {
            "id": "task_5",
            "worker": "insight",
            "description": "중요 인사이트와 잔여 리스크를 요약한다.",
        },
    ],
}


def _coerce_number(value: Any, fallback: float) -> float:
    try:
        if value is None:
            raise ValueError
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = str(value).replace(",", "").strip()
        if not cleaned:
            raise ValueError
        return float(cleaned)
    except Exception:
        return float(fallback)


def _extract_stock_code(state: ResearchState) -> str:
    stock_code = state.get("stock_code")
    if stock_code:
        return stock_code

    pattern = re.compile(r"\b(\d{6})\b")

    query = state.get("query")
    if query:
        match = pattern.search(query)
        if match:
            return match.group(1)

    for message in state.get("messages", []):
        if isinstance(message, HumanMessage):
            match = pattern.search(message.content)
            if match:
                return match.group(1)

    raise ValueError("질문에서 종목 코드를 찾을 수 없습니다.")


def _sanitize_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not tasks:
        return deepcopy(DEFAULT_PLAN["tasks"])

    sanitized: List[Dict[str, Any]] = []
    for idx, task in enumerate(tasks, start=1):
        worker_raw = str(task.get("worker", "")).lower()

        if worker_raw not in ALLOWED_WORKERS:
            if "data" in worker_raw:
                worker = "data"
            elif "bull" in worker_raw or "positive" in worker_raw:
                worker = "bull"
            elif "bear" in worker_raw or "risk" in worker_raw:
                worker = "bear"
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
    state: ResearchState,
    task: Optional[Dict[str, Any]],
    summary: str,
    extra: Dict[str, Any],
) -> ResearchState:
    completed = list(state.get("completed_tasks") or [])
    notes = list(state.get("task_notes") or [])

    if task:
        completed.append({**task, "status": "done", "summary": summary})
    if summary:
        notes.append(summary)

    update: ResearchState = {
        "completed_tasks": completed,
        "task_notes": notes,
        "current_task": None,
    }
    update.update(extra)
    return update


async def planner_node(state: ResearchState) -> ResearchState:
    query = state.get("query") or "종목 분석"
    stock_code = _extract_stock_code(state)

    llm = get_llm(temperature=0, max_tokens=1600)
    prompt = f"""
당신은 심층 종목 조사를 계획하는 플래너입니다.
사용자 요청: {query}
예상 종목코드: {stock_code}

JSON 형식으로만 답변하세요:
{{
  "plan_summary": "한 문장 요약",
  "tasks": [
    {{"id": "task_1", "worker": "data", "description": "..." }},
    {{"id": "task_2", "worker": "bull", "description": "..." }},
    {{"id": "task_3", "worker": "bear", "description": "..." }},
    {{"id": "task_4", "worker": "insight", "description": "..."}}
  ]
}}
worker 값은 반드시 data, bull, bear, insight 중 하나여야 합니다.
"""

    plan = None
    try:
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        plan = safe_json_parse(content, "Research/Planner")
    except Exception as exc:
        logger.warning("⚠️ [Research/Planner] 계획 생성 실패, 기본 계획 사용: %s", exc)

    if not isinstance(plan, dict):
        plan = deepcopy(DEFAULT_PLAN)

    sanitized_tasks = _sanitize_tasks(plan.get("tasks", []))
    plan["tasks"] = sanitized_tasks

    plan_message_lines = [
        "📋 조사 계획을 수립했습니다.",
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
        "stock_code": stock_code,
    }


def task_router_node(state: ResearchState) -> ResearchState:
    pending = list(state.get("pending_tasks") or [])
    if not pending:
        return {"current_task": None, "pending_tasks": []}

    task = pending.pop(0)
    logger.info("🧭 [Research/Router] 다음 작업 선택: %s (%s)", task["id"], task["worker"])
    return {
        "current_task": task,
        "pending_tasks": pending,
    }


async def data_worker_node(state: ResearchState) -> ResearchState:
    task = state.get("current_task")
    stock_code = _extract_stock_code(state)
    request_id = state.get("request_id", "research-agent")

    logger.info("📊 [Research/Data] 데이터 수집 시작: %s", stock_code)

    try:
        price_df = await stock_data_service.get_stock_price(stock_code, days=30)
        if price_df is None or len(price_df) == 0:
            raise RuntimeError(f"주가 데이터 조회 실패: {stock_code}")

        price_data = {
            "stock_code": stock_code,
            "days": len(price_df),
            "prices": price_df.reset_index().to_dict("records"),
            "latest_close": float(price_df.iloc[-1]["Close"]),
            "latest_volume": int(price_df.iloc[-1]["Volume"]),
            "source": "FinanceDataReader",
        }

        corp_code = await dart_service.search_corp_code_by_stock_code(stock_code)
        if corp_code:
            financial_statements = await dart_service.get_financial_statement(
                corp_code, bsns_year="2023"
            )
            company_info = await dart_service.get_company_info(corp_code)
            financial_data = {
                "stock_code": stock_code,
                "corp_code": corp_code,
                "year": "2023",
                "statements": financial_statements or {},
                "source": "DART",
            }
            company_data = {
                "stock_code": stock_code,
                "corp_code": corp_code,
                "info": company_info or {},
                "source": "DART",
            }
        else:
            logger.warning("⚠️ [Research/Data] 고유번호 조회 실패: %s", stock_code)
            financial_data = None
            company_data = None

        technical_indicators = calculate_all_indicators(price_df)
        fundamental_data = await stock_data_service.get_fundamental_data(stock_code)
        market_cap_data = await stock_data_service.get_market_cap_data(stock_code)
        investor_trading_data = await stock_data_service.get_investor_trading(stock_code, days=30)

        try:
            market_df = await stock_data_service.get_market_index("KOSPI", days=30)
            market_data = {
                "index": "KOSPI",
                "current": float(market_df.iloc[-1]["Close"])
                if market_df is not None and len(market_df) > 0
                else None,
                "change": float(market_df.iloc[-1]["Close"] - market_df.iloc[-2]["Close"])
                if market_df is not None and len(market_df) > 1
                else None,
                "change_rate": float(
                    (market_df.iloc[-1]["Close"] / market_df.iloc[-2]["Close"] - 1) * 100
                )
                if market_df is not None and len(market_df) > 1
                else None,
            }
        except Exception as exc:
            logger.warning("⚠️ [Research/Data] 시장 지수 조회 실패: %s", exc)
            market_data = {"index": "KOSPI", "current": None, "change": None, "change_rate": None}

        cols = {
            "closing": price_data["latest_close"],
            "per": fundamental_data.get("PER") if fundamental_data else None,
            "pbr": fundamental_data.get("PBR") if fundamental_data else None,
            "foreign_trend": investor_trading_data.get("foreign_trend")
            if investor_trading_data
            else None,
        }
        summary = (
            f"{stock_code} 데이터 확보 완료 (종가 {cols['closing']:,}원, PER {cols['per']}, "
            f"PBR {cols['pbr']}, 외국인 {cols['foreign_trend']})"
        )

        message = AIMessage(
            content=(
                f"{stock_code} 데이터 수집을 완료했습니다. "
                f"현재가 {price_data['latest_close']:,}원, "
                f"최근 거래량 {price_data['latest_volume']:,}주입니다."
            )
        )

        payload: ResearchState = {
            "stock_code": stock_code,
            "price_data": price_data,
            "financial_data": financial_data,
            "company_data": company_data,
            "market_index_data": market_data,
            "fundamental_data": fundamental_data,
            "market_cap_data": market_cap_data,
            "investor_trading_data": investor_trading_data,
            "technical_indicators": technical_indicators,
            "messages": [message],
            "request_id": request_id,
        }
        return _task_complete(state, task, summary, payload)

    except Exception as exc:
        logger.error("❌ [Research/Data] 실패: %s", exc)
        return {
            "error": str(exc),
            "current_task": None,
            "messages": [
                AIMessage(content=f"데이터 수집 중 오류가 발생했습니다: {exc}")
            ],
        }


async def bull_worker_node(state: ResearchState) -> ResearchState:
    if state.get("error"):
        return state

    task = state.get("current_task")
    stock_code = state.get("stock_code") or _extract_stock_code(state)

    logger.info("🐂 [Research/Bull] 강세 분석 시작: %s", stock_code)

    llm = get_llm(max_tokens=2000, temperature=0.3)

    technical = state.get("technical_indicators") or {}
    market = state.get("market_index_data") or {}
    fundamental = state.get("fundamental_data") or {}
    market_cap = state.get("market_cap_data") or {}
    investor = state.get("investor_trading_data") or {}
    price = state.get("price_data") or {}

    prompt = f"""당신은 낙관적 주식 애널리스트입니다. 다음 데이터를 분석하여 긍정적 시나리오를 제시하세요.

종목코드: {stock_code}
현재가: {price.get('latest_close')}
시가총액: {market_cap.get('market_cap')}
펀더멘털: {json.dumps(fundamental, ensure_ascii=False)}
투자주체: {json.dumps(investor, ensure_ascii=False)}
기술적 지표: {json.dumps(technical, ensure_ascii=False)}
시장 지수: {json.dumps(market, ensure_ascii=False)}

JSON 형식으로 답변하세요:
{{
  "positive_factors": ["..."],
  "target_price": 0,
  "confidence": 1,
  "notes": ["핵심 근거"]
}}
"""

    max_retries = 4
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke(prompt)
            content = response.content
            analysis = safe_json_parse(content, "Research/Bull")
            if not isinstance(analysis, dict):
                analysis = {}

            target_price = int(
                _coerce_number(
                    (analysis or {}).get("target_price"),
                    (price.get("latest_close") or 0) * 1.1,
                )
            )
            confidence = int(_coerce_number((analysis or {}).get("confidence"), 3))
            confidence = max(1, min(confidence, 5))

            positive_factors = analysis.get("positive_factors")
            if isinstance(positive_factors, str):
                positive_factors = [positive_factors]
            elif not isinstance(positive_factors, list):
                positive_factors = []

            notes = analysis.get("notes")
            if isinstance(notes, str):
                notes = [notes]
            elif not isinstance(notes, list):
                notes = []

            analysis["target_price"] = target_price
            analysis["confidence"] = confidence
            analysis["positive_factors"] = positive_factors
            analysis["notes"] = notes

            summary = f"강세 분석 완료: 목표가 {target_price:,}, 신뢰도 {confidence}"
            message = AIMessage(
                content=(
                    f"강세 시나리오:\n"
                    f"- 목표가: {target_price:,}원\n"
                    f"- 신뢰도: {confidence}/5\n"
                    f"- 요인: {', '.join(positive_factors[:3])}"
                )
            )

            payload: ResearchState = {
                "bull_analysis": analysis,
                "messages": [message],
            }
            return _task_complete(state, task, summary, payload)
        except Exception as exc:
            logger.error(
                "❌ [Research/Bull] 실패 (시도 %s/%s): %s", attempt + 1, max_retries, exc
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            raise RuntimeError(f"강세 분석 실패: {exc}") from exc


async def bear_worker_node(state: ResearchState) -> ResearchState:
    if state.get("error"):
        return state

    task = state.get("current_task")
    stock_code = state.get("stock_code") or _extract_stock_code(state)

    logger.info("🐻 [Research/Bear] 약세 분석 시작: %s", stock_code)

    llm = get_llm(max_tokens=2000, temperature=0.3)

    technical = state.get("technical_indicators") or {}
    market = state.get("market_index_data") or {}
    fundamental = state.get("fundamental_data") or {}
    investor = state.get("investor_trading_data") or {}
    price = state.get("price_data") or {}

    prompt = f"""당신은 보수적 주식 애널리스트입니다. 다음 데이터를 분석하여 리스크 시나리오를 제시하세요.

종목코드: {stock_code}
현재가: {price.get('latest_close')}
펀더멘털: {json.dumps(fundamental, ensure_ascii=False)}
투자주체: {json.dumps(investor, ensure_ascii=False)}
기술적 지표: {json.dumps(technical, ensure_ascii=False)}
시장 지수: {json.dumps(market, ensure_ascii=False)}

JSON 형식으로 답변하세요:
{{
  "risk_factors": ["..."],
  "downside_target": 0,
  "confidence": 1,
  "notes": ["핵심 리스크"]
}}
"""

    max_retries = 4
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke(prompt)
            content = response.content
            analysis = safe_json_parse(content, "Research/Bear")
            if not isinstance(analysis, dict):
                analysis = {}

            downside_target = int(
                _coerce_number(
                    (analysis or {}).get("downside_target"),
                    (price.get("latest_close") or 0) * 0.95,
                )
            )
            confidence = int(_coerce_number((analysis or {}).get("confidence"), 3))
            confidence = max(1, min(confidence, 5))

            risk_factors = analysis.get("risk_factors")
            if isinstance(risk_factors, str):
                risk_factors = [risk_factors]
            elif not isinstance(risk_factors, list):
                risk_factors = []

            notes = analysis.get("notes")
            if isinstance(notes, str):
                notes = [notes]
            elif not isinstance(notes, list):
                notes = []

            analysis["downside_target"] = downside_target
            analysis["confidence"] = confidence
            analysis["risk_factors"] = risk_factors
            analysis["notes"] = notes

            summary = (
                f"약세 분석 완료: 하락 목표가 {downside_target:,}, 신뢰도 {confidence}"
            )
            message = AIMessage(
                content=(
                    f"약세 시나리오:\n"
                    f"- 하락 목표가: {downside_target:,}원\n"
                    f"- 신뢰도: {confidence}/5\n"
                    f"- 리스크: {', '.join(risk_factors[:3])}"
                )
            )

            payload: ResearchState = {
                "bear_analysis": analysis,
                "messages": [message],
            }
            return _task_complete(state, task, summary, payload)
        except Exception as exc:
            logger.error(
                "❌ [Research/Bear] 실패 (시도 %s/%s): %s", attempt + 1, max_retries, exc
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            raise RuntimeError(f"약세 분석 실패: {exc}") from exc


async def macro_worker_node(state: ResearchState) -> ResearchState:
    """
    거시경제 환경 분석 (BOK API + LLM)

    분석 항목:
    - 기준금리 추세 (상승/하락/유지)
    - CPI (소비자물가) 전년대비 증감률
    - 환율 (원/달러) 변동
    - 해당 종목에 미치는 영향
    """
    if state.get("error"):
        return state

    task = state.get("current_task")
    stock_code = state.get("stock_code") or _extract_stock_code(state)

    logger.info("🌍 [Research/Macro] 거시경제 분석 시작: %s", stock_code)

    try:
        # 1. BOK API로 거시경제 데이터 수집
        from src.services.bok_service import bok_service

        macro_data = bok_service.get_macro_indicators()

        # 2. 종목 정보 추출 (기업명, 업종 등)
        company_data = state.get("company_data") or {}
        company_info = company_data.get("info", {})
        company_name = company_info.get("corp_name", f"종목코드 {stock_code}")

        # 3. LLM으로 거시경제가 해당 종목에 미치는 영향 분석
        llm = get_llm(max_tokens=1500, temperature=0.2)

        prompt = f"""당신은 거시경제 전문 애널리스트입니다. 현재 거시경제 환경이 해당 기업에 미치는 영향을 분석하세요.

## 거시경제 지표
- 기준금리: {macro_data.get('base_rate', 'N/A')}% (추세: {macro_data.get('base_rate_trend', 'N/A')})
- CPI (소비자물가): {macro_data.get('cpi', 'N/A')} (전년대비: {macro_data.get('cpi_yoy', 'N/A') if macro_data.get('cpi_yoy') else 'N/A'}%)
- 환율 (원/달러): {macro_data.get('exchange_rate', 'N/A'):,.0f}원

## 분석 대상 기업
- 기업명: {company_name}
- 종목코드: {stock_code}

**분석 지침:**
1. 금리 환경이 해당 기업에 미치는 영향 (재무 비용, 투자 여력 등)
2. 물가 상승률이 해당 기업에 미치는 영향 (원가 부담, 가격 전가력 등)
3. 환율 변동이 해당 기업에 미치는 영향 (수출입 기업인 경우)
4. 전반적인 경기 사이클 판단

JSON 형식으로 답변하세요:
{{
  "interest_rate_impact": "긍정적" | "부정적" | "중립",
  "interest_rate_reason": "이유 설명",
  "inflation_impact": "긍정적" | "부정적" | "중립",
  "inflation_reason": "이유 설명",
  "exchange_rate_impact": "긍정적" | "부정적" | "중립",
  "exchange_rate_reason": "이유 설명",
  "overall_macro_sentiment": "긍정적" | "부정적" | "중립",
  "summary": "한 줄 요약"
}}
"""

        response = await llm.ainvoke(prompt)
        analysis = safe_json_parse(response.content, "Research/Macro")

        if not isinstance(analysis, dict):
            analysis = {}

        # 4. 거시경제 데이터와 분석 결과 통합
        macro_analysis = {
            "raw_data": macro_data,
            "analysis": analysis,
            "timestamp": asyncio.get_event_loop().time(),
        }

        summary = (
            f"거시경제 분석 완료: 금리 {macro_data.get('base_rate_trend', 'N/A')}, "
            f"전반적 {analysis.get('overall_macro_sentiment', 'N/A')}"
        )

        message = AIMessage(
            content=(
                f"거시경제 환경 분석:\n"
                f"- 기준금리: {macro_data.get('base_rate', 'N/A')}% ({macro_data.get('base_rate_trend', 'N/A')})\n"
                f"- 물가상승률: {macro_data.get('cpi_yoy', 'N/A') if macro_data.get('cpi_yoy') else 'N/A'}%\n"
                f"- 전반적 영향: {analysis.get('overall_macro_sentiment', 'N/A')}\n"
                f"- 요약: {analysis.get('summary', 'N/A')}"
            )
        )

        payload: ResearchState = {
            "macro_analysis": macro_analysis,
            "messages": [message],
        }
        return _task_complete(state, task, summary, payload)

    except Exception as exc:
        logger.error("❌ [Research/Macro] 실패: %s", exc)
        # 거시경제 분석 실패는 치명적이지 않으므로 계속 진행
        return _task_complete(
            state,
            task,
            "거시경제 분석 실패 (생략)",
            {
                "macro_analysis": None,
                "messages": [AIMessage(content=f"거시경제 분석을 건너뜁니다: {exc}")],
            }
        )


async def insight_worker_node(state: ResearchState) -> ResearchState:
    if state.get("error"):
        return state

    task = state.get("current_task")
    stock_code = state.get("stock_code") or _extract_stock_code(state)

    logger.info("🧠 [Research/Insight] 인사이트 정리 시작: %s", stock_code)

    llm = get_llm(max_tokens=1500, temperature=0.2)

    context = {
        "price": {
            "latest_close": state.get("price_data", {}).get("latest_close"),
            "latest_volume": state.get("price_data", {}).get("latest_volume"),
        },
        "fundamental": state.get("fundamental_data"),
        "technical": state.get("technical_indicators", {}),
        "bull": state.get("bull_analysis"),
        "bear": state.get("bear_analysis"),
        "investor": state.get("investor_trading_data"),
        "macro": state.get("macro_analysis"),
    }

    prompt = f"""당신은 시니어 애널리스트입니다. 다음 정보를 기반으로 핵심 인사이트를 도출하세요.

컨텍스트:
{json.dumps(context, ensure_ascii=False)}

**특히 거시경제 환경(macro)을 고려하여 종목의 리스크와 기회를 평가하세요.**

JSON 형식으로 답변하세요:
{{
  "key_takeaways": ["핵심 포인트 3~5개"],
  "risks": ["중요 리스크"],
  "follow_up_questions": ["추가 조사 필요 사안"]
}}
"""

    try:
        response = await llm.ainvoke(prompt)
        insight = safe_json_parse(response.content, "Research/Insight")
        if not isinstance(insight, dict):
            insight = {}

        for key in ("key_takeaways", "risks", "follow_up_questions"):
            value = insight.get(key)
            if isinstance(value, str):
                insight[key] = [value]
            elif not isinstance(value, list):
                insight[key] = []

        summary = "핵심 인사이트 정리 완료"
        message = AIMessage(
            content=(
                "핵심 인사이트 요약:\n"
                + "\n".join(f"- {point}" for point in insight.get("key_takeaways", [])[:4])
            )
        )

        payload: ResearchState = {
            "insight_summary": insight,
            "messages": [message],
        }
        return _task_complete(state, task, summary, payload)
    except Exception as exc:
        logger.error("❌ [Research/Insight] 실패: %s", exc)
        return {
            "error": str(exc),
            "current_task": None,
            "messages": [
                AIMessage(content=f"인사이트 정리 중 오류가 발생했습니다: {exc}")
            ],
        }


async def synthesis_node(state: ResearchState) -> ResearchState:
    if state.get("error"):
        return state

    logger.info("🤝 [Research/Synthesis] 최종 의견 통합 시작")

    bull = state.get("bull_analysis") or {}
    bear = state.get("bear_analysis") or {}
    price_data = state.get("price_data") or {}
    technical = state.get("technical_indicators") or {}
    fundamental = state.get("fundamental_data") or {}
    investor = state.get("investor_trading_data") or {}
    market_cap = state.get("market_cap_data") or {}
    stock_code = state.get("stock_code") or "N/A"

    current_price = price_data.get("latest_close") or 0
    bull_target = _coerce_number(bull.get("target_price"), current_price * 1.1)
    bear_target = _coerce_number(bear.get("downside_target"), current_price * 0.95)
    bull_conf = int(_coerce_number(bull.get("confidence"), 3))
    bear_conf = int(_coerce_number(bear.get("confidence"), 3))
    bull_conf = max(1, min(bull_conf, 5))
    bear_conf = max(1, min(bear_conf, 5))

    tech_trend = technical.get("overall_trend", "중립")
    if tech_trend == "강세":
        bull_conf = min(bull_conf + 1, 5)
    elif tech_trend == "약세":
        bear_conf = min(bear_conf + 1, 5)

    per = fundamental.get("PER")
    pbr = fundamental.get("PBR")

    valuation_status = "적정"
    if per is not None and pbr is not None:
        if per > 30 or pbr > 3:
            valuation_status = "고평가"
            bull_conf = max(bull_conf - 1, 1)
            bear_conf = min(bear_conf + 1, 5)
        elif per < 10 or pbr < 1:
            valuation_status = "저평가"
            bull_conf = min(bull_conf + 1, 5)
            bear_conf = max(bear_conf - 1, 1)

    foreign_trend = investor.get("foreign_trend", "보합")
    institution_trend = investor.get("institution_trend", "보합")

    investor_sentiment = "중립"
    if foreign_trend == "매수" and institution_trend == "매수":
        investor_sentiment = "긍정"
        bull_conf = min(bull_conf + 1, 5)
    elif foreign_trend == "매도" and institution_trend == "매도":
        investor_sentiment = "부정"
        bear_conf = min(bear_conf + 1, 5)

    total_conf = max(bull_conf + bear_conf, 1)
    target_price = int((bull_target * bull_conf + bear_target * bear_conf) / total_conf)

    upside = 0.0
    if current_price:
        upside = (target_price - current_price) / current_price

    rsi_signal = technical.get("rsi", {}).get("signal", "중립")

    if upside > 0.15 and rsi_signal != "과매수" and valuation_status != "고평가":
        recommendation = "BUY"
    elif upside < -0.05 or rsi_signal == "과매수" or valuation_status == "고평가":
        recommendation = "SELL"
    else:
        recommendation = "HOLD"

    confidence = int((bull_conf + bear_conf) / 2)

    fundamental_summary = {
        "PER": per,
        "PBR": pbr,
        "EPS": fundamental.get("EPS"),
        "DIV": fundamental.get("DIV"),
        "valuation": valuation_status,
    }

    investor_summary = {
        "foreign_trend": foreign_trend,
        "institution_trend": institution_trend,
        "foreign_net": investor.get("foreign_net"),
        "institution_net": investor.get("institution_net"),
        "sentiment": investor_sentiment,
    }

    market_cap_trillion = (
        market_cap.get("market_cap", 0) / 1e12 if market_cap.get("market_cap") else None
    )

    consensus = {
        "recommendation": recommendation,
        "target_price": target_price,
        "current_price": int(current_price),
        "upside_potential": f"{upside:.1%}" if current_price else "N/A",
        "confidence": confidence,
        "bull_case": bull.get("positive_factors", []),
        "bear_case": bear.get("risk_factors", []),
        "technical_summary": {
            "trend": tech_trend,
            "rsi": rsi_signal,
            "signals": technical.get("signals", []),
        },
        "fundamental_summary": fundamental_summary,
        "investor_summary": investor_summary,
        "market_cap_trillion": market_cap_trillion,
        "summary": (
            f"{stock_code} - {recommendation} (목표가: {target_price:,}원, "
            f"펀더멘털: {valuation_status}, 투자주체: {investor_sentiment}, "
            f"기술적 추세: {tech_trend})"
        ),
    }

    logger.info(
        "✅ [Research/Synthesis] 최종 의견: %s (신뢰도 %s, 상승여력 %s)",
        recommendation,
        confidence,
        consensus["upside_potential"],
    )

    per_text = f"PER {per:.1f}배" if per is not None else "PER N/A"
    pbr_text = f"PBR {pbr:.2f}배" if pbr is not None else "PBR N/A"

    message = AIMessage(
        content=(
            f"추천: {recommendation} (목표가 {target_price:,}원, 현재가 {current_price:,}원). "
            f"상승여력 {consensus['upside_potential']}, 신뢰도 {confidence}/5. "
            f"펀더멘털: {per_text}, {pbr_text} ({valuation_status}). "
            f"투자주체: 외국인 {foreign_trend}, 기관 {institution_trend}."
        )
    )

    notes = list(state.get("task_notes") or [])
    notes.append(f"최종 의견 {recommendation} (신뢰도 {confidence})")

    completed = list(state.get("completed_tasks") or [])
    completed.append(
        {
            "id": "synthesis",
            "worker": "synthesis",
            "description": "최종 의견 통합",
            "status": "done",
            "summary": consensus["summary"],
        }
    )

    return {
        "consensus": consensus,
        "messages": [message],
        "task_notes": notes,
        "completed_tasks": completed,
    }
