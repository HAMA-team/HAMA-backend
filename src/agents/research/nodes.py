"""
Research Agent 노드 함수들 (Deep Agent 스타일)
"""
import asyncio
import json
import logging
import re
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union, Coroutine

from langchain_core.messages import AIMessage, HumanMessage

from src.agents.research.state import ResearchState
from src.config.settings import settings
from src.utils.llm_factory import get_llm
from src.utils.json_parser import safe_json_parse
from src.utils.indicators import calculate_all_indicators
from src.utils.stock_name_extractor import extract_stock_names_from_query
from src.services.stock_data_service import stock_data_service
from src.services.dart_service import dart_service
from src.constants.analysis_depth import (
    ANALYSIS_DEPTH_LEVELS,
    classify_depth_by_keywords,
    extract_focus_areas,
    get_default_depth,
)

from .state import ResearchState

logger = logging.getLogger(__name__)

ALLOWED_WORKERS = {"data", "bull", "bear", "insight", "macro", "technical", "trading_flow", "information"}


def _json_default(value: Any) -> Union[float, str, list]:
    """json.dumps에서 직렬화할 수 없는 값을 안전하게 변환한다."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, set):
        return list(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


def _dumps(data: Any, **kwargs: Any) -> str:
    """ensure_ascii를 False로 유지하며 기본 변환기를 적용한다."""
    kwargs.setdefault("ensure_ascii", False)
    kwargs.setdefault("default", _json_default)
    return json.dumps(data, **kwargs)


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


async def _extract_stock_code(state: ResearchState) -> str:
    """
    State에서 종목 코드를 추출합니다 (LLM 기반 종목명 추출 지원).

    Returns:
        종목 코드 (6자리)

    Raises:
        ValueError: 종목 코드를 찾을 수 없는 경우
    """
    # 1. State에 이미 종목 코드가 있으면 사용
    stock_code = state.get("stock_code")
    if stock_code:
        return stock_code

    # 2. 6자리 코드 패턴 검색 (빠른 매칭)
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

    # 3. LLM을 사용하여 종목명 추출 후 코드로 변환
    if query:
        try:
            stock_names = await extract_stock_names_from_query(query)
            if stock_names:
                stock_name = stock_names[0]  # 첫 번째 종목 사용

                # 종목명으로 코드 검색
                markets = ["KOSPI", "KOSDAQ", "KONEX"]
                for market in markets:
                    try:
                        code = await stock_data_service.get_stock_by_name(stock_name, market=market)
                        if code:
                            logger.info(f"✅ [Research] 종목 코드 추출 성공: {stock_name} -> {code}")
                            return code
                    except Exception as exc:
                        logger.debug(f"⚠️ [Research] 종목 검색 실패 ({stock_name}/{market}): {exc}")
                        continue

                logger.warning(f"⚠️ [Research] 종목 코드를 찾을 수 없음: {stock_name}")
        except Exception as exc:
            logger.error(f"❌ [Research] 종목명 추출 실패: {exc}")

    raise ValueError(f"질문에서 종목 코드를 찾을 수 없습니다: {query}")


def _sanitize_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    LLM이 생성한 태스크를 검증하고 정리
    """
    if not tasks:
        raise ValueError("태스크 리스트가 비어있습니다. LLM이 올바른 계획을 생성하지 못했습니다.")

    sanitized: List[Dict[str, Any]] = []
    for idx, task in enumerate(tasks, start=1):
        worker_raw = str(task.get("worker", "")).lower()

        # Worker 타입 정규화
        if worker_raw not in ALLOWED_WORKERS:
            if "data" in worker_raw:
                worker = "data"
            elif "technical" in worker_raw or "기술적" in worker_raw:
                worker = "technical"
            elif "trading" in worker_raw or "거래" in worker_raw or "flow" in worker_raw:
                worker = "trading_flow"
            elif "information" in worker_raw or "news" in worker_raw or "정보" in worker_raw:
                worker = "information"
            elif "bull" in worker_raw or "positive" in worker_raw:
                worker = "bull"
            elif "bear" in worker_raw or "risk" in worker_raw:
                worker = "bear"
            elif "macro" in worker_raw:
                worker = "macro"
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


async def query_intent_classifier_node(state: ResearchState) -> ResearchState:
    """
    Query Intent Classifier (쿼리 의도 분석기) - LLM 완전 판단 기반

    사용자 쿼리와 UserProfile을 분석하여 적절한 분석 깊이를 결정합니다.
    키워드 의존성을 제거하고 LLM이 전체 맥락을 이해하여 판단합니다.

    분석 요소:
    1. LLM 기반 쿼리 복잡도 판단 (키워드 없이 전체 문맥 이해)
    2. 사용자 성향 반영 (투자 경험, 선호 깊이, 최근 선택 패턴)
    3. Focus Areas 자동 추출 (LLM이 필요한 분석 영역 판단)
    4. 암묵적 요구사항 파악
    """
    query = state.get("query", "")
    user_profile = state.get("user_profile") or {}

    logger.info("🎯 [Research/IntentClassifier] 쿼리 의도 분석 시작 (LLM 판단): %s", query[:50])

    # UserProfile 추출
    expertise_level = user_profile.get("expertise_level", "intermediate")
    preferred_depth = user_profile.get("preferred_depth", "detailed")
    recent_depth_choices = user_profile.get("recent_depth_choices", [])

    # Claude 4.x 프롬프트 사용
    from src.prompts.common.intent_classifier import build_research_intent_classifier_prompt

    try:
        llm = get_llm(temperature=0, max_tokens=1000)

        # Claude 4.x 최적화 프롬프트 생성
        prompt = build_research_intent_classifier_prompt(
            query=query,
            user_profile={
                "expertise_level": expertise_level,
                "preferred_depth": preferred_depth,
                "recent_depth_choices": recent_depth_choices,
            },
        )

        # LLM 호출
        response = await llm.ainvoke(prompt)

        # JSON 파싱 (프롬프트 유틸리티 사용)
        from src.prompts import parse_llm_json

        intent = parse_llm_json(response.content)

        # 결과 추출
        final_depth = intent.get("depth", "standard")
        confidence = intent.get("confidence", 0.5)
        reasoning = intent.get("reasoning", "LLM 기반 분류")
        llm_focus_areas = intent.get("focus_areas", [])
        implicit_needs = intent.get("implicit_needs", "")

        # Focus areas를 worker 이름으로 매핑
        focus_workers = []
        worker_mapping = {
            "data": ["data"],
            "technical": ["technical"],
            "trading_flow": ["trading_flow"],
            "information": ["information"],
            "macro": ["macro"],
            "bull": ["bull"],
            "bear": ["bear"],
            "insight": ["insight"],
        }

        for area in llm_focus_areas:
            if area in worker_mapping:
                focus_workers.extend(worker_mapping[area])

        focus_workers = list(set(focus_workers))  # 중복 제거

        logger.info(
            "✅ [Research/IntentClassifier] LLM 판단 완료: %s (확신도: %.2f) | 집중 영역: %s",
            final_depth,
            confidence,
            focus_workers or "자동 선택",
        )

        depth_reason = f"{reasoning} (확신도: {confidence:.0%})"
        if implicit_needs:
            depth_reason += f" | 암묵적 요구: {implicit_needs}"

    except Exception as exc:
        logger.warning("⚠️ [Research/IntentClassifier] LLM 분류 실패, fallback 사용: %s", exc)

        # Fallback: UserProfile 기반 기본값
        profile_depth_map = {
            "brief": "quick",
            "detailed": "standard",
            "comprehensive": "comprehensive",
        }
        final_depth = profile_depth_map.get(preferred_depth, "standard")
        focus_workers = []
        depth_reason = f"사용자 프로파일 기본값 ({preferred_depth})"

    # 최종 유효성 검증
    if final_depth not in ANALYSIS_DEPTH_LEVELS:
        final_depth = get_default_depth()
        depth_reason += " (기본값으로 대체)"

    depth_config = ANALYSIS_DEPTH_LEVELS[final_depth]

    logger.info(
        "📋 [Research/IntentClassifier] 최종 결정: %s (%s) | 집중 영역: %s",
        final_depth,
        depth_config["name"],
        focus_workers or "없음",
    )

    message = AIMessage(
        content=(
            f"분석 깊이: {depth_config['name']} ({depth_config['estimated_time']})\n"
            f"이유: {depth_reason}"
            + (f"\n집중 영역: {', '.join(focus_workers)}" if focus_workers else "")
        )
    )

    return {
        "analysis_depth": final_depth,
        "focus_areas": focus_workers,
        "depth_reason": depth_reason,
        "messages": [message],
    }


async def planner_node(state: ResearchState) -> ResearchState:
    """
    Smart Planner - 분석 깊이에 따라 동적으로 worker 선택

    query_intent_classifier_node에서 결정한 analysis_depth와 focus_areas를 기반으로
    필요한 worker만 선택하여 비용과 시간을 최적화합니다.
    """
    query = state.get("query") or "종목 분석"
    stock_code = await _extract_stock_code(state)
    analysis_depth = state.get("analysis_depth", "standard")
    focus_areas = state.get("focus_areas") or []
    depth_reason = state.get("depth_reason", "")

    # 분석 깊이에 맞는 추천 worker 리스트 가져오기
    from src.constants.analysis_depth import get_recommended_workers, get_depth_config

    recommended_workers = get_recommended_workers(analysis_depth, focus_areas)
    depth_config = get_depth_config(analysis_depth)

    logger.info(
        "🧠 [Research/Planner] Smart Planner 시작 | 깊이: %s (%s) | 추천 Worker: %s",
        analysis_depth, depth_config["name"], recommended_workers
    )

    # Worker 설명
    worker_descriptions = {
        "data": "원시 데이터 수집 (주가, 재무제표, 기업 정보, 기술적 지표)",
        "technical": "기술적 분석 전문가 (이평선, 지지/저항선, 기술적 지표 해석)",
        "trading_flow": "거래 동향 분석 전문가 (기관/외국인/개인 순매수 분석)",
        "information": "정보 분석 전문가 (뉴스, 호재/악재, 시장 센티먼트)",
        "macro": "거시경제 분석 (금리, 환율, 경기 동향)",
        "bull": "강세 시나리오 분석 (상승 가능성 및 근거)",
        "bear": "약세 시나리오 분석 (하락 리스크 및 근거)",
        "insight": "종합 인사이트 정리 (핵심 포인트 요약)",
    }

    # LLM에게 제공할 worker 정보
    available_workers = "\n".join([
        f"- **{worker}**: {worker_descriptions.get(worker, '')}"
        for worker in recommended_workers
    ])

    llm = get_llm(temperature=0, max_tokens=1600)
    prompt = f"""
당신은 심층 종목 조사를 계획하는 Smart Planner입니다.

사용자 요청: {query}
예상 종목코드: {stock_code}

**분석 깊이 설정:**
- 레벨: {analysis_depth} ({depth_config["name"]})
- 이유: {depth_reason}
- 집중 영역: {", ".join(focus_areas) if focus_areas else "없음"}
- 예상 소요 시간: {depth_config["estimated_time"]}

**사용 가능한 Worker (최대 {depth_config["max_workers"]}개):**
{available_workers}

**작업 계획 수립 가이드:**
1. 추천된 worker 중에서 선택하세요 (위 목록 참고)
2. {analysis_depth} 레벨에 맞는 적절한 worker 수를 선택하세요
3. 집중 영역({", ".join(focus_areas) if focus_areas else "없음"})이 있다면 우선적으로 포함하세요
4. worker는 순차적으로 실행됩니다 (data → technical → trading_flow → ... → insight)

JSON 형식으로만 답변하세요:
{{
  "plan_summary": "한 문장 요약",
  "tasks": [
    {{"id": "task_1", "worker": "data", "description": "주가 및 재무 데이터 수집" }},
    {{"id": "task_2", "worker": "technical", "description": "기술적 분석 수행" }}
  ]
}}

중요: worker 값은 위에 나열된 worker 중에서만 선택하세요: {", ".join(recommended_workers)}
"""

    try:
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        plan = safe_json_parse(content, "Research/Planner")

        if not isinstance(plan, dict):
            raise ValueError("LLM이 올바른 JSON 형식의 계획을 생성하지 못했습니다.")

        sanitized_tasks = _sanitize_tasks(plan.get("tasks", []))

        # Worker 검증: 추천된 worker만 사용하도록 필터링
        validated_tasks = []
        for task in sanitized_tasks:
            worker = task.get("worker", "").lower()
            if worker in recommended_workers:
                validated_tasks.append(task)
            else:
                logger.warning(
                    "⚠️ [Research/Planner] 추천되지 않은 worker 제외: %s (추천: %s)",
                    worker, recommended_workers
                )

        if not validated_tasks:
            # Fallback: 최소한 data worker는 실행
            logger.warning("⚠️ [Research/Planner] 유효한 task가 없어 기본 task 생성")
            validated_tasks = [{"id": "task_1", "worker": "data", "description": "기본 데이터 수집"}]

        plan["tasks"] = validated_tasks

    except Exception as exc:
        logger.error("❌ [Research/Planner] 계획 생성 실패: %s", exc)
        raise

    plan_message_lines = [
        f"📋 조사 계획을 수립했습니다 ({depth_config['name']}, {len(validated_tasks)}개 작업).",
        plan.get("plan_summary", "종목 분석 계획"),
    ]
    for task in validated_tasks:
        plan_message_lines.append(f"- ({task['worker']}) {task['description']}")

    plan_message = AIMessage(content="\n".join(plan_message_lines))

    return {
        "plan": plan,
        "pending_tasks": deepcopy(validated_tasks),
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
    stock_code = await _extract_stock_code(state)
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
    stock_code = state.get("stock_code") or await _extract_stock_code(state)

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
펀더멘털: {_dumps(fundamental)} 
투자주체: {_dumps(investor)} 
기술적 지표: {_dumps(technical)} 
시장 지수: {_dumps(market)} 

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
    stock_code = state.get("stock_code") or await _extract_stock_code(state)

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
펀더멘털: {_dumps(fundamental)} 
투자주체: {_dumps(investor)} 
기술적 지표: {_dumps(technical)} 
시장 지수: {_dumps(market)} 

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
    stock_code = state.get("stock_code") or await _extract_stock_code(state)

    logger.info("🌍 [Research/Macro] 거시경제 분석 시작: %s", stock_code)

    try:
        # 1. BOK API로 거시경제 데이터 수집
        from src.services.macro_data_service import macro_data_service

        macro_data = macro_data_service.macro_summary()
        if not macro_data.get("base_rate"):
            await macro_data_service.refresh_all()
            macro_data = macro_data_service.macro_summary()

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
    stock_code = state.get("stock_code") or await _extract_stock_code(state)

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
{_dumps(context)} 

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


async def technical_analyst_worker_node(state: ResearchState) -> ResearchState:
    """
    기술적 분석 전문가 (Technical Analyst)

    역할:
    - 주가 및 거래량 기술적 분석
    - 이동평균선 분석 (골든크로스/데드크로스)
    - 지지선/저항선 식별
    - 거래량 패턴 분석
    - RSI, MACD, 볼린저밴드 등 기술적 지표 해석
    """
    if state.get("error"):
        return state

    task = state.get("current_task")
    stock_code = state.get("stock_code") or await _extract_stock_code(state)

    logger.info("📊 [Research/TechnicalAnalyst] 기술적 분석 시작: %s", stock_code)

    # 데이터 추출
    price_data = state.get("price_data") or {}
    technical = state.get("technical_indicators") or {}

    if not price_data or not technical:
        logger.warning("⚠️ [Research/TechnicalAnalyst] 기술적 데이터 부족")
        return _task_complete(
            state,
            task,
            "기술적 데이터 부족으로 분석 생략",
            {
                "technical_analysis": None,
                "messages": [AIMessage(content="기술적 데이터가 부족하여 분석을 생략합니다.")],
            },
        )

    llm = get_llm(max_tokens=2500, temperature=0.2)

    current_price = price_data.get("latest_close", 0)
    volume = price_data.get("latest_volume", 0)

    prompt = f"""당신은 기술적 분석 전문가입니다. 다음 데이터를 기반으로 상세한 기술적 분석을 제공하세요.

## 종목 정보
- 종목코드: {stock_code}
- 현재가: {current_price:,}원
- 거래량: {volume:,}주

## 기술적 지표 
{_dumps(technical, indent=2)} 

## 분석 항목
1. **주가 추세 분석**: 상승추세/하락추세/횡보 판단 (이동평균선 기반)
2. **이동평균선 분석**:
   - 단기(5일)/중기(20일)/장기(60일) 이평선 배열 상태
   - 골든크로스/데드크로스 발생 여부
   - 현재가와 이평선의 위치 관계
3. **지지선/저항선**:
   - 주요 지지선 가격대
   - 주요 저항선 가격대
4. **거래량 패턴**:
   - 최근 거래량 변화 추세
   - 가격 변동과 거래량의 관계
5. **기술적 지표 해석**:
   - RSI: 과매수/과매도 여부
   - MACD: 매수/매도 신호
   - 볼린저밴드: 밴드폭과 현재가 위치
6. **단기 방향성**: 향후 1~2주 기술적 전망

JSON 형식으로 답변하세요:
{{
  "trend": "상승추세" | "하락추세" | "횡보",
  "trend_strength": 1-5,
  "moving_average_analysis": {{
    "arrangement": "정배열" | "역배열" | "혼재",
    "golden_cross": true | false,
    "death_cross": true | false,
    "ma5": 0,
    "ma20": 0,
    "ma60": 0
  }},
  "support_resistance": {{
    "support_levels": [가격1, 가격2, 가격3],
    "resistance_levels": [가격1, 가격2, 가격3]
  }},
  "volume_pattern": {{
    "trend": "증가" | "감소" | "보합",
    "price_volume_relationship": "설명"
  }},
  "technical_signals": {{
    "rsi_signal": "과매수" | "과매도" | "중립",
    "macd_signal": "매수" | "매도" | "중립",
    "bollinger_signal": "상단돌파" | "하단돌파" | "중립"
  }},
  "short_term_outlook": "1-2주 전망",
  "trading_strategy": "기술적 관점 매매 전략",
  "confidence": 1-5
}}
"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke(prompt)
            analysis = safe_json_parse(response.content, "Research/TechnicalAnalyst")

            if not isinstance(analysis, dict):
                analysis = {}

            # 기본값 설정
            trend = analysis.get("trend", "횡보")
            confidence = int(_coerce_number(analysis.get("confidence"), 3))
            confidence = max(1, min(confidence, 5))

            summary = f"기술적 분석 완료: {trend}, 신뢰도 {confidence}/5"

            # 주요 신호 추출
            signals = []
            tech_signals = analysis.get("technical_signals", {})
            if tech_signals.get("rsi_signal") in ["과매수", "과매도"]:
                signals.append(f"RSI {tech_signals['rsi_signal']}")
            if tech_signals.get("macd_signal") in ["매수", "매도"]:
                signals.append(f"MACD {tech_signals['macd_signal']}")

            ma_analysis = analysis.get("moving_average_analysis", {})
            if ma_analysis.get("golden_cross"):
                signals.append("골든크로스 발생")
            elif ma_analysis.get("death_cross"):
                signals.append("데드크로스 발생")

            message = AIMessage(
                content=(
                    f"기술적 분석 결과:\n"
                    f"- 추세: {trend}\n"
                    f"- 신호: {', '.join(signals) if signals else '특이사항 없음'}\n"
                    f"- 단기 전망: {analysis.get('short_term_outlook', 'N/A')}"
                )
            )

            payload: ResearchState = {
                "technical_analysis": analysis,
                "messages": [message],
            }
            return _task_complete(state, task, summary, payload)

        except Exception as exc:
            logger.error(
                "❌ [Research/TechnicalAnalyst] 실패 (시도 %s/%s): %s",
                attempt + 1,
                max_retries,
                exc,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            raise RuntimeError(f"기술적 분석 실패: {exc}") from exc


async def trading_flow_analyst_worker_node(state: ResearchState) -> ResearchState:
    """
    거래 동향 분석 전문가 (Trading Flow Analyst)

    역할:
    - 투자자별(기관/외국인/개인) 거래 동향 분석
    - 순매수/순매도 추이 분석
    - 주가와의 상관관계 분석
    - 수급 전망
    """
    if state.get("error"):
        return state

    task = state.get("current_task")
    stock_code = state.get("stock_code") or await _extract_stock_code(state)

    logger.info("💹 [Research/TradingFlowAnalyst] 거래 동향 분석 시작: %s", stock_code)

    # 데이터 추출
    investor_data = state.get("investor_trading_data") or {}
    price_data = state.get("price_data") or {}

    if not investor_data:
        logger.warning("⚠️ [Research/TradingFlowAnalyst] 투자자 거래 데이터 부족")
        return _task_complete(
            state,
            task,
            "투자자 거래 데이터 부족으로 분석 생략",
            {
                "trading_flow_analysis": None,
                "messages": [AIMessage(content="투자자 거래 데이터가 부족하여 분석을 생략합니다.")],
            },
        )

    llm = get_llm(max_tokens=2000, temperature=0.2)

    current_price = price_data.get("latest_close", 0)

    prompt = f"""당신은 거래 동향 분석 전문가입니다. 투자 주체별 거래 동향을 분석하고 수급 전망을 제시하세요.

## 종목 정보
- 종목코드: {stock_code}
- 현재가: {current_price:,}원

## 투자자별 거래 동향 
{_dumps(investor_data, indent=2)} 

## 분석 항목
1. **외국인 투자자**:
   - 최근 30일 순매수/순매도 추이
   - 주가와의 상관관계
   - 외국인 보유 비중 변화 (가능한 경우)
2. **기관 투자자**:
   - 최근 30일 순매수/순매도 추이
   - 주가와의 상관관계
   - 특이 동향 (대규모 매수/매도 등)
3. **개인 투자자**:
   - 순매수/순매도 추이
   - 외국인/기관과의 반대 매매 여부
4. **종합 수급 분석**:
   - 누가 주도하고 있는가?
   - 수급 강도 (강함/약함)
   - 향후 수급 전망

JSON 형식으로 답변하세요:
{{
  "foreign_investor": {{
    "trend": "순매수" | "순매도" | "보합",
    "strength": 1-5,
    "correlation_with_price": "양의 상관관계" | "음의 상관관계" | "무관",
    "net_amount": 0,
    "analysis": "상세 설명"
  }},
  "institutional_investor": {{
    "trend": "순매수" | "순매도" | "보합",
    "strength": 1-5,
    "correlation_with_price": "양의 상관관계" | "음의 상관관계" | "무관",
    "net_amount": 0,
    "analysis": "상세 설명"
  }},
  "individual_investor": {{
    "trend": "순매수" | "순매도" | "보합",
    "opposite_trading": true | false,
    "analysis": "상세 설명"
  }},
  "supply_demand_analysis": {{
    "leading_investor": "외국인" | "기관" | "개인" | "혼재",
    "supply_strength": "강함" | "약함" | "보통",
    "outlook": "긍정적" | "부정적" | "중립",
    "forecast": "향후 수급 전망"
  }},
  "confidence": 1-5
}}
"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke(prompt)
            analysis = safe_json_parse(response.content, "Research/TradingFlowAnalyst")

            if not isinstance(analysis, dict):
                analysis = {}

            confidence = int(_coerce_number(analysis.get("confidence"), 3))
            confidence = max(1, min(confidence, 5))

            supply_demand = analysis.get("supply_demand_analysis", {})
            outlook = supply_demand.get("outlook", "중립")
            leading = supply_demand.get("leading_investor", "혼재")

            summary = f"거래 동향 분석 완료: {leading} 주도, 수급 {outlook}"

            foreign = analysis.get("foreign_investor", {})
            institutional = analysis.get("institutional_investor", {})

            message = AIMessage(
                content=(
                    f"거래 동향 분석 결과:\n"
                    f"- 외국인: {foreign.get('trend', 'N/A')}\n"
                    f"- 기관: {institutional.get('trend', 'N/A')}\n"
                    f"- 주도 세력: {leading}\n"
                    f"- 수급 전망: {outlook}"
                )
            )

            payload: ResearchState = {
                "trading_flow_analysis": analysis,
                "messages": [message],
            }
            return _task_complete(state, task, summary, payload)

        except Exception as exc:
            logger.error(
                "❌ [Research/TradingFlowAnalyst] 실패 (시도 %s/%s): %s",
                attempt + 1,
                max_retries,
                exc,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            raise RuntimeError(f"거래 동향 분석 실패: {exc}") from exc


async def information_analyst_worker_node(state: ResearchState) -> ResearchState:
    """
    정보 분석 전문가 (Information Analyst)

    역할:
    - 뉴스 및 이슈 트렌드 분석
    - 호재/악재 식별
    - 시장 센티먼트 분석

    Note: 현재는 기존 데이터를 기반으로 분석하며,
    향후 뉴스 API 연동 시 실제 뉴스 크롤링 추가 예정
    """
    if state.get("error"):
        return state

    task = state.get("current_task")
    stock_code = state.get("stock_code") or await _extract_stock_code(state)

    logger.info("📰 [Research/InformationAnalyst] 정보 분석 시작: %s", stock_code)

    # 기업 정보 추출
    company_data = state.get("company_data") or {}
    company_info = company_data.get("info", {})
    company_name = company_info.get("corp_name", f"종목코드 {stock_code}")

    # 컨텍스트 구성
    context = {
        "stock_code": stock_code,
        "company_name": company_name,
        "market_index": state.get("market_index_data"),
        "market_cap": state.get("market_cap_data"),
        "fundamental": state.get("fundamental_data"),
        "price_trend": state.get("price_data", {}).get("latest_close"),
    }

    llm = get_llm(max_tokens=2000, temperature=0.3)

    prompt = f"""당신은 정보 분석 전문가입니다. 기업 정보와 시장 맥락을 분석하여 투자 관련 인사이트를 제공하세요.

## 기업 정보
- 기업명: {company_name}
- 종목코드: {stock_code}

## 시장 컨텍스트 
{_dumps(context, indent=2)} 

## 분석 항목
1. **기업 개요 및 사업 특성**:
   - 주요 사업 분야
   - 시장 내 위치
2. **최근 이슈 및 트렌드** (데이터 기반 추론):
   - 주가 변동성에서 추론 가능한 이슈
   - 업종 트렌드
3. **호재/악재 요인**:
   - 긍정적 요인
   - 부정적 요인
4. **시장 센티먼트**:
   - 전반적 투자 심리
   - 리스크 레벨

Note: 뉴스 API 연동 전이므로, 기존 데이터(주가, 거래량, 시총 등)를 기반으로 추론하세요.

JSON 형식으로 답변하세요:
{{
  "company_overview": "기업 개요",
  "business_characteristics": "사업 특성",
  "positive_factors": ["호재 요인 리스트"],
  "negative_factors": ["악재 요인 리스트"],
  "market_sentiment": "긍정적" | "부정적" | "중립",
  "risk_level": "높음" | "중간" | "낮음",
  "key_themes": ["주요 테마/트렌드"],
  "investment_implications": "투자 시사점",
  "confidence": 1-5
}}
"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke(prompt)
            analysis = safe_json_parse(response.content, "Research/InformationAnalyst")

            if not isinstance(analysis, dict):
                analysis = {}

            confidence = int(_coerce_number(analysis.get("confidence"), 3))
            confidence = max(1, min(confidence, 5))

            sentiment = analysis.get("market_sentiment", "중립")
            risk_level = analysis.get("risk_level", "중간")

            summary = f"정보 분석 완료: 센티먼트 {sentiment}, 리스크 {risk_level}"

            positive = analysis.get("positive_factors", [])
            negative = analysis.get("negative_factors", [])

            message = AIMessage(
                content=(
                    f"정보 분석 결과:\n"
                    f"- 시장 센티먼트: {sentiment}\n"
                    f"- 리스크 레벨: {risk_level}\n"
                    f"- 주요 호재: {', '.join(positive[:2]) if positive else '없음'}\n"
                    f"- 주요 악재: {', '.join(negative[:2]) if negative else '없음'}"
                )
            )

            payload: ResearchState = {
                "information_analysis": analysis,
                "messages": [message],
            }
            return _task_complete(state, task, summary, payload)

        except Exception as exc:
            logger.error(
                "❌ [Research/InformationAnalyst] 실패 (시도 %s/%s): %s",
                attempt + 1,
                max_retries,
                exc,
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            raise RuntimeError(f"정보 분석 실패: {exc}") from exc


async def synthesis_node(state: ResearchState) -> ResearchState:
    """
    최종 의견 통합 (Research Synthesizer)
    - Technical Analyst 결과
    - Trading Flow Analyst 결과
    - Information Analyst 결과
    - Bull/Bear 분석 결과
    - Macro 분석 결과
    를 종합하여 최종 투자 의견 생성
    """
    if state.get("error"):
        return state

    logger.info("🤝 [Research/Synthesis] 최종 의견 통합 시작 ")

    # 기존 분석 결과
    bull = state.get("bull_analysis") or {}
    bear = state.get("bear_analysis") or {}
    price_data = state.get("price_data") or {}
    technical_indicators = state.get("technical_indicators") or {}
    fundamental = state.get("fundamental_data") or {}
    investor = state.get("investor_trading_data") or {}
    market_cap = state.get("market_cap_data") or {}
    stock_code = state.get("stock_code") or "N/A"

    # 새로운 전문가 분석 결과
    technical_analysis = state.get("technical_analysis") or {}
    trading_flow_analysis = state.get("trading_flow_analysis") or {}
    information_analysis = state.get("information_analysis") or {}
    macro_analysis = state.get("macro_analysis") or {}

    current_price = price_data.get("latest_close") or 0
    bull_target = _coerce_number(bull.get("target_price"), current_price * 1.1)
    bear_target = _coerce_number(bear.get("downside_target"), current_price * 0.95)
    bull_conf = int(_coerce_number(bull.get("confidence"), 3))
    bear_conf = int(_coerce_number(bear.get("confidence"), 3))
    bull_conf = max(1, min(bull_conf, 5))
    bear_conf = max(1, min(bear_conf, 5))

    # 1. Technical Analyst 결과 반영
    tech_trend = technical_analysis.get("trend", technical_indicators.get("overall_trend", "중립"))
    tech_trend_strength = technical_analysis.get("trend_strength", 3)

    if tech_trend in ["상승추세", "강세"]:
        bull_conf = min(bull_conf + int(tech_trend_strength / 2), 5)
    elif tech_trend in ["하락추세", "약세"]:
        bear_conf = min(bear_conf + int(tech_trend_strength / 2), 5)

    # 기술적 신호 반영
    tech_signals = technical_analysis.get("technical_signals", {})
    if tech_signals.get("rsi_signal") == "과매도":
        bull_conf = min(bull_conf + 1, 5)
    elif tech_signals.get("rsi_signal") == "과매수":
        bear_conf = min(bear_conf + 1, 5)

    if tech_signals.get("macd_signal") == "매수":
        bull_conf = min(bull_conf + 1, 5)
    elif tech_signals.get("macd_signal") == "매도":
        bear_conf = min(bear_conf + 1, 5)

    # 이동평균선 분석 반영
    ma_analysis = technical_analysis.get("moving_average_analysis", {})
    if ma_analysis.get("golden_cross"):
        bull_conf = min(bull_conf + 1, 5)
    elif ma_analysis.get("death_cross"):
        bear_conf = min(bear_conf + 1, 5)

    # 2. Trading Flow Analyst 결과 반영
    supply_demand = trading_flow_analysis.get("supply_demand_analysis", {})
    supply_outlook = supply_demand.get("outlook", "중립")

    if supply_outlook == "긍정적":
        bull_conf = min(bull_conf + 1, 5)
    elif supply_outlook == "부정적":
        bear_conf = min(bear_conf + 1, 5)

    # 외국인/기관 동향 반영
    foreign_investor = trading_flow_analysis.get("foreign_investor", {})
    institutional_investor = trading_flow_analysis.get("institutional_investor", {})

    if foreign_investor.get("trend") == "순매수" and institutional_investor.get("trend") == "순매수":
        bull_conf = min(bull_conf + 1, 5)
    elif foreign_investor.get("trend") == "순매도" and institutional_investor.get("trend") == "순매도":
        bear_conf = min(bear_conf + 1, 5)

    # 3. Information Analyst 결과 반영
    market_sentiment = information_analysis.get("market_sentiment", "중립")
    risk_level = information_analysis.get("risk_level", "중간")

    if market_sentiment == "긍정적":
        bull_conf = min(bull_conf + 1, 5)
    elif market_sentiment == "부정적":
        bear_conf = min(bear_conf + 1, 5)

    if risk_level == "높음":
        bear_conf = min(bear_conf + 1, 5)
    elif risk_level == "낮음":
        bull_conf = min(bull_conf + 1, 5)

    # 4. Macro 분석 결과 반영
    if macro_analysis:
        macro_sentiment = macro_analysis.get("analysis", {}).get("overall_macro_sentiment", "중립")
        if macro_sentiment == "긍정적":
            bull_conf = min(bull_conf + 1, 5)
        elif macro_sentiment == "부정적":
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

    rsi_signal = (
        tech_signals.get("rsi_signal")
        or technical_indicators.get("rsi_signal")
        or technical_indicators.get("rsi", {}).get("signal")
        or "중립"
    )

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

    # Technical Analyst 요약
    technical_summary = {
        "trend": tech_trend,
        "trend_strength": tech_trend_strength,
        "signals": tech_signals,
        "moving_average": ma_analysis,
        "short_term_outlook": technical_analysis.get("short_term_outlook"),
        "support_resistance": technical_analysis.get("support_resistance"),
    }

    # Trading Flow Analyst 요약
    trading_flow_summary = {
        "foreign": foreign_investor.get("trend", "N/A"),
        "institutional": institutional_investor.get("trend", "N/A"),
        "leading_investor": supply_demand.get("leading_investor", "혼재"),
        "outlook": supply_outlook,
    }

    # Information Analyst 요약
    information_summary = {
        "sentiment": market_sentiment,
        "risk_level": risk_level,
        "positive_factors": information_analysis.get("positive_factors", []),
        "negative_factors": information_analysis.get("negative_factors", []),
        "key_themes": information_analysis.get("key_themes", []),
    }

    # Macro Analyst 요약
    macro_summary = {}
    if macro_analysis:
        macro_data = macro_analysis.get("raw_data", {})
        macro_result = macro_analysis.get("analysis", {})
        macro_summary = {
            "base_rate": macro_data.get("base_rate"),
            "base_rate_trend": macro_data.get("base_rate_trend"),
            "overall_sentiment": macro_result.get("overall_macro_sentiment"),
            "summary": macro_result.get("summary"),
        }

    consensus = {
        "recommendation": recommendation,
        "target_price": target_price,
        "current_price": int(current_price),
        "upside_potential": f"{upside:.1%}" if current_price else "N/A",
        "confidence": confidence,
        "bull_case": bull.get("positive_factors", []),
        "bear_case": bear.get("risk_factors", []),
        # 전문가 분석 요약
        "technical_summary": technical_summary,
        "trading_flow_summary": trading_flow_summary,
        "information_summary": information_summary,
        "macro_summary": macro_summary,
        # 기존 요약
        "fundamental_summary": fundamental_summary,
        "investor_summary": investor_summary,
        "market_cap_trillion": market_cap_trillion,
        "summary": (
            f"{stock_code} - {recommendation} (목표가: {target_price:,}원, "
            f"펀더멘털: {valuation_status}, 기술적 추세: {tech_trend}, "
            f"수급: {supply_outlook}, 센티먼트: {market_sentiment})"
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

    # Investment Dashboard 생성 (Claude 4.x 프롬프트 사용)
    from src.prompts.templates.investment_dashboard import build_dashboard_prompt
    from src.prompts import add_formatting_guidelines

    try:
        llm = get_llm(temperature=0, max_tokens=3000)

        # 분석 결과 정리
        analysis_results = {
            "Bull Analysis": bull.get("analysis", "N/A"),
            "Bear Analysis": bear.get("analysis", "N/A"),
            "Technical Analysis": technical_analysis.get("analysis", "N/A"),
            "Trading Flow Analysis": trading_flow_analysis.get("analysis", "N/A"),
            "Information Analysis": information_analysis.get("analysis", "N/A"),
            "Macro Analysis": macro_analysis.get("analysis", {}).get("summary", "N/A") if macro_analysis else "N/A",
        }

        # Dashboard 프롬프트 생성
        dashboard_prompt = build_dashboard_prompt(
            stock_name=f"{stock_code} (종목코드: {stock_code})",
            analysis_results=analysis_results,
        )

        # LLM 호출하여 Dashboard 생성
        dashboard_response = await llm.ainvoke(dashboard_prompt)
        dashboard_content = dashboard_response.content

        logger.info("✅ [Research/Synthesis] Investment Dashboard 생성 완료")

    except Exception as exc:
        logger.warning("⚠️ [Research/Synthesis] Dashboard 생성 실패, 기본 포맷 사용: %s", exc)

        # Fallback: 기존 간단한 텍스트 포맷
        dashboard_content = (
            f"# {stock_code} 투자 분석 요약\n\n"
            f"## 💭 투자 의견\n"
            f"**추천**: {recommendation}\n"
            f"**목표가**: {target_price:,}원 (현재가: {current_price:,}원)\n"
            f"**상승여력**: {consensus['upside_potential']}\n"
            f"**신뢰도**: {confidence}/5\n\n"
            f"## 📊 핵심 지표\n"
            f"- 펀더멘털: {per_text}, {pbr_text} ({valuation_status})\n"
            f"- 기술적 추세: {tech_trend} (강도: {tech_trend_strength}/5)\n"
            f"- 수급 전망: {supply_outlook}\n"
            f"- 시장 센티먼트: {market_sentiment}\n\n"
            f"## 🎯 투자 시나리오\n"
            f"### Bull Case (확신도: {bull_conf}/5)\n"
            + "\n".join([f"- {factor}" for factor in bull.get("positive_factors", [])[:3]]) + "\n\n"
            f"### Bear Case (확신도: {bear_conf}/5)\n"
            + "\n".join([f"- {factor}" for factor in bear.get("risk_factors", [])[:3]]) + "\n\n"
            f"## 📈 투자주체 동향\n"
            f"- 외국인: {foreign_trend}\n"
            f"- 기관: {institution_trend}\n"
        )

    message = AIMessage(content=dashboard_content)

    notes = list(state.get("task_notes") or [])
    notes.append(f"최종 의견 {recommendation} (신뢰도 {confidence})")

    completed = list(state.get("completed_tasks") or [])
    completed.append(
        {
            "id": "synthesis",
            "worker": "synthesis",
            "description": "최종 의견 통합 (Investment Dashboard)",
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
