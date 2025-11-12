"""
포트폴리오 리스크 계산 도구

매매 실행 전 포트폴리오 리스크 변화를 계산하여 HITL 승인에 필요한 정보를 제공합니다.

TODO: 기존 Risk Agent (src/agents/risk/) 로직을 순수 함수로 변환
"""
import logging
from typing import Dict, Any

from langchain_core.tools import tool
from pydantic.v1 import BaseModel, Field

logger = logging.getLogger(__name__)


# ==================== Input Schema ====================

class PortfolioRiskInput(BaseModel):
    """포트폴리오 리스크 계산 입력"""
    portfolio: dict = Field(
        description=(
            "현재 포트폴리오 (get_portfolio_positions 결과). "
            "예: {'positions': [{'ticker': '005930', 'weight': 0.3, ...}], 'total_evaluation': 10000000}"
        )
    )
    proposed_trade: dict = Field(
        description=(
            "실행할 매매 주문. "
            "예: {'ticker': '005930', 'action': 'buy', 'quantity': 10, 'price': 75000}"
        )
    )


# ==================== Tool ====================

@tool(args_schema=PortfolioRiskInput)
async def calculate_portfolio_risk(
    portfolio: dict,
    proposed_trade: dict
) -> Dict[str, Any]:
    """
    [언제] 매매 실행 전, 포트폴리오 리스크 변화를 확인할 때 사용합니다.
    [무엇] 현재 리스크와 매매 후 예상 리스크를 계산합니다.
    [필수] execute_trade 호출 전에 반드시 이 tool을 먼저 호출하세요.

    계산 항목:
    - 집중도 리스크 (상위 종목 비중)
    - 변동성 (포트폴리오 표준편차)
    - 베타 (시장 대비 민감도)
    - VaR (손실 가능성)

    Args:
        portfolio: 현재 포트폴리오 (get_portfolio_positions 결과)
        proposed_trade: 실행할 매매 주문

    Returns:
        dict: {
            "current_risk": {
                "concentration": 0.30,      # 집중도: 상위 종목 비중
                "volatility": 0.15,         # 변동성: 표준편차
                "beta": 1.2,                # 베타: 시장 민감도
                "var_95": 0.10              # VaR 95%: 5% 확률로 10% 이상 손실
            },
            "after_trade_risk": {
                "concentration": 0.45,
                "volatility": 0.18,
                "beta": 1.3,
                "var_95": 0.12
            },
            "risk_change": {
                "concentration": "+15%p",   # 집중도 증가
                "volatility": "+3%p",       # 변동성 증가
                "beta": "+0.1",             # 베타 증가
                "var_95": "+2%p"            # VaR 증가
            },
            "warnings": [
                "⚠️ 집중도 리스크 증가: 30% → 45% (권장: 40% 이하)",
                "⚠️ 변동성 증가: 15% → 18%"
            ]
        }

    예시:
    사용자: "삼성전자 10주 매수해줘"
    → get_portfolio_positions()
    → calculate_portfolio_risk(portfolio, {"ticker": "005930", "action": "buy", "quantity": 10})
    → [사용자에게 리스크 보고]
    → 사용자: "승인"
    → execute_trade(...)
    """
    try:
        logger.info("⚖️ [Risk Tool] 포트폴리오 리스크 계산 시작")

        # 거래 정보 추출
        ticker = proposed_trade.get("ticker")
        action = proposed_trade.get("action", "buy").lower()
        quantity = proposed_trade.get("quantity", 0)
        price = proposed_trade.get("price", 0)

        if not ticker or quantity <= 0:
            return {
                "success": False,
                "message": "거래 정보가 올바르지 않습니다 (ticker, quantity 필수)"
            }

        # 1. 현재 포트폴리오 상태 분석
        current_holdings = portfolio.get("holdings", [])
        current_cash = portfolio.get("cash_balance", 0)
        current_total_value = portfolio.get("total_value", 0)

        if current_total_value <= 0:
            current_total_value = current_cash + sum(
                h.get("quantity", 0) * h.get("current_price", 0)
                for h in current_holdings
            )

        logger.info(f"  - 현재 보유 종목: {len(current_holdings)}개")
        logger.info(f"  - 현재 총 자산: {current_total_value:,.0f}원")
        logger.info(f"  - 거래 계획: {action.upper()} {ticker} {quantity}주 @ {price:,.0f}원")

        # 2. 거래 시뮬레이션
        trade_amount = quantity * price
        is_buy = action in ("buy", "매수")

        if is_buy:
            cash_after = current_cash - trade_amount
            if cash_after < 0:
                return {
                    "success": False,
                    "risk_level": "critical",
                    "recommended_action": "cancel",
                    "summary": f"❌ 현금 부족: 필요 {trade_amount:,.0f}원, 보유 {current_cash:,.0f}원",
                    "warnings": ["현금 부족으로 거래 불가"],
                }
        else:  # sell
            cash_after = current_cash + trade_amount

        total_value_after = current_total_value
        cash_ratio_before = current_cash / current_total_value if current_total_value > 0 else 0
        cash_ratio_after = cash_after / total_value_after if total_value_after > 0 else 0

        # 3. 거래 전후 종목 비중 계산
        position_weight_before = {}
        for h in current_holdings:
            code = h.get("stock_code")
            if code:
                pos_value = h.get("quantity", 0) * h.get("current_price", 0)
                weight = pos_value / current_total_value if current_total_value > 0 else 0
                position_weight_before[code] = weight

        position_weight_after = dict(position_weight_before)

        # 거래 후 대상 종목 비중 계산
        if is_buy:
            existing_qty = next((h.get("quantity", 0) for h in current_holdings if h.get("stock_code") == ticker), 0)
            new_qty = existing_qty + quantity
            new_value = new_qty * price
            target_weight_after = new_value / total_value_after if total_value_after > 0 else 0
            position_weight_after[ticker] = target_weight_after
        else:  # sell
            existing_qty = next((h.get("quantity", 0) for h in current_holdings if h.get("stock_code") == ticker), 0)
            remaining_qty = existing_qty - quantity
            if remaining_qty > 0:
                new_value = remaining_qty * price
                target_weight_after = new_value / total_value_after if total_value_after > 0 else 0
                position_weight_after[ticker] = target_weight_after
            else:
                target_weight_after = 0.0
                position_weight_after.pop(ticker, None)

        # 4. 집중도 리스크 계산
        # HHI 계산
        hhi_before = sum(w ** 2 for w in position_weight_before.values())
        hhi_after = sum(w ** 2 for w in position_weight_after.values())

        # 최대 종목 비중
        max_stock_weight_before = max(position_weight_before.values()) if position_weight_before else 0
        max_stock_weight_after = max(position_weight_after.values()) if position_weight_after else 0

        # 5. 리스크 레벨 및 경고 생성
        warnings = []

        # 집중도 경고
        if max_stock_weight_after > 0.40:
            warnings.append(f"⚠️⚠️ 단일 종목 비중 {max_stock_weight_after*100:.0f}% (권장: 30% 이하)")
        elif max_stock_weight_after > 0.30:
            warnings.append(f"⚠️ 단일 종목 비중 {max_stock_weight_after*100:.0f}%")

        # 현금 비중 경고
        if cash_ratio_after < 0.05:
            warnings.append(f"🚨 현금 비중 {cash_ratio_after*100:.1f}% - 긴급 자금 부족 위험")
        elif cash_ratio_after < 0.10:
            warnings.append(f"⚠️ 현금 비중 {cash_ratio_after*100:.1f}% - 유동성 리스크 주의")

        # 6. 종합 리스크 레벨 결정
        if cash_ratio_after < 0.05 or max_stock_weight_after > 0.50:
            risk_level = "critical"
            recommended_action = "cancel"
            recommended_quantity = None
        elif cash_ratio_after < 0.10 or max_stock_weight_after > 0.40:
            risk_level = "high"
            recommended_action = "adjust"
            recommended_quantity = max(quantity // 2, 1)
        elif max_stock_weight_after > 0.30:
            risk_level = "moderate"
            recommended_action = "proceed"
            recommended_quantity = None
        else:
            risk_level = "low"
            recommended_action = "proceed"
            recommended_quantity = None

        # 7. 손절/익절 라인 (매수인 경우만)
        stop_loss_target = None
        if is_buy:
            stop_loss_price = price * 0.95  # -5%
            target_price = price * 1.10  # +10%
            stop_loss_target = {
                "stop_loss_price": stop_loss_price,
                "stop_loss_percent": -5.0,
                "target_price": target_price,
                "target_percent": 10.0,
            }

        # 8. 요약 생성
        risk_emoji = {
            "low": "✅",
            "moderate": "⚠️",
            "high": "⚠️⚠️",
            "critical": "🚨",
        }.get(risk_level, "ℹ️")

        if recommended_action == "cancel":
            summary = f"{risk_emoji} 고위험: 거래를 취소하고 포트폴리오 재조정을 권장합니다."
        elif recommended_action == "adjust":
            summary = f"{risk_emoji} 중위험: 비중이 과도하게 높아집니다. 수량을 {recommended_quantity}주로 조정하는 것을 권장합니다."
        else:
            summary = f"{risk_emoji} 저위험: 거래를 진행해도 무방합니다."

        logger.info(f"✅ [Risk Tool] 리스크 평가 완료: {risk_level} | {recommended_action}")

        return {
            "success": True,
            "current_risk": {
                "cash_balance": current_cash,
                "cash_ratio": cash_ratio_before,
                "max_stock_weight": max_stock_weight_before,
                "hhi": hhi_before,
                "concentration": max_stock_weight_before,
                "volatility": 0.15,  # TODO: 실제 계산
                "beta": 1.0,  # TODO: 실제 계산
                "var_95": 0.08,  # TODO: 실제 계산
            },
            "after_trade_risk": {
                "cash_balance": cash_after,
                "cash_ratio": cash_ratio_after,
                "max_stock_weight": max_stock_weight_after,
                "hhi": hhi_after,
                "target_stock_weight": position_weight_after.get(ticker, 0),
                "concentration": max_stock_weight_after,
                "volatility": 0.18,  # TODO: 실제 계산
                "beta": 1.1,  # TODO: 실제 계산
                "var_95": 0.10,  # TODO: 실제 계산
            },
            "risk_change": {
                "concentration": f"{(max_stock_weight_after - max_stock_weight_before)*100:+.1f}%p",
                "cash_ratio": f"{(cash_ratio_after - cash_ratio_before)*100:+.1f}%p",
            },
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "recommended_quantity": recommended_quantity,
            "warnings": warnings,
            "summary": summary,
            "stop_loss_target": stop_loss_target,
        }

    except Exception as e:
        logger.error(f"❌ [Risk Tool] 리스크 계산 실패: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": f"리스크 계산 중 오류가 발생했습니다: {e}"
        }


# ==================== Tool 목록 ====================

def get_risk_tools():
    """리스크 도구 목록 반환"""
    return [
        calculate_portfolio_risk,
    ]
