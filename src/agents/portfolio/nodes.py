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

logger = logging.getLogger(__name__)

# 기본 포트폴리오 (Mock)
DEFAULT_PORTFOLIO: List[PortfolioHolding] = [
    {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.35, "value": 3_500_000},
    {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.20, "value": 2_000_000},
    {"stock_code": "035420", "stock_name": "NAVER", "weight": 0.15, "value": 1_500_000},
    {"stock_code": "005380", "stock_name": "현대차", "weight": 0.15, "value": 1_500_000},
    {"stock_code": "000270", "stock_name": "기아", "weight": 0.10, "value": 1_000_000},
    {"stock_code": "CASH", "stock_name": "현금", "weight": 0.05, "value": 500_000},
]

# 위험 성향별 추천 비중
RISK_TARGETS: Dict[str, List[PortfolioHolding]] = {
    "conservative": [
        {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.20},
        {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.12},
        {"stock_code": "035420", "stock_name": "NAVER", "weight": 0.08},
        {"stock_code": "005380", "stock_name": "현대차", "weight": 0.12},
        {"stock_code": "000270", "stock_name": "기아", "weight": 0.08},
        {"stock_code": "CASH", "stock_name": "현금", "weight": 0.40},
    ],
    "moderate": [
        {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.25},
        {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.20},
        {"stock_code": "035420", "stock_name": "NAVER", "weight": 0.15},
        {"stock_code": "005380", "stock_name": "현대차", "weight": 0.15},
        {"stock_code": "000270", "stock_name": "기아", "weight": 0.10},
        {"stock_code": "CASH", "stock_name": "현금", "weight": 0.15},
    ],
    "aggressive": [
        {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.28},
        {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.24},
        {"stock_code": "035420", "stock_name": "NAVER", "weight": 0.18},
        {"stock_code": "005380", "stock_name": "현대차", "weight": 0.14},
        {"stock_code": "000270", "stock_name": "기아", "weight": 0.11},
        {"stock_code": "CASH", "stock_name": "현금", "weight": 0.05},
    ],
}

EXPECTED_RETURN = {
    "conservative": 0.08,
    "moderate": 0.12,
    "aggressive": 0.16,
}

EXPECTED_VOLATILITY = {
    "conservative": 0.11,
    "moderate": 0.17,
    "aggressive": 0.24,
}

SHARPE_RATIO = {
    "conservative": 0.78,
    "moderate": 0.82,
    "aggressive": 0.74,
}

RATIONALE_TEXT = {
    "conservative": "현금·방어주 비중 확대, 시장 변동성 대비 안전자산 확보",
    "moderate": "IT 코어 비중 유지하면서 현금 완충 확대",
    "aggressive": "성장주와 IT 비중 확대, 공격적 수익 추구",
}


async def collect_portfolio_node(state: PortfolioState) -> PortfolioState:
    """포트폴리오 스냅샷 수집 노드"""
    if state.get("error"):
        return state

    logger.info("📊 [Portfolio] 현재 포트폴리오 수집")

    holdings = state.get("current_holdings") or DEFAULT_PORTFOLIO
    total_value = state.get("total_value") or sum(h.get("value", 0) for h in holdings) or 10_000_000

    # value가 지정되지 않았으면 weight 기반으로 계산
    resolved_holdings: List[PortfolioHolding] = []
    for holding in holdings:
        weight = holding.get("weight", 0)
        value = holding.get("value")
        if value is None:
            value = round(total_value * weight, -3)
        resolved_holdings.append(
            {
                "stock_code": holding["stock_code"],
                "stock_name": holding.get("stock_name", holding["stock_code"]),
                "weight": round(weight, 4),
                "value": float(value),
            }
        )

    risk_profile = (state.get("risk_profile") or state.get("preferences", {}).get("risk_profile") or "moderate").lower()
    if risk_profile not in RISK_TARGETS:
        risk_profile = "moderate"

    return {
        **state,
        "portfolio_id": state.get("portfolio_id") or "portfolio_mock_001",
        "total_value": float(total_value),
        "current_holdings": resolved_holdings,
        "risk_profile": risk_profile,
    }


async def optimize_allocation_node(state: PortfolioState) -> PortfolioState:
    """위험 성향에 맞는 목표 비중 산출"""
    if state.get("error"):
        return state

    risk_profile = state.get("risk_profile", "moderate")
    targets = RISK_TARGETS.get(risk_profile, RISK_TARGETS["moderate"])

    logger.info(f"🧮 [Portfolio] 목표 비중 산출 (risk={risk_profile})")

    proposed: List[PortfolioHolding] = []
    total_value = state.get("total_value", 0)
    for target in targets:
        weight = round(target["weight"], 4)
        proposed.append(
            {
                "stock_code": target["stock_code"],
                "stock_name": target["stock_name"],
                "weight": weight,
                "value": round(total_value * weight, -3) if total_value else 0.0,
            }
        )

    return {
        **state,
        "proposed_allocation": proposed,
        "expected_return": EXPECTED_RETURN[risk_profile],
        "expected_volatility": EXPECTED_VOLATILITY[risk_profile],
        "sharpe_ratio": SHARPE_RATIO[risk_profile],
        "rationale": RATIONALE_TEXT[risk_profile],
    }


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
