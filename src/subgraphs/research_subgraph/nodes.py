"""
Research Agent 노드 함수들 (Deep Agent 스타일)
"""
import asyncio
import json
import logging
import re
import uuid
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Interrupt

from src.utils.llm_factory import get_research_llm as get_llm
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
from .tools import (
    get_stock_price_tool,
    get_stock_by_name_tool,
    get_fundamental_data_tool,
    get_market_cap_data_tool,
    get_market_index_tool,
    search_corp_code_tool,
    get_financial_statement_tool,
    get_company_info_tool,
    get_macro_summary_tool,
)

logger = logging.getLogger(__name__)

ALLOWED_WORKERS = {"data", "bull", "bear", "macro", "technical", "trading_flow"}


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

                # 종목명으로 코드 검색 (Tool 사용)
                markets = ["KOSPI", "KOSDAQ", "KONEX"]
                for market in markets:
                    try:
                        code = await get_stock_by_name_tool.ainvoke({"stock_name": stock_name, "market": market})
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
                worker = "data"  # fallback
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
    worker_name: str,
    summary: str,
    extra: Dict[str, Any],
) -> ResearchState:
    """
    Worker 작업 완료 후 상태 업데이트 (병렬 실행 안전)

    Args:
        state: 현재 상태
        worker_name: worker 이름 (예: "data_worker")
        summary: 작업 요약
        extra: 추가 상태 업데이트

    Note:
        completed_tasks와 task_notes는 Annotated[List, add]로 정의되어
        병렬 실행 시 자동으로 리스트가 병합됩니다.
        따라서 기존 리스트에 append하지 않고 새 항목만 반환합니다.
    """
    # pending_tasks에서 해당 worker task 찾기
    pending_tasks = state.get("pending_tasks") or []
    task = None
    for t in pending_tasks:
        if t.get("worker") == worker_name.replace("_worker", "").replace("_analyst", ""):
            task = t
            break

    # 새로 추가할 항목만 생성 (병렬 실행 시 자동 병합됨)
    new_completed = []
    new_notes = []

    if task:
        new_completed.append({**task, "status": "done", "summary": summary})
    if summary:
        new_notes.append(summary)

    update: ResearchState = {
        "completed_tasks": new_completed,
        "task_notes": new_notes,
    }
    update.update(extra)
    return update


def _perspectives_to_workers(perspectives: List[str]) -> List[str]:
    """
    UI Perspectives → Workers 변환

    Args:
        perspectives: UI에서 선택한 관점 리스트

    Returns:
        실행할 worker 리스트 (중복 제거됨)
    """
    from src.constants.analysis_depth import PERSPECTIVE_TO_WORKER_MAPPING

    workers = []
    for perspective in perspectives:
        mapped_workers = PERSPECTIVE_TO_WORKER_MAPPING.get(perspective, [])
        workers.extend(mapped_workers)

    # 중복 제거, 순서 유지
    seen = set()
    unique_workers = []
    for w in workers:
        if w not in seen:
            seen.add(w)
            unique_workers.append(w)

    return unique_workers


def _apply_scope_limit(workers: List[str], scope: str) -> List[str]:
    """
    Scope에 따라 worker 개수 제한

    Args:
        workers: worker 리스트
        scope: 분석 범위 ("key_points" | "balanced" | "wide_coverage")

    Returns:
        제한된 worker 리스트
    """
    from src.constants.analysis_depth import get_scope_config

    scope_config = get_scope_config(scope)
    limit = scope_config["max_workers"]

    # 우선순위: data > technical > macro > trading_flow > bull > bear
    priority = ["data", "technical", "macro", "trading_flow", "bull", "bear"]

    sorted_workers = []
    for p in priority:
        if p in workers:
            sorted_workers.append(p)

    return sorted_workers[:limit]


async def _refine_plan_with_user_input(
    original_plan: Dict[str, Any],
    user_input: str,
    stock_code: Optional[str],
    query: Optional[str],
) -> Dict[str, Any]:
    """
    사용자 입력을 해석하여 분석 계획 재조정

    Args:
        original_plan: 원본 계획 (depth, scope, perspectives)
        user_input: 사용자의 자유 텍스트 입력
        stock_code: 종목 코드
        query: 원본 쿼리

    Returns:
        재조정된 계획 (depth, scope, perspectives)
    """
    from src.utils.llm_factory import get_portfolio_risk_llm as get_llm
    from src.prompts import safe_json_parse

    llm = get_llm(temperature=0, max_tokens=1500)

    prompt = f"""당신은 주식 투자 분석 계획을 재조정하는 전문가입니다.

**원본 요청:** {query}
**종목코드:** {stock_code}

**AI가 추천한 계획:**
- Depth: {original_plan.get('depth')}
- Scope: {original_plan.get('scope')}
- Perspectives: {original_plan.get('perspectives')}

**사용자의 추가 요청:**
"{user_input}"

사용자 요청을 반영하여 분석 계획을 재조정하세요.

**Depth (분석 깊이):**
- brief: 빠른 분석 (10-20초)
- detailed: 표준 분석 (30-45초)
- comprehensive: 종합 분석 (60-90초)

**Scope (분석 범위):**
- key_points: 핵심만 (최대 3개 관점)
- balanced: 균형잡힌 (최대 5개 관점)
- wide_coverage: 광범위 (최대 6개 관점)

**Perspectives (분석 관점):**
- macro: 거시경제 분석
- fundamental: 재무제표 및 기업 정보
- technical: 기술적 분석
- flow: 거래 동향 (외국인/기관)
- strategy: 투자 전략 (bull/bear 시나리오)
- bull_case: 강세 시나리오만
- bear_case: 약세 시나리오만

**해석 예시:**
- "더 깊게" → depth를 comprehensive로
- "간단하게" → depth를 brief로
- "반도체 사업부에 집중" → fundamental 추가, depth는 detailed 이상
- "기술적 지표만" → perspectives를 ["technical"]로
- "시장 전망 포함" → macro 추가

JSON 형식으로만 답변하세요:
{{
  "depth": "detailed",
  "scope": "balanced",
  "perspectives": ["fundamental", "technical"],
  "reasoning": "사용자가 요청한 이유 설명"
}}
"""

    try:
        response = await llm.ainvoke(prompt)
        refined_plan = safe_json_parse(response.content, "Research/PlanRefiner")

        logger.info("✅ [Research/PlanRefiner] 계획 재조정 성공: %s", refined_plan.get("reasoning", ""))

        return {
            "depth": refined_plan.get("depth", original_plan.get("depth")),
            "scope": refined_plan.get("scope", original_plan.get("scope")),
            "perspectives": refined_plan.get("perspectives", original_plan.get("perspectives")),
        }

    except Exception as exc:
        logger.warning("⚠️ [Research/PlanRefiner] 계획 재조정 실패, 원본 유지: %s", exc)
        return original_plan


async def planner_node(state: ResearchState) -> ResearchState:
    """
    Planner Node - HITL 패턴 구현

    경로 1: 첫 실행 - UserProfile + LLM 기반 계획 수립 후 INTERRUPT
    경로 2: 승인 후 재개 - perspectives를 workers로 변환하여 pending_tasks 생성
    """

    # ========== 경로 2: 승인 후 재개 (두 번째 실행) ==========
    if state.get("plan_approved"):
        logger.info("✅ [Research/Planner] 사용자 승인 완료, 분석 시작")

        # 사용자 수정사항 처리
        modifications = state.get("user_modifications")

        if modifications:
            logger.info("✏️ [Research/Planner] 사용자 수정사항 반영: %s", modifications)

            # 1. 구조화된 수정사항 적용 (depth, scope, perspectives)
            depth = modifications.get("depth", state.get("depth", "detailed"))
            scope = modifications.get("scope", state.get("scope", "balanced"))
            perspectives = modifications.get("perspectives", state.get("perspectives", []))

            # 2. 자유 텍스트 입력 처리 (user_input)
            user_input = modifications.get("user_input")
            if user_input:
                logger.info("💬 [Research/Planner] 사용자 입력 해석: %s", user_input[:100])

                # LLM을 사용하여 사용자 입력 해석 및 plan 재조정
                refined_plan = await _refine_plan_with_user_input(
                    original_plan={
                        "depth": depth,
                        "scope": scope,
                        "perspectives": perspectives,
                    },
                    user_input=user_input,
                    stock_code=state.get("stock_code"),
                    query=state.get("query"),
                )

                # 해석된 결과로 plan 업데이트
                depth = refined_plan.get("depth", depth)
                scope = refined_plan.get("scope", scope)
                perspectives = refined_plan.get("perspectives", perspectives)

                logger.info("🔄 [Research/Planner] 재조정된 plan: depth=%s, scope=%s, perspectives=%s",
                           depth, scope, perspectives)
        else:
            # 수정 없음 - 기존 state의 plan 사용
            depth = state.get("depth", "detailed")
            scope = state.get("scope", "balanced")
            perspectives = state.get("perspectives", [])

        # perspectives → workers 변환
        workers = _perspectives_to_workers(perspectives)

        # scope에 따라 worker 개수 제한
        workers = _apply_scope_limit(workers, scope)

        # pending_tasks 생성
        pending_tasks = []
        for worker in workers:
            pending_tasks.append({
                "id": f"task_{worker}",
                "worker": worker,
                "description": f"{worker} 분석",
            })

        logger.info(
            f"🚀 [Research/Planner] 실행할 workers: {workers} (총 {len(workers)}개)"
        )

        return {
            "depth": depth,
            "scope": scope,
            "perspectives": perspectives,
            "pending_tasks": pending_tasks,
            "completed_tasks": [],
            "task_notes": [],
            "messages": [AIMessage(content="분석을 시작합니다...")],
        }

    # ========== 경로 1: 첫 실행 (계획 수립 및 INTERRUPT) ==========

    query = state.get("query") or "종목 분석"
    stock_code = await _extract_stock_code(state)

    logger.info("🧠 [Research/Planner] 계획 수립 시작: %s", query[:50])

    # 1. UserProfile + LLM 기반 기본 계획 수립
    user_profile = state.get("user_profile") or {}

    llm = get_llm(temperature=0, max_tokens=1200)
    prompt = f"""당신은 주식 투자 분석 계획을 수립하는 전문가입니다.

사용자 요청: {query}
종목코드: {stock_code}

다음 중에서 적절한 분석 설정을 추천하세요:

**Depth (분석 깊이):**
- brief: 빠른 분석 (10-20초)
- detailed: 표준 분석 (30-45초) - 일반적인 선택
- comprehensive: 종합 분석 (60-90초)

**Scope (분석 범위):**
- key_points: 핵심만 (최대 3개 관점)
- balanced: 균형잡힌 (최대 5개 관점) - 일반적인 선택
- wide_coverage: 광범위 (최대 6개 관점)

**Perspectives (분석 관점 - 복수 선택):**
- macro: 거시경제 분석
- fundamental: 재무제표 및 기업 정보
- technical: 기술적 분석
- flow: 거래 동향 (외국인/기관)
- strategy: 투자 전략 (bull/bear 시나리오)
- bull_case: 강세 시나리오만
- bear_case: 약세 시나리오만

JSON 형식으로만 답변하세요:
{{
  "depth": "detailed",
  "scope": "balanced",
  "perspectives": ["fundamental", "technical"]
}}
"""

    try:
        response = await llm.ainvoke(prompt)
        plan = safe_json_parse(response.content, "Research/Planner")

        recommended_depth = plan.get("depth", "detailed")
        recommended_scope = plan.get("scope", "balanced")
        recommended_perspectives = plan.get("perspectives", ["fundamental", "technical"])

    except Exception as exc:
        logger.warning("⚠️ [Research/Planner] LLM 계획 실패, 기본값 사용: %s", exc)
        recommended_depth = "detailed"
        recommended_scope = "balanced"
        recommended_perspectives = ["fundamental", "technical"]

    # 2. intervention_required 체크
    intervention_required = state.get("intervention_required", False)

    if not intervention_required:
        # 분석 단계는 자동 진행 (매매만 HITL)
        logger.info("✅ [Research/Planner] 분석 자동 진행 (intervention_required=False)")

        workers = _perspectives_to_workers(recommended_perspectives)
        workers = _apply_scope_limit(workers, recommended_scope)

        pending_tasks = []
        for worker in workers:
            pending_tasks.append({
                "id": f"task_{worker}",
                "worker": worker,
                "description": f"{worker} 분석",
            })

        from src.constants.analysis_depth import get_depth_config

        depth_config = get_depth_config(recommended_depth)

        return {
            "plan_approved": True,
            "depth": recommended_depth,
            "scope": recommended_scope,
            "perspectives": recommended_perspectives,
            "method": "both",
            "pending_tasks": pending_tasks,
            "completed_tasks": [],
            "task_notes": [],
            "messages": [AIMessage(content=f"{depth_config['name']} 분석을 시작합니다.")],
            "stock_code": stock_code,
        }

    # 3. INTERRUPT 발생 (사용자 승인 대기) - intervention_required=True
    from src.constants.analysis_depth import get_depth_config

    depth_config = get_depth_config(recommended_depth)

    approval_id = str(uuid.uuid4())

    logger.info("⚠️ [Research/Planner] INTERRUPT 발생 - 사용자 승인 대기")

    # Interrupt를 발생시키기 전에 State 업데이트
    # (재개 시 사용할 기본값 저장)
    state_update: ResearchState = {
        "depth": recommended_depth,
        "scope": recommended_scope,
        "perspectives": recommended_perspectives,
        "method": "both",
        "plan_approval_id": approval_id,
        "stock_code": stock_code,
        "messages": [AIMessage(content="분석 계획을 수립했습니다. 승인을 기다립니다...")],
    }

    # Interrupt payload 생성
    interrupt_payload = {
        "type": "research_plan_approval",
        "approval_id": approval_id,
        "stock_code": stock_code,
        "query": query,
        "plan": {
            "depth": recommended_depth,
            "depth_name": depth_config["name"],
            "scope": recommended_scope,
            "perspectives": recommended_perspectives,
            "method": "both",
            "estimated_time": depth_config["estimated_time"],
        },
        "options": {
            "depths": ["brief", "detailed", "comprehensive"],
            "scopes": ["key_points", "balanced", "wide_coverage"],
            "perspectives": ["macro", "fundamental", "technical", "flow",
                           "strategy", "bull_case", "bear_case"],
            "methods": ["qualitative", "quantitative", "both"],
        },
        "message": "다음과 같이 분석할 예정입니다. 진행하시겠습니까?",
    }

    # State 업데이트 후 Interrupt 발생
    # Note: LangGraph는 interrupt 전 return된 state를 저장함
    raise Interrupt(state_update, value=interrupt_payload)


async def data_worker_node(state: ResearchState) -> ResearchState:
    stock_code = await _extract_stock_code(state)
    request_id = state.get("request_id", "research-agent")

    logger.info("📊 [Research/Data] 데이터 수집 시작: %s", stock_code)

    try:
        # 분석 깊이에 따라 주가 데이터 기간 동적 설정
        analysis_depth = state.get("analysis_depth", "standard")
        days_map = {
            "quick": 60,            # 빠른 분석 (2개월)
            "standard": 180,        # 표준 분석 (6개월)
            "comprehensive": 365,   # 종합 분석 (1년)
        }
        days = days_map.get(analysis_depth, 180)

        # Tool을 사용하여 주가 데이터 조회
        price_result = await get_stock_price_tool.ainvoke({"stock_code": stock_code, "days": days})
        if "error" in price_result:
            raise RuntimeError(f"주가 데이터 조회 실패: {stock_code}")

        # Tool 결과에서 price_df 재구성 (기존 로직 유지를 위해)
        import pandas as pd
        price_df = pd.DataFrame(price_result["prices"])
        if "날짜" in price_df.columns:
            price_df = price_df.set_index("날짜")
        elif "Date" in price_df.columns:
            price_df = price_df.set_index("Date")

        price_data = price_result

        # Tool을 사용하여 DART 데이터 조회
        corp_code = await search_corp_code_tool.ainvoke({"stock_code": stock_code})
        if corp_code:
            # 재무제표 연도를 동적으로 설정 (상반기면 전년도, 하반기면 당해년도)
            current_year = datetime.now().year
            current_month = datetime.now().month
            # 1~6월: 전년도 재무제표, 7~12월: 당해년도 재무제표
            bsns_year = str(current_year - 1 if current_month < 7 else current_year)

            financial_statements = await get_financial_statement_tool.ainvoke({
                "corp_code": corp_code,
                "bsns_year": bsns_year
            })
            company_info = await get_company_info_tool.ainvoke({"corp_code": corp_code})
            financial_data = {
                "stock_code": stock_code,
                "corp_code": corp_code,
                "year": bsns_year,  # 동적 연도
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

        # Tool을 사용하여 기본 재무 데이터 조회
        fundamental_data = await get_fundamental_data_tool.ainvoke({"stock_code": stock_code})
        market_cap_data = await get_market_cap_data_tool.ainvoke({"stock_code": stock_code})
        # investor_trading_data 제거됨 (KIS API 미지원)

        try:
            # Tool을 사용하여 시장 지수 조회
            market_result = await get_market_index_tool.ainvoke({"index_name": "KOSPI", "days": 30})
            if "error" in market_result:
                raise RuntimeError(market_result["error"])

            market_df = pd.DataFrame(market_result["data"])
            if "날짜" in market_df.columns:
                market_df = market_df.set_index("날짜")
            elif "Date" in market_df.columns:
                market_df = market_df.set_index("Date")
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
        }
        summary = (
            f"{stock_code} 데이터 확보 완료 (종가 {cols['closing']:,}원, PER {cols['per']}, "
            f"PBR {cols['pbr']})"
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
            # investor_trading_data 제거됨 (KIS API 미지원)
            "technical_indicators": technical_indicators,
            "messages": [message],
            "request_id": request_id,
        }
        return _task_complete(state, "data", summary, payload)

    except Exception as exc:
        logger.error("❌ [Research/Data] 실패: %s", exc)
        return {
            "error": str(exc),
            "messages": [
                AIMessage(content=f"데이터 수집 중 오류가 발생했습니다: {exc}")
            ],
        }


async def bull_worker_node(state: ResearchState) -> ResearchState:
    if state.get("error"):
        return state

    stock_code = state.get("stock_code") or await _extract_stock_code(state)

    logger.info("🐂 [Research/Bull] 강세 분석 시작: %s", stock_code)

    llm = get_llm(max_tokens=2000, temperature=0.3)

    technical = state.get("technical_indicators") or {}
    market = state.get("market_index_data") or {}
    fundamental = state.get("fundamental_data") or {}
    market_cap = state.get("market_cap_data") or {}
    price = state.get("price_data") or {}
    financial_data = state.get("financial_data") or {}
    company_data = state.get("company_data") or {}

    # 업종 정보 추출
    company_info = company_data.get("info", {})
    corp_name = company_info.get("corp_name", "N/A")
    industry = company_info.get("induty_code", "N/A")
    financial_year = financial_data.get("year", "N/A")

    prompt = f"""당신은 낙관적 주식 애널리스트입니다. 다음 데이터를 분석하여 긍정적 시나리오를 제시하세요.

**기업 정보:**
- 종목코드: {stock_code}
- 기업명: {corp_name}
- 업종: {industry}

**현재 시장 데이터:**
- 현재가: {price.get('latest_close')}
- 시가총액: {market_cap.get('market_cap')}
- 주가 데이터 기간: {price.get('days')}일

**재무 데이터:**
- 재무제표 연도: {financial_year}
- 펀더멘털: {_dumps(fundamental)}

**기술적 분석:**
- 기술적 지표: {_dumps(technical)}
- 시장 지수: {_dumps(market)}

**분석 지침:**
해당 업종의 최신 시장 동향과 사이클을 고려하여 분석하세요.

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
            return _task_complete(state, "bull", summary, payload)
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

    stock_code = state.get("stock_code") or await _extract_stock_code(state)

    logger.info("🐻 [Research/Bear] 약세 분석 시작: %s", stock_code)

    llm = get_llm(max_tokens=2000, temperature=0.3)

    technical = state.get("technical_indicators") or {}
    market = state.get("market_index_data") or {}
    fundamental = state.get("fundamental_data") or {}
    market_cap = state.get("market_cap_data") or {}
    price = state.get("price_data") or {}
    financial_data = state.get("financial_data") or {}
    company_data = state.get("company_data") or {}

    # 업종 정보 추출
    company_info = company_data.get("info", {})
    corp_name = company_info.get("corp_name", "N/A")
    industry = company_info.get("induty_code", "N/A")
    financial_year = financial_data.get("year", "N/A")

    prompt = f"""당신은 보수적 주식 애널리스트입니다. 다음 데이터를 분석하여 리스크 시나리오를 제시하세요.

**기업 정보:**
- 종목코드: {stock_code}
- 기업명: {corp_name}
- 업종: {industry}

**현재 시장 데이터:**
- 현재가: {price.get('latest_close')}
- 시가총액: {market_cap.get('market_cap')}
- 주가 데이터 기간: {price.get('days')}일

**재무 데이터:**
- 재무제표 연도: {financial_year}
- 펀더멘털: {_dumps(fundamental)}

**기술적 분석:**
- 기술적 지표: {_dumps(technical)}
- 시장 지수: {_dumps(market)}

**분석 지침:**
해당 업종의 최신 시장 동향과 사이클을 고려하여 리스크를 분석하세요.

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
            return _task_complete(state, "bear", summary, payload)
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

    stock_code = state.get("stock_code") or await _extract_stock_code(state)

    logger.info("🌍 [Research/Macro] 거시경제 분석 시작: %s", stock_code)

    try:
        # 1. Tool을 사용하여 거시경제 데이터 수집
        macro_data = await get_macro_summary_tool.ainvoke({})
        if "error" in macro_data:
            raise RuntimeError(f"거시경제 데이터 조회 실패: {macro_data['error']}")

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
        return _task_complete(state, "macro", summary, payload)

    except Exception as exc:
        logger.error("❌ [Research/Macro] 실패: %s", exc)
        # 거시경제 분석 실패는 치명적이지 않으므로 계속 진행
        return _task_complete(
            state,
            "macro",
            "거시경제 분석 실패 (생략)",
            {
                "macro_analysis": None,
                "messages": [AIMessage(content=f"거시경제 분석을 건너뜁니다: {exc}")],
            }
        )


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

    stock_code = state.get("stock_code") or await _extract_stock_code(state)

    logger.info("📊 [Research/TechnicalAnalyst] 기술적 분석 시작: %s", stock_code)

    # 데이터 추출
    price_data = state.get("price_data") or {}
    technical = state.get("technical_indicators") or {}

    if not price_data or not technical:
        logger.warning("⚠️ [Research/TechnicalAnalyst] 기술적 데이터 부족")
        return _task_complete(
            state,
            "technical",
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
            return _task_complete(state, "technical", summary, payload)

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

    stock_code = state.get("stock_code") or await _extract_stock_code(state)

    logger.info("💹 [Research/TradingFlowAnalyst] 거래 동향 분석 시작: %s", stock_code)

    # 데이터 추출
    # investor_trading_data는 KIS API 미지원으로 항상 None
    investor_data = state.get("investor_trading_data") or {}
    price_data = state.get("price_data") or {}

    if not investor_data:
        logger.warning("⚠️ [Research/TradingFlowAnalyst] 투자자 거래 데이터 부족 (KIS API 미지원)")
        return _task_complete(
            state,
            "trading_flow",
            "투자자 거래 데이터 미지원으로 분석 생략",
            {
                "trading_flow_analysis": None,
                "messages": [AIMessage(content="투자자 거래 데이터는 현재 제공되지 않습니다.")],
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
            return _task_complete(state, "trading_flow", summary, payload)

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


async def synthesis_node(state: ResearchState) -> ResearchState:
    """
    최종 의견 통합 (Research Synthesizer)
    - Technical Analyst 결과
    - Trading Flow Analyst 결과
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
    market_cap = state.get("market_cap_data") or {}
    stock_code = state.get("stock_code") or "N/A"

    # 새로운 전문가 분석 결과
    technical_analysis = state.get("technical_analysis") or {}
    trading_flow_analysis = state.get("trading_flow_analysis") or {}
    macro_analysis = state.get("macro_analysis") or {}
    information_analysis = state.get("information_analysis") or {}

    # Information Analyst 결과 추출 (미구현 시 기본값)
    if not information_analysis:
        logger.warning("⚠️ [Research/Synthesis] Information Analyst 미실행 - 기본값 사용")
        market_sentiment = "중립"
        risk_level = "보통"
    else:
        market_sentiment = information_analysis.get("market_sentiment", "중립")
        risk_level = information_analysis.get("risk_level", "보통")

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

    # 3. Macro 분석 결과 반영
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

    # foreign_trend, institution_trend 제거 (investor_trading_data 더 이상 사용 불가)
    # investor_sentiment 계산 로직 제거

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

    # investor_summary 제거 (investor_trading_data 더 이상 사용 불가)

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
        # "investor_summary": investor_summary,  # 제거됨
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
            + "\n".join([f"- {factor}" for factor in bear.get("risk_factors", [])[:3]]) + "\n"
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
