"""
포트폴리오 리스크 계산 도구

매매 실행 전 포트폴리오 리스크 변화를 계산하여 HITL 승인에 필요한 정보를 제공합니다.

Risk Agent 로직을 portfolio_service로 이식하여 재사용
"""
import ast
import json
import logging
from typing import Dict, Any, Optional, List, Tuple

from langchain_core.tools import tool
from pydantic.v1 import BaseModel, Field, validator

from src.services.portfolio_service import (
    calculate_comprehensive_portfolio_risk,
    calculate_concentration_risk_metrics,
    calculate_market_risk_metrics,
    portfolio_service,
)

logger = logging.getLogger(__name__)


# ==================== Helper Functions ====================

def _coerce_number(value: Any, default: float = 0.0) -> float:
    """Safely convert mixed numeric inputs (int/float/str/Decimal) into float."""
    if value in (None, "", "null"):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return default


def _unwrap_portfolio_dict(portfolio: Dict[str, Any]) -> Dict[str, Any]:
    """
    get_portfolio_positions → {"success": True, "data": {...}}
    portfolio_service snapshot → {"portfolio_data": {...}}
    등 다양한 래퍼 구조를 단일 dict로 평탄화한다.
    """
    current = portfolio or {}
    visited = set()

    while True:
        # 순환 참조 방지
        key = id(current)
        if key in visited:
            break
        visited.add(key)

        if isinstance(current, dict):
            for unwrap_key in ("portfolio_data", "data", "portfolio"):
                nested = current.get(unwrap_key)
                if isinstance(nested, dict):
                    current = nested
                    break
            else:
                break
        else:
            break
    return current if isinstance(current, dict) else {}


def _normalize_holdings(raw_holdings: Any) -> List[Dict[str, Any]]:
    """다양한 키 이름을 갖는 보유 종목 리스트를 risk tool이 기대하는 스키마로 정규화."""
    if not isinstance(raw_holdings, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in raw_holdings:
        if not isinstance(item, dict):
            continue

        stock_code = (
            item.get("stock_code")
            or item.get("ticker")
            or item.get("symbol")
            or item.get("code")
        )
        if not stock_code:
            continue

        quantity = _coerce_number(
            item.get("quantity")
            or item.get("qty")
            or item.get("shares")
            or item.get("hldg_qty"),
            default=0.0,
        )
        current_price = _coerce_number(
            item.get("current_price")
            or item.get("price")
            or item.get("currentPrice")
            or item.get("market_price")
            or item.get("prpr"),
            default=0.0,
        )

        if current_price <= 0:
            evaluation = _coerce_number(
                item.get("evaluation")
                or item.get("eval_amount")
                or item.get("market_value")
                or item.get("value")
                or item.get("evlu_amt"),
                default=0.0,
            )
            if quantity > 0:
                current_price = evaluation / quantity

        normalized_item = dict(item)
        normalized_item["stock_code"] = stock_code
        normalized_item["quantity"] = quantity
        normalized_item["current_price"] = current_price
        normalized.append(normalized_item)

    return normalized


def _extract_portfolio_state(portfolio: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], float, float]:
    """Risk Tool이 필요로 하는 holdings/cash/total_value를 다양한 입력에서 추출."""
    normalized_portfolio = _unwrap_portfolio_dict(portfolio)

    raw_holdings = (
        normalized_portfolio.get("holdings")
        or normalized_portfolio.get("positions")
        or normalized_portfolio.get("stocks")
        or []
    )
    holdings = _normalize_holdings(raw_holdings)

    cash_balance = normalized_portfolio.get("cash_balance")
    if cash_balance is None:
        cash_balance = (
            normalized_portfolio.get("cash")
            or normalized_portfolio.get("available_cash")
            or normalized_portfolio.get("cashAmount")
        )
    cash_balance = _coerce_number(cash_balance, default=0.0)

    total_value = (
        normalized_portfolio.get("total_value")
        or normalized_portfolio.get("total_assets")
        or normalized_portfolio.get("total_evaluation")
        or normalized_portfolio.get("portfolio_value")
    )
    total_value = _coerce_number(total_value, default=0.0)

    if total_value <= 0:
        holdings_value = sum(
            h.get("quantity", 0) * h.get("current_price", 0)
            for h in holdings
        )
        total_value = holdings_value + cash_balance

    return holdings, cash_balance, total_value


def _coerce_to_dict(value: Any, field_name: str) -> Dict[str, Any]:
    """LLM이 문자열/리스트로 전달한 payload를 dict로 강제 변환한다."""
    if value is None:
        logger.warning("⚠️ [%s] 값이 비어 있어 기본 dict를 반환합니다.", field_name)
        return {}

    if isinstance(value, dict):
        return value

    if hasattr(value, "dict"):
        try:
            return value.dict()
        except Exception:  # pragma: no cover - 방어적 처리
            pass

    if isinstance(value, str):
        raw_text = value.strip()
        if not raw_text:
            logger.warning("⚠️ [%s] 빈 문자열 입력, 기본 dict를 반환합니다.", field_name)
            return {}

        json_candidates = [raw_text]
        # Python repr(dict) 형태일 경우 작은따옴표를 큰따옴표로 치환해 재시도
        if raw_text.startswith("{") and "'" in raw_text:
            json_candidates.append(raw_text.replace("'", '"'))

        for candidate in json_candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list) and field_name == "portfolio":
                    return {"positions": parsed}
            except json.JSONDecodeError:
                continue

        try:
            parsed_literal = ast.literal_eval(raw_text)
        except (ValueError, SyntaxError):
            parsed_literal = None

        if isinstance(parsed_literal, dict):
            return parsed_literal
        if isinstance(parsed_literal, list) and field_name == "portfolio":
            return {"positions": parsed_literal}

        logger.warning("⚠️ [%s] 문자열을 dict로 변환하지 못했습니다. 입력 타입=%s", field_name, type(value))
        return {}

    if isinstance(value, list):
        if field_name == "portfolio":
            return {"positions": value}

    logger.warning("⚠️ [%s] dict로 파싱할 수 없는 타입입니다: %s", field_name, type(value))
    return {}


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
    user_id: Optional[str] = Field(
        default=None,
        description="선택: 해당 포트폴리오 소유자. 제공 시 잔고 정보가 누락된 경우 snapshot으로 보정합니다.",
    )

    @validator("portfolio", pre=True)
    def validate_portfolio(cls, value: Any) -> Dict[str, Any]:  # noqa: D417 - validator 설명 불필요
        return _coerce_to_dict(value, "portfolio")

    @validator("proposed_trade", pre=True)
    def validate_trade(cls, value: Any) -> Dict[str, Any]:  # noqa: D417 - validator 설명 불필요
        parsed = _coerce_to_dict(value, "proposed_trade")
        if not parsed:
            raise ValueError("proposed_trade는 dict 형태여야 합니다.")
        return parsed


# ==================== Tool ====================

@tool(args_schema=PortfolioRiskInput)
async def calculate_portfolio_risk(
    portfolio: dict,
    proposed_trade: dict,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    [언제] 매매 실행 전, 포트폴리오 리스크 변화를 확인할 때 사용합니다.
    [무엇] 현재 리스크와 매매 후 예상 리스크를 계산합니다.
    [필수] request_trade 또는 HITL 승인을 요청하기 전에 반드시 이 tool을 먼저 호출하세요.

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
    → request_trade(...) 호출 → HITL 패널 승인 대기
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

        # 1. 현재 포트폴리오 상태 분석 (다양한 입력 스키마 허용)
        current_holdings, current_cash, current_total_value = _extract_portfolio_state(portfolio)

        holdings_value = sum(
            h.get("quantity", 0) * h.get("current_price", 0) for h in current_holdings
        )

        if (current_cash <= 0 or current_total_value <= holdings_value) and portfolio_service:
            # HITL 용도로 정확한 현금이 필요하므로 snapshot으로 보정
            try:
                snapshot = await portfolio_service.get_portfolio_snapshot(user_id=user_id)
            except Exception as exc:  # pragma: no cover - fallback용
                logger.warning("⚠️ [Risk Tool] 포트폴리오 snapshot 보정 실패: %s", exc)
                snapshot = None

            if snapshot and snapshot.portfolio_data:
                snapshot_holdings, snapshot_cash, snapshot_total = _extract_portfolio_state(
                    snapshot.portfolio_data
                )
                if snapshot_cash > 0:
                    current_holdings = snapshot_holdings
                    current_cash = snapshot_cash
                    current_total_value = snapshot_total
                    holdings_value = sum(
                        h.get("quantity", 0) * h.get("current_price", 0) for h in current_holdings
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

        # 3. 거래 전후 종목 비중 및 holdings 재구성
        position_weight_before = {}
        holdings_before_structured = []  # service layer용

        for h in current_holdings:
            code = h.get("stock_code")
            if code:
                pos_value = h.get("quantity", 0) * h.get("current_price", 0)
                weight = pos_value / current_total_value if current_total_value > 0 else 0
                position_weight_before[code] = weight

                # service layer 호출용으로 weight 필드 포함
                holdings_before_structured.append({
                    "stock_code": code,
                    "stock_name": h.get("stock_name", code),
                    "weight": weight,
                    "quantity": h.get("quantity", 0),
                    "current_price": h.get("current_price", 0),
                    "sector": h.get("sector", "기타"),  # sector 정보가 없으면 "기타"
                })

        position_weight_after = dict(position_weight_before)
        holdings_after_structured = list(holdings_before_structured)  # 복사

        # 거래 후 대상 종목 비중 계산 및 holdings 업데이트
        if is_buy:
            existing_qty = next((h.get("quantity", 0) for h in current_holdings if h.get("stock_code") == ticker), 0)
            existing_sector = next((h.get("sector", "기타") for h in current_holdings if h.get("stock_code") == ticker), "기타")
            new_qty = existing_qty + quantity
            new_value = new_qty * price
            target_weight_after = new_value / total_value_after if total_value_after > 0 else 0
            position_weight_after[ticker] = target_weight_after

            # holdings_after 업데이트
            found = False
            for h in holdings_after_structured:
                if h["stock_code"] == ticker:
                    h["quantity"] = new_qty
                    h["weight"] = target_weight_after
                    found = True
                    break
            if not found:  # 신규 종목
                holdings_after_structured.append({
                    "stock_code": ticker,
                    "stock_name": ticker,
                    "weight": target_weight_after,
                    "quantity": new_qty,
                    "current_price": price,
                    "sector": existing_sector,
                })
        else:  # sell
            existing_qty = next((h.get("quantity", 0) for h in current_holdings if h.get("stock_code") == ticker), 0)
            remaining_qty = existing_qty - quantity
            if remaining_qty > 0:
                new_value = remaining_qty * price
                target_weight_after = new_value / total_value_after if total_value_after > 0 else 0
                position_weight_after[ticker] = target_weight_after

                # holdings_after 업데이트
                for h in holdings_after_structured:
                    if h["stock_code"] == ticker:
                        h["quantity"] = remaining_qty
                        h["weight"] = target_weight_after
                        break
            else:
                target_weight_after = 0.0
                position_weight_after.pop(ticker, None)

                # holdings_after에서 제거
                holdings_after_structured = [h for h in holdings_after_structured if h["stock_code"] != ticker]

        # 4. 섹터별 비중 계산 (거래 전/후)
        sectors_before = {}
        for h in holdings_before_structured:
            sector = h.get("sector", "기타")
            sectors_before[sector] = sectors_before.get(sector, 0) + h["weight"]

        sectors_after = {}
        for h in holdings_after_structured:
            sector = h.get("sector", "기타")
            sectors_after[sector] = sectors_after.get(sector, 0) + h["weight"]

        # 5. Service layer를 사용한 리스크 계산
        # 5.1 거래 전 집중도 리스크
        concentration_before = calculate_concentration_risk_metrics(
            holdings_before_structured, sectors_before
        )

        # 5.2 거래 후 집중도 리스크
        concentration_after = calculate_concentration_risk_metrics(
            holdings_after_structured, sectors_after
        )

        # 5.3 거래 전 시장 리스크
        # portfolio 인자에서 market_data 추출 시도
        normalized_portfolio = _unwrap_portfolio_dict(portfolio)
        market_data_input = normalized_portfolio.get("market_data", {})

        portfolio_data_before = {
            "holdings": holdings_before_structured,
            "total_value": current_total_value,
        }
        market_risk_before = calculate_market_risk_metrics(
            portfolio_data_before, market_data_input
        )

        # 5.4 거래 후 시장 리스크
        portfolio_data_after = {
            "holdings": holdings_after_structured,
            "total_value": total_value_after,
        }
        market_risk_after = calculate_market_risk_metrics(
            portfolio_data_after, market_data_input
        )

        # 집중도 및 시장 리스크 추출
        hhi_before = concentration_before["hhi"]
        hhi_after = concentration_after["hhi"]
        max_stock_weight_before = concentration_before["top_holding"]["weight"]
        max_stock_weight_after = concentration_after["top_holding"]["weight"]

        volatility_before = market_risk_before["portfolio_volatility"]
        volatility_after = market_risk_after["portfolio_volatility"]
        beta_before = market_risk_before["portfolio_beta"]
        beta_after = market_risk_after["portfolio_beta"]
        var_95_before = market_risk_before["var_95"]
        var_95_after = market_risk_after["var_95"]

        # 6. 리스크 레벨 및 경고 생성
        warnings = []

        # 집중도 경고 (service layer에서 계산된 경고 포함)
        if concentration_after.get("warnings"):
            warnings.extend(concentration_after["warnings"])

        # 추가 집중도 경고
        if max_stock_weight_after > 0.40:
            if not any("비중" in w for w in warnings):  # 중복 방지
                warnings.append(f"⚠️⚠️ 단일 종목 비중 {max_stock_weight_after*100:.0f}% (권장: 30% 이하)")
        elif max_stock_weight_after > 0.30:
            if not any("비중" in w for w in warnings):
                warnings.append(f"⚠️ 단일 종목 비중 {max_stock_weight_after*100:.0f}%")

        # 현금 비중 경고
        if cash_ratio_after < 0.05:
            warnings.append(f"🚨 현금 비중 {cash_ratio_after*100:.1f}% - 긴급 자금 부족 위험")
        elif cash_ratio_after < 0.10:
            warnings.append(f"⚠️ 현금 비중 {cash_ratio_after*100:.1f}% - 유동성 리스크 주의")

        # 시장 리스크 경고
        if market_risk_after["risk_level"] == "high":
            warnings.append(f"⚠️ 높은 시장 리스크: VaR(95%) {var_95_after*100:.1f}%")

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
                "volatility": volatility_before,
                "beta": beta_before,
                "var_95": var_95_before,
                "concentration_level": concentration_before["level"],
                "top_holding": concentration_before["top_holding"],
                "top_sector": concentration_before["top_sector"],
            },
            "after_trade_risk": {
                "cash_balance": cash_after,
                "cash_ratio": cash_ratio_after,
                "max_stock_weight": max_stock_weight_after,
                "hhi": hhi_after,
                "target_stock_weight": position_weight_after.get(ticker, 0),
                "concentration": max_stock_weight_after,
                "volatility": volatility_after,
                "beta": beta_after,
                "var_95": var_95_after,
                "concentration_level": concentration_after["level"],
                "top_holding": concentration_after["top_holding"],
                "top_sector": concentration_after["top_sector"],
            },
            "risk_change": {
                "concentration": f"{(max_stock_weight_after - max_stock_weight_before)*100:+.1f}%p",
                "cash_ratio": f"{(cash_ratio_after - cash_ratio_before)*100:+.1f}%p",
                "volatility": f"{(volatility_after - volatility_before)*100:+.1f}%p",
                "beta": f"{(beta_after - beta_before):+.2f}",
                "var_95": f"{(var_95_after - var_95_before)*100:+.1f}%p",
                "hhi": f"{(hhi_after - hhi_before):+.3f}",
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
