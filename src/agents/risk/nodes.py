"""Risk Agent 노드 함수들.

ReAct 패턴: Intent Classifier → Planner → Task Router → Specialists → Final Assessment
"""
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage

from src.agents.risk.state import RiskState
from src.services import (
    PortfolioNotFoundError,
    portfolio_service,
)

logger = logging.getLogger(__name__)


# ==================== ReAct Pattern Nodes ====================

async def query_intent_classifier_node(state: RiskState) -> RiskState:
    """
    Query Intent Classifier (쿼리 의도 분석기) - LLM 완전 판단 기반

    리스크 분석 의도를 분석하여 분석 깊이와 집중 영역 결정
    """
    query = state.get("query", "")
    user_profile = state.get("portfolio_profile") or {}
    portfolio_data = state.get("portfolio_data") or {}

    logger.info("🎯 [Risk/IntentClassifier] 쿼리 의도 분석 시작: %s", query[:50] if query else "쿼리 없음")

    # Claude 4.x 프롬프트 사용
    from src.prompts.risk.intent_classifier import build_risk_intent_classifier_prompt
    from src.utils.llm import get_llm

    try:
        llm = get_llm(temperature=0, max_tokens=1000)

        # Intent Classifier 프롬프트 생성
        prompt = build_risk_intent_classifier_prompt(
            query=query or "포트폴리오 리스크 분석",
            user_profile=user_profile,
            portfolio_data=portfolio_data,
        )

        # LLM 호출
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts import parse_llm_json

        intent = parse_llm_json(response.content)

        # 결과 추출
        final_depth = intent.get("depth", "standard")
        focus_areas = intent.get("focus_areas", ["concentration", "market"])
        specialists = intent.get("specialists", [])
        reasoning = intent.get("reasoning", "LLM 기반 분류")

        logger.info(
            "✅ [Risk/IntentClassifier] LLM 판단 완료: %s | 집중 영역: %s",
            final_depth,
            focus_areas,
        )

        depth_reason = reasoning

    except Exception as exc:
        logger.warning("⚠️ [Risk/IntentClassifier] LLM 분류 실패, fallback 사용: %s", exc)

        # Fallback: 기본값
        final_depth = "standard"
        focus_areas = ["concentration", "market"]
        specialists = ["concentration_specialist", "market_risk_specialist"]
        depth_reason = "표준 리스크 분석"

    logger.info(
        "📋 [Risk/IntentClassifier] 최종 결정: %s | Specialists: %s",
        final_depth,
        specialists,
    )

    message = AIMessage(
        content=(
            f"리스크 분석 깊이: {final_depth}\\n"
            f"집중 영역: {', '.join(focus_areas)}\\n"
            f"이유: {depth_reason}"
        )
    )

    return {
        "analysis_depth": final_depth,
        "focus_areas": focus_areas,
        "depth_reason": depth_reason,
        "messages": [message],
    }


async def planner_node(state: RiskState) -> RiskState:
    """
    Smart Planner - 분석 깊이에 따라 동적으로 Specialist 선택

    Intent Classifier가 결정한 analysis_depth와 focus_areas를 기반으로
    필요한 Specialist만 선택하여 비용과 시간을 최적화합니다.
    """
    query = state.get("query", "")
    analysis_depth = state.get("analysis_depth", "standard")
    focus_areas = state.get("focus_areas") or []

    logger.info(
        "🧠 [Risk/Planner] Smart Planner 시작 | 깊이: %s | 집중 영역: %s",
        analysis_depth,
        focus_areas,
    )

    # Claude 4.x 프롬프트 사용
    from src.prompts.risk.intent_classifier import build_risk_planner_prompt
    from src.utils.llm import get_llm

    try:
        llm = get_llm(temperature=0, max_tokens=1000)

        # Planner 프롬프트 생성
        prompt = build_risk_planner_prompt(
            query=query or "포트폴리오 리스크 분석",
            analysis_depth=analysis_depth,
            focus_areas=focus_areas,
        )

        # LLM 호출
        response = await llm.ainvoke(prompt)

        # JSON 파싱
        from src.prompts import parse_llm_json

        plan = parse_llm_json(response.content)

        # 결과 추출
        specialists = plan.get("specialists", [])
        execution_order = plan.get("execution_order", "sequential")
        reasoning = plan.get("reasoning", "")
        estimated_time = plan.get("estimated_time", "20")

        logger.info(
            "✅ [Risk/Planner] 계획 수립 완료: %s개 Specialist | 실행 방식: %s | 예상 시간: %s초",
            len(specialists),
            execution_order,
            estimated_time,
        )

    except Exception as exc:
        logger.warning("⚠️ [Risk/Planner] 계획 수립 실패, fallback 사용: %s", exc)

        # Fallback: depth 기반 기본 계획
        if analysis_depth == "quick":
            specialists = ["collect_data", "concentration_specialist", "final_assessment"]
        elif analysis_depth == "comprehensive":
            specialists = ["collect_data", "concentration_specialist", "market_risk_specialist", "final_assessment"]
        else:  # standard
            specialists = ["collect_data", "concentration_specialist", "market_risk_specialist", "final_assessment"]

        execution_order = "sequential"
        reasoning = "Fallback 기본 계획"

    # pending_tasks 생성
    pending_tasks = [
        {
            "id": f"task_{i}",
            "specialist": specialist,
            "status": "pending",
            "description": f"{specialist} 실행",
        }
        for i, specialist in enumerate(specialists)
    ]

    logger.info("📋 [Risk/Planner] %s개 작업 생성: %s", len(pending_tasks), specialists)

    message = AIMessage(
        content=f"리스크 분석 계획: {len(specialists)}개 Specialist 실행 ({execution_order})\\n이유: {reasoning}"
    )

    return {
        "pending_tasks": pending_tasks,
        "completed_tasks": [],
        "task_notes": [f"계획 수립: {len(specialists)}개 Specialist"],
        "messages": [message],
    }


async def task_router_node(state: RiskState) -> RiskState:
    """
    Task Router - 다음 작업 선택

    pending_tasks에서 다음 작업을 가져와 current_task로 설정합니다.
    """
    pending_tasks = list(state.get("pending_tasks") or [])

    if not pending_tasks:
        logger.info("✅ [Risk/TaskRouter] 모든 작업 완료, final_assessment로 이동")
        return {"current_task": None}

    # 다음 작업 선택
    current_task = pending_tasks.pop(0)
    specialist = current_task.get("specialist")

    logger.info("🔀 [Risk/TaskRouter] 다음 작업 선택: %s", specialist)

    return {
        "current_task": current_task,
        "pending_tasks": pending_tasks,
    }


# ==================== Original Nodes ====================


async def collect_portfolio_data_node(state: RiskState) -> dict:
    """실제 DB 기반 포트폴리오 및 시장 데이터 수집."""
    logger.info("📊 [Risk] 포트폴리오 데이터 조회 시작")

    user_id = state.get("user_id")
    portfolio_id = state.get("portfolio_id")
    messages = list(state.get("messages", []))

    try:
        snapshot = await portfolio_service.get_portfolio_snapshot(
            user_id=user_id,
            portfolio_id=portfolio_id,
        )
    except PortfolioNotFoundError as exc:
        logger.error("❌ [Risk] 포트폴리오 없음: %s", exc)
        return {**state, "error": str(exc), "messages": messages}
    except Exception as exc:  # pragma: no cover - 방어 로깅
        logger.exception("❌ [Risk] 포트폴리오 조회 실패: %s", exc)
        return {**state, "error": str(exc), "messages": messages}

    if snapshot is None:
        error_msg = "포트폴리오를 찾을 수 없습니다."
        logger.warning("⚠️ [Risk] %s", error_msg)
        return {**state, "error": error_msg, "messages": messages}

    portfolio_data = snapshot.portfolio_data
    market_data = snapshot.market_data
    profile = snapshot.profile

    holdings = portfolio_data.get("holdings", [])
    logger.info("✅ [Risk] 포트폴리오 로딩 완료 - 종목 수: %d", len(holdings))

    return {
        "portfolio_data": portfolio_data,
        "market_data": market_data,
        "portfolio_profile": profile,
        "messages": messages,
    }


async def concentration_check_node(state: RiskState) -> dict:
    """개별·섹터 집중도와 경고 메시지를 계산."""
    if state.get("error"):
        return state

    portfolio = state.get("portfolio_data") or {}
    holdings: List[Dict[str, Any]] = portfolio.get("holdings", [])  # type: ignore[arg-type]
    sectors = portfolio.get("sectors", {})

    if not holdings:
        logger.warning("⚠️ [Risk] 보유 종목이 없어 집중도 분석을 건너뜁니다")
        return {**state, "concentration_risk": None}

    warnings: List[str] = []
    hhi, top_holding, top_sector = _calculate_concentration_metrics(holdings, sectors)

    if top_holding[1] > 0.30:
        warnings.append(
            f"{top_holding[0]} 비중이 {top_holding[1]:.0%}로 높습니다 (권장: 25% 이하)"
        )
    if top_sector[1] > 0.50:
        warnings.append(
            f"{top_sector[0]} 섹터 비중이 {top_sector[1]:.0%}로 높습니다 (권장: 50% 이하)"
        )

    level = "high" if hhi > 0.25 else "medium" if hhi > 0.15 else "low"
    concentration_risk = {
        "hhi": float(hhi),
        "level": level,
        "warnings": warnings,
        "top_holding": {
            "name": top_holding[0],
            "weight": float(top_holding[1]),
        },
        "top_sector": {
            "name": top_sector[0],
            "weight": float(top_sector[1]),
        },
        "sector_breakdown": {k: float(v) for k, v in sectors.items()},
    }

    logger.info("✅ [Risk] 집중도 체크 완료 - HHI=%.3f, 레벨=%s", hhi, level)

    messages = list(state.get("messages", []))
    return {"concentration_risk": concentration_risk, "messages": messages}


async def market_risk_node(state: RiskState) -> dict:
    """포트폴리오 변동성, VaR 등 시장 리스크 지표 계산."""
    if state.get("error"):
        return state

    market_data = state.get("market_data") or {}
    portfolio = state.get("portfolio_data") or {}
    holdings = portfolio.get("holdings", [])

    volatility = market_data.get("portfolio_volatility")
    var_95 = market_data.get("var_95")
    max_drawdown = market_data.get("max_drawdown_estimate")
    beta_map = market_data.get("beta") or {}

    if volatility is None or var_95 is None:
        logger.debug("[Risk] 시장 리스크 선계산 값이 없어 재계산을 시도합니다")
        volatility, var_95, max_drawdown = _fallback_market_metrics(holdings)

    portfolio_beta = sum(
        (h.get("weight") or 0.0) * beta_map.get(h.get("stock_code"), 1.0)
        for h in holdings
    ) or 1.0

    risk_level = "high" if (var_95 or 0) > 0.10 else "medium" if (var_95 or 0) > 0.05 else "low"
    market_risk = {
        "portfolio_volatility": volatility,
        "portfolio_beta": portfolio_beta,
        "var_95": var_95,
        "max_drawdown_estimate": max_drawdown,
        "risk_level": risk_level,
    }

    logger.info(
        "✅ [Risk] 시장 리스크 분석 완료 - VaR=%.2f%%, 변동성=%.2f%%",
        (var_95 or 0) * 100,
        (volatility or 0) * 100,
    )

    messages = list(state.get("messages", []))
    return {"market_risk": market_risk, "messages": messages}


def _calculate_concentration_metrics(
    holdings: List[Dict[str, Any]],
    sectors: Dict[str, float],
) -> Tuple[float, Tuple[str, float], Tuple[str, float]]:
    hhi = 0.0
    top_holding = ("N/A", 0.0)
    for holding in holdings:
        weight = float(holding.get("weight") or 0.0)
        hhi += weight ** 2
        if weight > top_holding[1]:
            top_holding = (holding.get("stock_name") or holding.get("stock_code", "N/A"), weight)

    if not sectors:
        sectors = {}
    top_sector = ("N/A", 0.0)
    for name, weight in sectors.items():
        weight_float = float(weight)
        if weight_float > top_sector[1]:
            top_sector = (name, weight_float)

    return hhi, top_holding, top_sector


def _fallback_market_metrics(holdings: List[Dict[str, Any]]) -> Tuple[float, float, Optional[float]]:
    if not holdings:
        return 0.0, 0.0, None

    average_beta = sum(float(h.get("beta") or 1.0) for h in holdings) / len(holdings)
    average_weight = sum(float(h.get("weight") or 0.0) for h in holdings)
    volatility = max(0.05, average_beta * 0.15 * max(average_weight, 1.0))
    var_95 = volatility * 1.65
    max_drawdown = var_95 * 1.8
    return volatility, var_95, max_drawdown


async def final_assessment_node(state: RiskState) -> dict:
    """
    4단계: 최종 리스크 평가

    - 전체 리스크 점수 산출
    - 리스크 레벨 결정
    - 권고사항 생성
    - HITL 트리거 여부 결정
    """
    concentration = state.get("concentration_risk", {})
    market = state.get("market_risk", {})

    # 리스크 점수 계산 (0-100)
    concentration_score = {
        "high": 70,
        "medium": 40,
        "low": 10,
    }.get(concentration.get("level"), 50)

    market_score = {
        "high": 70,
        "medium": 40,
        "low": 10,
    }.get(market.get("risk_level"), 50)

    risk_score = (concentration_score + market_score) / 2

    # 최종 리스크 레벨
    if risk_score >= 60:
        risk_level = "high"
    elif risk_score >= 30:
        risk_level = "medium"
    else:
        risk_level = "low"

    # 경고 및 권고사항
    profile = state.get("portfolio_profile") or {}
    all_warnings = list(concentration.get("warnings", []))

    top_holding = concentration.get("top_holding", {}) or {}
    top_sector = concentration.get("top_sector", {}) or {}

    recommendations = []
    if float(top_holding.get("weight") or 0.0) > 0.30:
        recommendations.append("주요 종목 비중이 높습니다. 추가 분산을 고려하세요.")
    if float(market.get("var_95") or 0.0) > 0.10:
        recommendations.append("변동성이 높은 구간입니다. 현금 비중을 확대해 리스크를 관리하세요.")
    if float(top_sector.get("weight") or 0.0) > 0.50:
        recommendations.append("특정 섹터 비중이 높습니다. 섹터 다변화를 검토하세요.")

    risk_pref = profile.get("risk_tolerance")
    if risk_pref and risk_pref in {"conservative", "safe"} and risk_level != "low":
        recommendations.append("보수적 성향에 비해 리스크가 높습니다. 목표 성향을 재조정하세요.")

    # HITL 트리거 (고위험일 때)
    should_trigger_hitl = risk_level == "high"

    risk_assessment = {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "concentration_risk": concentration.get("hhi"),
        "volatility": market.get("portfolio_volatility"),
        "var_95": market.get("var_95"),
        "max_drawdown_estimate": market.get("max_drawdown_estimate"),
        "warnings": all_warnings,
        "recommendations": recommendations,
        "should_trigger_hitl": should_trigger_hitl,
        "sector_breakdown": state.get("portfolio_data", {}).get("sectors", {}),
        "profile": profile,
    }

    logger.info(f"✅ [Risk] 최종 평가 완료: {risk_level} (점수: {risk_score:.0f})")

    risk_pref_desc = f" (선호 {risk_pref})" if risk_pref else ""
    summary = (
        f"리스크 수치: {risk_level.upper()} / 점수 {risk_score:.0f}{risk_pref_desc}. "
        f"변동성 {market.get('portfolio_volatility', 0):.1%}, VaR95 {market.get('var_95', 0):.1%}."
    )

    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=summary))

    # MasterState(GraphState)로 결과 전달
    # agent_results는 간단한 요약만 포함 (프론트엔드 직렬화 문제 방지)
    return {
        "risk_assessment": risk_assessment,  # RiskState 내부용
        "agent_results": {  # MasterState 공유용
            "risk": {
                "summary": summary,
                "risk_level": risk_level,
                "risk_score": risk_score,
                "warnings_count": len(all_warnings),
                "should_trigger_hitl": should_trigger_hitl,
            }
        },
        "messages": messages,
    }
