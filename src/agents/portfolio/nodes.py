"""Portfolio Agent 노드 함수들

포트폴리오 스냅샷 → 최적화 → 리밸런싱 계획 → 승인 (HITL) → 실행
"""
from __future__ import annotations

import logging
from typing import Dict, List
import uuid

from langchain_core.messages import AIMessage
from langgraph_sdk.schema import Interrupt

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


async def validate_constraints_node(state: PortfolioState) -> PortfolioState:
    """
    포트폴리오 제약 조건 검증

    검증 항목:
    1. 최대 슬롯 수 (기본 10개)
    2. 섹터 집중도 (동일 섹터 최대 30%)
    3. 동일 산업군 종목 수 (최대 3개)
    """
    if state.get("error"):
        return state

    proposed = state.get("proposed_allocation") or []
    max_slots = state.get("max_slots", 10)
    max_sector_concentration = state.get("max_sector_concentration", 0.30)
    max_same_industry = state.get("max_same_industry_count", 3)

    logger.info("🔍 [Portfolio] 제약 조건 검증 시작")

    violations = []

    # 1. 최대 슬롯 수 검증
    non_cash_holdings = [h for h in proposed if h.get("stock_code") != "CASH"]
    if len(non_cash_holdings) > max_slots:
        violations.append({
            "type": "max_slots",
            "message": f"최대 보유 종목 수({max_slots}개) 초과: {len(non_cash_holdings)}개",
            "severity": "high",
            "current": len(non_cash_holdings),
            "limit": max_slots,
        })
        logger.warning(f"⚠️ [Portfolio] 최대 슬롯 수 초과: {len(non_cash_holdings)}/{max_slots}")

    # 2. 섹터 집중도 검증
    # 실제로는 종목별 섹터 정보가 필요하지만, 여기서는 stock_name에서 추론하거나
    # 나중에 서비스에서 섹터 정보를 받아와야 함
    # 임시로 간단한 로직으로 구현
    sector_weights = {}
    for holding in non_cash_holdings:
        # TODO: 실제 섹터 정보를 DB나 서비스에서 가져와야 함
        # 현재는 stock_code 기반으로 임시 섹터 할당
        sector = _infer_sector(holding.get("stock_code", ""))
        weight = holding.get("weight", 0.0)
        sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

    for sector, weight in sector_weights.items():
        if weight > max_sector_concentration:
            violations.append({
                "type": "sector_concentration",
                "message": f"섹터 '{sector}' 집중도 초과: {weight:.1%} (제한: {max_sector_concentration:.0%})",
                "severity": "medium",
                "sector": sector,
                "current": weight,
                "limit": max_sector_concentration,
            })
            logger.warning(f"⚠️ [Portfolio] 섹터 집중도 초과: {sector} {weight:.1%}")

    # 3. 동일 산업군 종목 수 검증
    # TODO: 실제 산업군 정보 필요
    industry_counts = {}
    for holding in non_cash_holdings:
        industry = _infer_industry(holding.get("stock_code", ""))
        industry_counts[industry] = industry_counts.get(industry, 0) + 1

    for industry, count in industry_counts.items():
        if count > max_same_industry:
            violations.append({
                "type": "industry_count",
                "message": f"산업군 '{industry}' 종목 수 초과: {count}개 (제한: {max_same_industry}개)",
                "severity": "low",
                "industry": industry,
                "current": count,
                "limit": max_same_industry,
            })
            logger.warning(f"⚠️ [Portfolio] 산업군 종목 수 초과: {industry} {count}개")

    if violations:
        logger.warning(f"⚠️ [Portfolio] 제약 조건 위반 {len(violations)}건 발견")
    else:
        logger.info("✅ [Portfolio] 모든 제약 조건 충족")

    return {
        **state,
        "constraint_violations": violations,
    }


def _infer_sector(stock_code: str) -> str:
    """종목 코드에서 섹터 추론 (임시)"""
    # TODO: 실제 섹터 정보를 DB에서 조회해야 함
    # 임시로 종목 코드 범위로 추정
    if not stock_code or stock_code == "CASH":
        return "CASH"

    code_num = int(stock_code) if stock_code.isdigit() else 0

    if 0 <= code_num < 100000:
        return "제조업"
    elif 100000 <= code_num < 200000:
        return "IT"
    elif 200000 <= code_num < 300000:
        return "금융"
    else:
        return "기타"


def _infer_industry(stock_code: str) -> str:
    """종목 코드에서 산업군 추론 (임시)"""
    # TODO: 실제 산업군 정보를 DB에서 조회해야 함
    if not stock_code or stock_code == "CASH":
        return "CASH"

    code_num = int(stock_code) if stock_code.isdigit() else 0

    if 0 <= code_num < 50000:
        return "전자/전기"
    elif 50000 <= code_num < 100000:
        return "화학/소재"
    elif 100000 <= code_num < 150000:
        return "소프트웨어"
    elif 150000 <= code_num < 200000:
        return "반도체"
    elif 200000 <= code_num < 250000:
        return "은행"
    elif 250000 <= code_num < 300000:
        return "증권"
    else:
        return "기타"


async def market_condition_node(state: PortfolioState) -> PortfolioState:
    """
    시장 상황 분석 및 최대 슬롯 조정

    시장 상황에 따라 최대 보유 종목 수 조정:
    - 강세장: 10개
    - 중립장: 7개
    - 약세장: 5개
    """
    if state.get("error"):
        return state

    logger.info("📈 [Portfolio] 시장 상황 분석 시작")

    # 시장 데이터 추출
    portfolio_snapshot = state.get("portfolio_snapshot") or {}
    market_data = portfolio_snapshot.get("market_data") or {}

    # KOSPI 인덱스 변화율로 시장 상황 판단
    kospi_change = market_data.get("kospi_change_rate", 0.0)

    # 시장 상황 분류
    if kospi_change > 0.05:  # 5% 이상 상승
        market_condition = "강세장"
        recommended_max_slots = 10
    elif kospi_change < -0.05:  # 5% 이상 하락
        market_condition = "약세장"
        recommended_max_slots = 5
    else:
        market_condition = "중립장"
        recommended_max_slots = 7

    logger.info(
        f"📊 [Portfolio] 시장 상황: {market_condition} (KOSPI {kospi_change:+.1%}), "
        f"권장 최대 슬롯: {recommended_max_slots}개"
    )

    messages = list(state.get("messages", []))
    messages.append(
        AIMessage(
            content=(
                f"시장 상황: {market_condition} (KOSPI {kospi_change:+.1%})\n"
                f"권장 최대 보유 종목: {recommended_max_slots}개"
            )
        )
    )

    return {
        **state,
        "market_condition": market_condition,
        "max_slots": recommended_max_slots,
        "messages": messages,
    }


async def summary_node(state: PortfolioState) -> PortfolioState:
    """최종 요약 및 리포트 구성"""
    if state.get("error"):
        return state

    proposed = state.get("proposed_allocation") or []
    trades = state.get("trades_required") or []
    current = state.get("current_holdings") or []
    risk_profile = state.get("risk_profile", "moderate")
    violations = state.get("constraint_violations") or []
    market_condition = state.get("market_condition", "중립장")
    max_slots = state.get("max_slots", 10)

    equity_weight = sum(item["weight"] for item in proposed if item["stock_code"] != "CASH")
    cash_weight = next((item["weight"] for item in proposed if item["stock_code"] == "CASH"), 0.0)

    summary_parts = [
        f"예상 수익률 {state.get('expected_return', 0):.0%} / 변동성 {state.get('expected_volatility', 0):.0%}.",
        f"주식 비중 {equity_weight:.0%}, 현금 {cash_weight:.0%}.",
    ]

    # 시장 상황 정보 추가
    summary_parts.append(f"시장 상황: {market_condition} (최대 {max_slots}개 종목).")

    # 제약 조건 위반 정보 추가
    if violations:
        high_severity = [v for v in violations if v.get("severity") == "high"]
        if high_severity:
            summary_parts.append(f"⚠️ 중요: {len(high_severity)}건의 제약 조건 위반.")
        else:
            summary_parts.append(f"주의: {len(violations)}건의 제약 조건 위반.")

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
        # 포트폴리오 제약 조건 관련
        "market_condition": market_condition,
        "max_slots": max_slots,
        "constraint_violations": violations,
    }

    logger.info("📝 [Portfolio] 리포트 생성 완료")

    messages = list(state.get("messages", []))
    messages.append(AIMessage(content=summary))

    # 리밸런싱 준비 완료 플래그 설정
    rebalance_prepared = state.get("rebalancing_needed", False)
    rebalance_order_id = state.get("rebalance_order_id") or str(uuid.uuid4())

    # MasterState(GraphState)로 결과 전달
    return {
        **state,
        "summary": summary,
        "portfolio_report": portfolio_report,  # PortfolioState 내부용
        "agent_results": {  # MasterState 공유용
            "portfolio": portfolio_report
        },
        "messages": messages,
        "rebalance_prepared": rebalance_prepared,
        "rebalance_order_id": rebalance_order_id if rebalance_prepared else None,
    }


def approval_rebalance_node(state: PortfolioState) -> dict:
    """
    리밸런싱 승인 노드 (HITL Interrupt Point)

    이 노드는 자동화 레벨과 리밸런싱 필요 여부에 따라 사용자 승인을 요청합니다.
    interrupt_before=["approval_rebalance"]로 설정되어 그래프가 이 노드 전에 일시 정지됩니다.
    """
    # 이미 승인된 경우 스킵
    if state.get("rebalance_approved"):
        logger.info("⏭️ [Portfolio] 이미 승인된 리밸런싱입니다")
        return {}

    # 리밸런싱이 필요하지 않은 경우
    if not state.get("rebalancing_needed"):
        logger.info("⏭️ [Portfolio] 리밸런싱이 필요하지 않습니다")
        return {"rebalance_approved": True}  # 자동 승인

    # 자동화 레벨 1 (Pilot)은 자동 승인
    automation_level = state.get("automation_level", 2)
    if automation_level == 1:
        logger.info("✅ [Portfolio] 자동화 레벨 1 - 리밸런싱 자동 승인")
        return {"rebalance_approved": True}

    logger.info("🔔 [Portfolio] 리밸런싱 사용자 승인을 요청합니다")

    # Interrupt payload 생성
    trades_required = state.get("trades_required") or []
    proposed_allocation = state.get("proposed_allocation") or []

    interrupt_payload = {
        "type": "rebalance_approval",
        "order_id": state.get("rebalance_order_id", "UNKNOWN"),
        "automation_level": automation_level,
        "rebalancing_needed": state.get("rebalancing_needed", False),
        "trades_required": trades_required,
        "proposed_allocation": proposed_allocation,
        "expected_return": state.get("expected_return"),
        "expected_volatility": state.get("expected_volatility"),
        "sharpe_ratio": state.get("sharpe_ratio"),
        "constraint_violations": state.get("constraint_violations") or [],
        "market_condition": state.get("market_condition", "중립장"),
        "message": "리밸런싱을 승인하시겠습니까?",
    }

    approval: Interrupt = {
        "id": f"rebalance-{interrupt_payload['order_id']}",
        "value": interrupt_payload,
    }

    logger.info("✅ [Portfolio] 승인 요청 생성: %s", approval)

    messages = list(state.get("messages", []))
    return {"rebalance_approved": True, "messages": messages}


async def execute_rebalance_node(state: PortfolioState) -> dict:
    """
    리밸런싱 실행 노드

    승인된 리밸런싱을 실제로 실행합니다.
    """
    # 이미 실행된 경우 스킵
    if state.get("rebalance_executed"):
        logger.info("⏭️ [Portfolio] 이미 실행된 리밸런싱입니다")
        return {}

    # 승인되지 않은 경우
    if not state.get("rebalance_approved"):
        warning = "리밸런싱이 승인되지 않았습니다."
        logger.warning("⚠️ [Portfolio] %s", warning)
        return {"error": warning}

    # 리밸런싱이 필요하지 않은 경우
    if not state.get("rebalancing_needed"):
        logger.info("⏭️ [Portfolio] 리밸런싱이 필요하지 않습니다")
        return {
            "rebalance_executed": True,
            "messages": list(state.get("messages", [])),
        }

    logger.info("💼 [Portfolio] 리밸런싱 실행 시작")

    trades_required = state.get("trades_required") or []

    if not trades_required:
        logger.info("⏭️ [Portfolio] 실행할 거래가 없습니다")
        return {
            "rebalance_executed": True,
            "messages": list(state.get("messages", [])),
        }

    # TODO: 실제 거래 실행 로직 (Phase 2)
    # 현재는 시뮬레이션으로 처리
    logger.info(f"📝 [Portfolio] {len(trades_required)}건의 거래를 시뮬레이션합니다")

    execution_results = []
    for trade in trades_required:
        execution_results.append({
            "action": trade["action"],
            "stock_code": trade["stock_code"],
            "stock_name": trade["stock_name"],
            "amount": trade["amount"],
            "status": "simulated",  # Phase 2: "executed"
        })
        logger.info(
            f"  - {trade['action']} {trade['stock_name']} {trade['amount']:,.0f}원"
        )

    messages = list(state.get("messages", []))
    summary = (
        f"✅ 리밸런싱 완료:\n"
        f"{len(execution_results)}건의 거래를 시뮬레이션했습니다.\n"
        f"예상 수익률: {state.get('expected_return', 0):.1%}\n"
        f"예상 변동성: {state.get('expected_volatility', 0):.1%}"
    )
    messages.append(AIMessage(content=summary))

    # MasterState(GraphState)로 결과 전달
    return {
        "rebalance_executed": True,
        "execution_results": execution_results,
        "agent_results": {  # MasterState 공유용
            "portfolio": {
                "rebalancing_executed": True,
                "trades": execution_results,
                "expected_return": state.get("expected_return"),
                "expected_volatility": state.get("expected_volatility"),
            }
        },
        "messages": messages,
    }
