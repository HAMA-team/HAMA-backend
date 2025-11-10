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
    from src.utils.llm_factory import get_portfolio_risk_llm as get_llm

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
    from src.utils.llm_factory import get_portfolio_risk_llm as get_llm

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


# ==================== Phase 1: Pre-Trade Risk Briefing ====================

async def simulate_portfolio_change(
    portfolio_id: str,
    order_type: str,
    stock_code: str,
    stock_name: str,
    quantity: int,
    price: float,
) -> Dict[str, Any]:
    """
    거래 후 포트폴리오 변화 시뮬레이션

    Args:
        portfolio_id: 포트폴리오 ID
        order_type: 주문 유형 (BUY/SELL)
        stock_code: 종목 코드
        stock_name: 종목명
        quantity: 수량
        price: 가격

    Returns:
        Dict: 포트폴리오 변화 데이터
    """
    from src.services import kis_service, sector_data_service

    logger.info(
        "🔮 [Risk/Simulate] 포트폴리오 변화 시뮬레이션 시작: %s %s %d주 @ %s원",
        order_type,
        stock_code,
        quantity,
        f"{price:,.0f}",
    )

    try:
        # 1. 현재 포트폴리오 스냅샷 조회
        snapshot = await portfolio_service.get_portfolio_snapshot(portfolio_id=portfolio_id)
        if not snapshot:
            raise PortfolioNotFoundError(f"포트폴리오 {portfolio_id}를 찾을 수 없습니다")

        portfolio_data = snapshot.portfolio_data
        current_cash = float(portfolio_data.get("cash_balance", 0))
        current_total_value = float(portfolio_data.get("total_value", 0))

        # 2. 현재 포지션 조회 (holdings에서 추출)
        holdings = portfolio_data.get("holdings", [])
        position_dict = {
            h["stock_code"]: {
                "stock_code": h["stock_code"],
                "quantity": h.get("quantity", 0),
                "current_price": h.get("current_price", 0),
                "average_price": h.get("average_price", 0),
            }
            for h in holdings
            if h.get("stock_code") and h["stock_code"].upper() != "CASH"
        }

        # 3. 거래 금액 계산
        total_amount = quantity * price
        is_buy = order_type.upper() in ("BUY", "매수")

        # 4. 거래 후 현금 계산
        if is_buy:
            cash_after = current_cash - total_amount
            if cash_after < 0:
                logger.warning("⚠️ [Risk/Simulate] 현금 부족: 필요 %s원, 보유 %s원", f"{total_amount:,.0f}", f"{current_cash:,.0f}")
        else:  # SELL
            cash_after = current_cash + total_amount

        # 5. 거래 후 총 자산 계산
        # 매수/매도는 포트폴리오 내에서 자산 형태만 변환하므로 총 자산은 변하지 않음
        total_value_after = current_total_value

        # 6. 종목별 비중 계산 (거래 전)
        position_weight_before = {}
        for h in holdings:
            if h.get("stock_code") and h["stock_code"].upper() != "CASH":
                pos_value = float(h.get("quantity", 0)) * float(h.get("current_price", 0))
                weight = pos_value / current_total_value if current_total_value > 0 else 0
                position_weight_before[h["stock_code"]] = weight

        # 7. 거래 대상 종목의 거래 전 비중
        target_weight_before = position_weight_before.get(stock_code, 0.0)

        # 8. 거래 후 종목별 비중 계산
        position_weight_after = dict(position_weight_before)

        if is_buy:
            # 매수: 기존 수량 + 신규 수량
            existing_pos = position_dict.get(stock_code)
            if existing_pos:
                new_quantity = existing_pos["quantity"] + quantity
            else:
                new_quantity = quantity
            new_value = new_quantity * price
            target_weight_after = new_value / total_value_after if total_value_after > 0 else 0
            position_weight_after[stock_code] = target_weight_after
        else:
            # 매도: 기존 수량 - 매도 수량
            existing_pos = position_dict.get(stock_code)
            if existing_pos:
                remaining_quantity = existing_pos["quantity"] - quantity
                if remaining_quantity > 0:
                    new_value = remaining_quantity * price
                    target_weight_after = new_value / total_value_after if total_value_after > 0 else 0
                    position_weight_after[stock_code] = target_weight_after
                else:
                    # 전량 매도
                    target_weight_after = 0.0
                    position_weight_after.pop(stock_code, None)
            else:
                target_weight_after = 0.0

        # 9. 현금 비중 계산
        cash_ratio_before = current_cash / current_total_value if current_total_value > 0 else 0
        cash_ratio_after = cash_after / total_value_after if total_value_after > 0 else 0

        logger.info(
            "✅ [Risk/Simulate] 시뮬레이션 완료: 현금 %s원 → %s원 (%.1f%% → %.1f%%)",
            f"{current_cash:,.0f}",
            f"{cash_after:,.0f}",
            cash_ratio_before * 100,
            cash_ratio_after * 100,
        )

        return {
            "cash_before": current_cash,
            "cash_after": cash_after,
            "cash_ratio_before": cash_ratio_before,
            "cash_ratio_after": cash_ratio_after,
            "position_weight_before": position_weight_before,
            "position_weight_after": position_weight_after,
            "target_stock_code": stock_code,
            "target_stock_name": stock_name,
            "target_weight_before": target_weight_before,
            "target_weight_after": target_weight_after,
        }

    except Exception as exc:
        logger.error("❌ [Risk/Simulate] 시뮬레이션 실패: %s", exc, exc_info=True)
        raise


async def calculate_concentration_risk(
    position_weight_after: Dict[str, float],
    stock_code: str,
) -> Dict[str, Any]:
    """
    집중도 리스크 계산

    Args:
        position_weight_after: 거래 후 종목별 비중
        stock_code: 거래 대상 종목 코드

    Returns:
        Dict: 집중도 리스크 분석 결과
    """
    import asyncio
    from src.models.database import SessionLocal
    from src.models.stock import Stock

    logger.info("📊 [Risk/Concentration] 집중도 리스크 계산 시작")

    try:
        # 1. Stock 테이블에서 섹터 정보 조회
        def get_sectors_sync(stock_codes):
            session = SessionLocal()
            try:
                stocks = session.query(Stock).filter(Stock.stock_code.in_(stock_codes)).all()
                return {stock.stock_code: stock.sector or "기타" for stock in stocks}
            finally:
                session.close()

        stock_codes = list(position_weight_after.keys())
        sector_map = await asyncio.to_thread(get_sectors_sync, stock_codes)

        # 2. 섹터별 비중 계산
        sector_concentration = {}
        for code, weight in position_weight_after.items():
            sector = sector_map.get(code, "기타")
            sector_concentration[sector] = sector_concentration.get(sector, 0.0) + weight

        # 3. 최대 섹터 집중도
        if sector_concentration:
            max_sector_name = max(sector_concentration, key=sector_concentration.get)
            max_sector_concentration = sector_concentration[max_sector_name]
        else:
            max_sector_name = "없음"
            max_sector_concentration = 0.0

        # 4. 최대 단일 종목 비중
        if position_weight_after:
            max_stock_code = max(position_weight_after, key=position_weight_after.get)
            single_stock_max = position_weight_after[max_stock_code]
            # 종목명 조회 (간단히 코드로 대체 가능)
            single_stock_name = max_stock_code
        else:
            single_stock_max = 0.0
            single_stock_name = None

        # 5. 리스크 레벨 판단
        warnings = []
        if max_sector_concentration > 0.50:
            risk_level = "critical"
            warnings.append(f"⚠️⚠️⚠️ {max_sector_name} 섹터 집중도 {max_sector_concentration*100:.0f}% (권장: 40% 이하)")
        elif max_sector_concentration > 0.40:
            risk_level = "high"
            warnings.append(f"⚠️⚠️ {max_sector_name} 섹터 집중도 {max_sector_concentration*100:.0f}% (권장: 40% 이하)")
        elif max_sector_concentration > 0.30:
            risk_level = "moderate"
            warnings.append(f"⚠️ {max_sector_name} 섹터 집중도 {max_sector_concentration*100:.0f}%")
        else:
            risk_level = "low"

        if single_stock_max > 0.40:
            if risk_level not in ("critical", "high"):
                risk_level = "high"
            warnings.append(f"⚠️⚠️ {single_stock_name} 단일 종목 비중 {single_stock_max*100:.0f}% (권장: 30% 이하)")
        elif single_stock_max > 0.30:
            if risk_level == "low":
                risk_level = "moderate"
            warnings.append(f"⚠️ {single_stock_name} 단일 종목 비중 {single_stock_max*100:.0f}%")

        logger.info(
            "✅ [Risk/Concentration] 계산 완료: %s (최대 섹터 %s %.0f%%, 최대 종목 %.0f%%)",
            risk_level,
            max_sector_name,
            max_sector_concentration * 100,
            single_stock_max * 100,
        )

        return {
            "sector_concentration": sector_concentration,
            "max_sector_concentration": max_sector_concentration,
            "max_sector_name": max_sector_name,
            "single_stock_max": single_stock_max,
            "single_stock_name": single_stock_name,
            "risk_level": risk_level,
            "warnings": warnings,
        }

    except Exception as exc:
        logger.error("❌ [Risk/Concentration] 계산 실패: %s", exc, exc_info=True)
        # Fallback
        return {
            "sector_concentration": {},
            "max_sector_concentration": 0.0,
            "max_sector_name": "알 수 없음",
            "single_stock_max": 0.0,
            "single_stock_name": None,
            "risk_level": "low",
            "warnings": [],
        }


async def calculate_stop_loss_target(
    stock_code: str,
    current_price: float,
) -> Optional[Dict[str, Any]]:
    """
    손절/익절 라인 계산 (ATR 기반)

    Args:
        stock_code: 종목 코드
        current_price: 현재가

    Returns:
        Dict: 손절/익절 라인 정보 또는 None
    """
    logger.info("🎯 [Risk/StopLoss] 손절/익절 라인 계산 시작: %s @ %s원", stock_code, f"{current_price:,.0f}")

    try:
        # 1. 고정 비율 기반 손절/익절 라인 계산
        # TODO: 향후 ATR 기반 계산으로 개선
        # 손절: -5% (현재가의 95%)
        # 익절: +10% (현재가의 110%)
        atr_value = current_price * 0.05  # 5% 기본
        volatility_level = "moderate"
        calculation_method = "fixed_percentage"

        # 2. 손절/익절 라인 계산
        stop_loss_price = current_price * 0.95  # -5%
        target_price = current_price * 1.10  # +10%

        stop_loss_percent = ((stop_loss_price - current_price) / current_price) * 100
        target_percent = ((target_price - current_price) / current_price) * 100

        logger.info(
            "✅ [Risk/StopLoss] 계산 완료: 손절 %s원 (%.1f%%), 익절 %s원 (%.1f%%)",
            f"{stop_loss_price:,.0f}",
            stop_loss_percent,
            f"{target_price:,.0f}",
            target_percent,
        )

        return {
            "current_price": current_price,
            "stop_loss_price": stop_loss_price,
            "stop_loss_percent": stop_loss_percent,
            "target_price": target_price,
            "target_percent": target_percent,
            "atr_value": atr_value,
            "volatility_level": volatility_level,
            "calculation_method": calculation_method,
        }

    except Exception as exc:
        logger.error("❌ [Risk/StopLoss] 계산 실패: %s", exc, exc_info=True)
        # Fallback: 고정 비율
        return {
            "current_price": current_price,
            "stop_loss_price": current_price * 0.95,
            "stop_loss_percent": -5.0,
            "target_price": current_price * 1.10,
            "target_percent": 10.0,
            "atr_value": None,
            "volatility_level": "moderate",
            "calculation_method": "fixed_percentage",
        }


async def generate_pre_trade_risk_briefing(
    portfolio_id: str,
    order_type: str,
    stock_code: str,
    stock_name: str,
    quantity: int,
    price: float,
) -> Dict[str, Any]:
    """
    Pre-Trade Risk Briefing 생성

    매매 실행 전 리스크를 사전 평가하여 RiskBriefing 객체 반환

    Args:
        portfolio_id: 포트폴리오 ID
        order_type: 주문 유형 (BUY/SELL)
        stock_code: 종목 코드
        stock_name: 종목명
        quantity: 수량
        price: 가격

    Returns:
        Dict: RiskBriefing 스키마에 맞는 데이터
    """
    logger.info(
        "🚨 [Risk/PreTrade] Pre-Trade Risk Briefing 시작: %s %s %d주 @ %s원",
        order_type,
        stock_name,
        quantity,
        f"{price:,.0f}",
    )

    try:
        # 1. 포트폴리오 변화 시뮬레이션
        portfolio_change = await simulate_portfolio_change(
            portfolio_id=portfolio_id,
            order_type=order_type,
            stock_code=stock_code,
            stock_name=stock_name,
            quantity=quantity,
            price=price,
        )

        # 2. 집중도 리스크 계산
        concentration_risk = await calculate_concentration_risk(
            position_weight_after=portfolio_change["position_weight_after"],
            stock_code=stock_code,
        )

        # 3. 손절/익절 라인 계산 (매수인 경우만)
        stop_loss_target = None
        if order_type.upper() in ("BUY", "매수"):
            stop_loss_target = await calculate_stop_loss_target(stock_code, price)

        # 4. 종합 리스크 레벨 판단
        concentration_level = concentration_risk["risk_level"]
        cash_ratio_after = portfolio_change["cash_ratio_after"]

        # 현금 비중이 10% 미만이면 유동성 리스크
        if cash_ratio_after < 0.10:
            overall_risk_level = "high"
        elif concentration_level in ("critical", "high"):
            overall_risk_level = concentration_level
        elif concentration_level == "moderate":
            overall_risk_level = "moderate"
        else:
            overall_risk_level = "low"

        # 5. 권장 조치 결정
        if overall_risk_level == "critical":
            recommended_action = "cancel"
            recommended_quantity = None
        elif overall_risk_level == "high":
            recommended_action = "adjust"
            recommended_quantity = max(quantity // 2, 1)  # 절반으로 조정
        else:
            recommended_action = "proceed"
            recommended_quantity = None

        # 6. 요약 메시지 생성
        risk_emoji = {
            "low": "✅",
            "moderate": "⚠️",
            "high": "⚠️⚠️",
            "critical": "🚨",
        }.get(overall_risk_level, "ℹ️")

        if recommended_action == "cancel":
            summary = f"{risk_emoji} 고위험: 거래를 취소하고 포트폴리오 재조정을 권장합니다."
        elif recommended_action == "adjust":
            summary = (
                f"{risk_emoji} 중위험: {stock_name} 비중이 과도하게 높아집니다. "
                f"수량을 {recommended_quantity}주로 조정하는 것을 권장합니다."
            )
        else:
            summary = f"{risk_emoji} 저위험: 거래를 진행해도 무방합니다."

        # 7. 상세 경고 목록 생성
        detailed_warnings = list(concentration_risk.get("warnings", []))
        if cash_ratio_after < 0.10:
            detailed_warnings.append(f"현금 비중이 {cash_ratio_after*100:.1f}%로 낮아져 유동성 리스크 발생")
        if cash_ratio_after < 0.05:
            detailed_warnings.append("긴급 자금 부족 가능성 높음")

        logger.info(
            "✅ [Risk/PreTrade] Briefing 완료: %s | 권장 조치: %s",
            overall_risk_level,
            recommended_action,
        )

        # 8. RiskBriefing 스키마 형식으로 반환
        return {
            "order_type": order_type.lower(),
            "stock_code": stock_code,
            "stock_name": stock_name,
            "quantity": quantity,
            "price": price,
            "total_amount": quantity * price,
            "portfolio_change": portfolio_change,
            "concentration_risk": concentration_risk,
            "stop_loss_target": stop_loss_target,
            "overall_risk_level": overall_risk_level,
            "recommended_action": recommended_action,
            "recommended_quantity": recommended_quantity,
            "summary": summary,
            "detailed_warnings": detailed_warnings,
        }

    except Exception as exc:
        logger.error("❌ [Risk/PreTrade] Briefing 생성 실패: %s", exc, exc_info=True)
        # Fallback: 최소한의 정보 반환
        return {
            "order_type": order_type.lower(),
            "stock_code": stock_code,
            "stock_name": stock_name,
            "quantity": quantity,
            "price": price,
            "total_amount": quantity * price,
            "portfolio_change": {
                "cash_before": 0,
                "cash_after": 0,
                "cash_ratio_before": 0,
                "cash_ratio_after": 0,
                "position_weight_before": {},
                "position_weight_after": {},
                "target_stock_code": stock_code,
                "target_stock_name": stock_name,
                "target_weight_before": 0,
                "target_weight_after": 0,
            },
            "concentration_risk": {
                "sector_concentration": {},
                "max_sector_concentration": 0,
                "max_sector_name": "알 수 없음",
                "single_stock_max": 0,
                "single_stock_name": None,
                "risk_level": "low",
                "warnings": [],
            },
            "stop_loss_target": None,
            "overall_risk_level": "low",
            "recommended_action": "proceed",
            "recommended_quantity": None,
            "summary": "⚠️ 리스크 분석 실패. 신중하게 진행하세요.",
            "detailed_warnings": [f"리스크 분석 오류: {str(exc)}"],
        }
