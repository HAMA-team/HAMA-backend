"""Portfolio Agent 노드 함수들

포트폴리오 스냅샷 → 최적화 → 리밸런싱 계획 → 요약
"""
from __future__ import annotations

import logging
from typing import Dict, List

from langchain_core.messages import AIMessage

from src.agents.portfolio.state import (
    PortfolioState,
    PortfolioHolding,
    RebalanceInstruction,
)
from src.services import (
    KISAPIError,
    KISAuthError,
    PortfolioNotFoundError,
    portfolio_optimizer,
    portfolio_service,
)

logger = logging.getLogger(__name__)


async def collect_portfolio_node(state: PortfolioState) -> PortfolioState:
    """포트폴리오 스냅샷 수집 노드 (KIS API 연동)."""
    if state.get("error"):
        return state

    logger.info("📊 [Portfolio] 현재 포트폴리오 스냅샷 조회")

    try:
        snapshot = await portfolio_service.get_portfolio_snapshot(
            user_id=state.get("user_id"),
            portfolio_id=state.get("portfolio_id"),
        )
        if snapshot is None or not (snapshot.portfolio_data or {}).get("holdings"):
            snapshot = await portfolio_service.sync_with_kis(
                user_id=state.get("user_id"),
                portfolio_id=state.get("portfolio_id"),
            )
    except PortfolioNotFoundError as exc:
        logger.error("❌ [Portfolio] 포트폴리오 없음: %s", exc)
        return {**state, "error": str(exc)}
    except (KISAPIError, KISAuthError) as exc:
        logger.error("❌ [Portfolio] KIS 동기화 실패: %s", exc)
        return {**state, "error": "KIS API와 연동에 실패했습니다. 설정을 확인해주세요."}
    except Exception as exc:  # pragma: no cover - 방어 로깅
        logger.exception("❌ [Portfolio] 포트폴리오 조회 실패: %s", exc)
        return {**state, "error": str(exc)}

    if snapshot is None:
        error = "포트폴리오 정보를 찾을 수 없습니다."
        logger.warning("⚠️ [Portfolio] %s", error)
        return {**state, "error": error}

    portfolio_data = snapshot.portfolio_data
    profile = snapshot.profile or {}

    holdings = portfolio_data.get("holdings") or []

    # 보유 종목이 없으면 에러
    if not holdings:
        error_msg = "포트폴리오에 보유 종목이 없습니다."
        logger.error(f"❌ [Portfolio] {error_msg}")
        return {**state, "error": error_msg}

    risk_profile = (
        state.get("risk_profile")
        or profile.get("risk_tolerance")
        or state.get("preferences", {}).get("risk_profile")
        or "moderate"
    ).lower()

    return {
        **state,
        "portfolio_id": portfolio_data.get("portfolio_id") or state.get("portfolio_id"),
        "total_value": float(portfolio_data.get("total_value", 0.0)),
        "current_holdings": holdings,
        "risk_profile": risk_profile,
        "portfolio_profile": profile,
        "portfolio_snapshot": {
            "portfolio_data": portfolio_data,
            "market_data": snapshot.market_data,
            "profile": profile,
        },
    }


async def optimize_allocation_node(state: PortfolioState) -> PortfolioState:
    """
    목표 비중 최적화 (동적 계산)

    Strategy Agent 결과를 우선 반영하여 실제 데이터 기반 목표 비중을 계산합니다.
    """
    if state.get("error"):
        return state

    risk_profile = state.get("risk_profile", "moderate")
    current_holdings = state.get("current_holdings", [])
    total_value = state.get("total_value", 0.0)

    # Strategy Agent 결과 추출
    strategy_result = state.get("strategy_result")

    logger.info(f"🧮 [Portfolio] 동적 목표 비중 계산 시작 (risk={risk_profile})")

    try:
        # Portfolio Optimizer로 목표 비중 계산
        proposed, metrics = await portfolio_optimizer.calculate_target_allocation(
            current_holdings=current_holdings,
            strategy_result=strategy_result,
            risk_profile=risk_profile,
            total_value=total_value
        )

        logger.info(f"✅ [Portfolio] 목표 비중 계산 완료: {len(proposed)}개 자산")

        return {
            **state,
            "proposed_allocation": proposed,
            "expected_return": metrics.get("expected_return", 0.12),
            "expected_volatility": metrics.get("expected_volatility", 0.17),
            "sharpe_ratio": metrics.get("sharpe_ratio", 0.80),
            "rationale": metrics.get("rationale", "균형 포트폴리오 구성"),
        }

    except Exception as exc:
        error_msg = f"목표 비중 계산 실패: {exc}"
        logger.error(f"❌ [Portfolio] {error_msg}")
        return {**state, "error": error_msg}


async def rebalance_plan_node(state: PortfolioState) -> PortfolioState:
    """현 비중과 목표 비중 비교 후 리밸런싱 지시 생성"""
    if state.get("error"):
        return state

    current = state.get("current_holdings") or []
    proposed = state.get("proposed_allocation") or []
    total_value = state.get("total_value") or 0

    logger.info("⚖️ [Portfolio] 리밸런싱 플랜 계산")

    current_map = {item["stock_code"]: item for item in current}
    proposed_map = {item["stock_code"]: item for item in proposed}

    trades: List[RebalanceInstruction] = []
    max_delta = 0.0

    processed_codes = set()

    for code, proposed_item in proposed_map.items():
        current_weight = current_map.get(code, {}).get("weight", 0.0)
        delta = round(proposed_item.get("weight", 0.0) - current_weight, 4)
        max_delta = max(max_delta, abs(delta))
        processed_codes.add(code)

        if abs(delta) < 0.005:
            continue

        action = "BUY" if delta > 0 else "SELL"
        amount = round(total_value * abs(delta), -3)
        trades.append(
            {
                "action": action,
                "stock_code": code,
                "stock_name": proposed_item.get("stock_name", code),
                "amount": float(amount),
                "weight_delta": delta,
            }
        )

    # 현재 보유하지만 목표에서 제외된 자산 정리
    for code, current_item in current_map.items():
        if code in processed_codes:
            continue
        delta = -current_item.get("weight", 0.0)
        if abs(delta) < 0.005:
            continue
        amount = round(total_value * abs(delta), -3)
        trades.append(
            {
                "action": "SELL",
                "stock_code": code,
                "stock_name": current_item.get("stock_name", code),
                "amount": float(amount),
                "weight_delta": delta,
            }
        )
        max_delta = max(max_delta, abs(delta))

    rebalancing_needed = max_delta >= 0.02
    hitl_required = rebalancing_needed and state.get("automation_level", 2) >= 2

    return {
        **state,
        "trades_required": trades,
        "rebalancing_needed": rebalancing_needed,
        "hitl_required": hitl_required,
    }


async def summary_node(state: PortfolioState) -> PortfolioState:
    """최종 요약 및 리포트 구성"""
    if state.get("error"):
        return state

    proposed = state.get("proposed_allocation") or []
    trades = state.get("trades_required") or []
    current = state.get("current_holdings") or []
    risk_profile = state.get("risk_profile", "moderate")

    equity_weight = sum(item["weight"] for item in proposed if item["stock_code"] != "CASH")
    cash_weight = next((item["weight"] for item in proposed if item["stock_code"] == "CASH"), 0.0)

    summary_parts = [
        f"예상 수익률 {state.get('expected_return', 0):.0%} / 변동성 {state.get('expected_volatility', 0):.0%}.",
        f"주식 비중 {equity_weight:.0%}, 현금 {cash_weight:.0%}.",
    ]

    if trades:
        summary_parts.append(f"주요 조정: {len(trades)}건 리밸런싱 예정.")
    else:
        summary_parts.append("주요 비중 변경 없음.")

    summary = " ".join(summary_parts)

    portfolio_report = {
        "portfolio_id": state.get("portfolio_id", "portfolio_mock_001"),
        "risk_profile": risk_profile,
        "current_allocation": current,
        "proposed_allocation": proposed,
        "expected_return": state.get("expected_return"),
        "expected_volatility": state.get("expected_volatility"),
        "sharpe_ratio": state.get("sharpe_ratio"),
        "rebalancing_needed": state.get("rebalancing_needed", False),
        "trades_required": trades,
        "rationale": state.get("rationale"),
        "hitl_required": state.get("hitl_required", False),
    }

    logger.info("📝 [Portfolio] 리포트 생성 완료")

    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=summary))

    return {
        **state,
        "summary": summary,
        "portfolio_report": portfolio_report,
        "messages": messages,
    }
