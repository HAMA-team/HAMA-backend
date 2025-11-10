"""
Trading Agent 노드 함수들

단순화된 구조: prepare_trade → approval_trade → execute_trade
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from src.agents.trading.state import TradingState
from src.services import OrderNotFoundError, PortfolioNotFoundError, trading_service
from src.utils.llm_factory import get_default_agent_llm as get_llm
from src.utils.json_parser import safe_json_parse
from src.schemas.hitl_config import HITLConfig, PRESET_COPILOT

logger = logging.getLogger(__name__)


# ==================== Core Nodes (3개만 유지) ====================


async def prepare_trade_node(state: TradingState) -> dict:
    """
    1단계: 주문 생성 및 기본 정보 정리

    LLM을 사용하여 query에서 매수/매도, 수량을 추출합니다.
    """
    if state.get("trade_prepared"):
        logger.info("⏭️ [Trade] 이미 준비된 주문이 있어 재사용합니다")
        return {}

    stock_code = state.get("stock_code")
    query = state.get("query", "")
    messages = list(state.get("messages", []))

    if not stock_code:
        error = "stock_code가 필요합니다."
        logger.warning("⚠️ [Trade] %s", error)
        return {**state, "error": error, "messages": messages}

    # 1. LLM으로 query 분석 (order_type, quantity 추출)
    logger.info("🔍 [Trade] 주문 내용 분석 중: %s", query)

    llm = get_llm(max_tokens=500, temperature=0)

    analysis_prompt = f"""다음 요청을 분석하세요:

요청: "{query}"
종목코드: {stock_code}

먼저 이것이 **조회 요청**인지 **매매 요청**인지 판단하세요.

**조회 요청 예시** (이런 경우 is_query_only: true):
- "삼성전자 몇 주 있지?"
- "현재 보유 중인 삼성전자 수량은?"
- "삼성전자 얼마나 가지고 있어?"
- "내가 삼성전자 있어?"

**매매 요청 예시** (이런 경우 is_query_only: false):
- "삼성전자 10주 매수"
- "삼성전자 가지고 있는거 다 팔아"
- "삼성전자 50% 매도"

다음 정보를 JSON 형식으로 추출하세요:
{{
  "is_query_only": true | false,
  "order_type": "BUY" | "SELL" | null,
  "quantity_type": "specific" | "all" | "percentage" | null,
  "quantity_value": <숫자> | null,
  "reasoning": "판단 근거"
}}

규칙:
- is_query_only: 단순 조회 요청이면 true, 매매 요청이면 false
- 조회 요청(is_query_only: true)이면 order_type, quantity_type, quantity_value는 null
- 매매 요청(is_query_only: false)이면:
  * order_type: 매수 관련 키워드(매수, 사다, buy) → BUY / 매도 관련 키워드(매도, 팔다, 판다, 청산, 전량, sell) → SELL
  * quantity_type:
    - "specific": "10주", "20주" 같이 명확한 수량 지정
    - "all": "전량", "다 팔아", "모두" 같이 보유 전체 매도
    - "percentage": "50%", "절반" 같이 비율 지정
  * quantity_value:
    - specific → 주문 수량
    - all → 0 (나중에 포트폴리오에서 조회)
    - percentage → 비율 (예: 50)

예시:
- "삼성전자 몇 주 있지?" → {{"is_query_only": true, "order_type": null, "quantity_type": null, "quantity_value": null}}
- "삼성전자 10주 매수" → {{"is_query_only": false, "order_type": "BUY", "quantity_type": "specific", "quantity_value": 10}}
- "삼성전자 가지고 있는거 다 팔아" → {{"is_query_only": false, "order_type": "SELL", "quantity_type": "all", "quantity_value": 0}}
"""

    try:
        response = await llm.ainvoke(analysis_prompt)
        analysis = safe_json_parse(response.content, "TradingAnalysis")

        if not isinstance(analysis, dict):
            raise ValueError("LLM 응답을 파싱할 수 없습니다")

        is_query_only = analysis.get("is_query_only", False)
        reasoning = analysis.get("reasoning", "")

        # 조회 요청인 경우 에러 반환 (Portfolio Agent가 처리해야 함)
        if is_query_only:
            error = f"보유 수량 조회는 Portfolio Agent에서 처리합니다. 매매 요청이 아닙니다."
            logger.info("⏭️ [Trade] 조회 요청 감지 - Portfolio로 이동 필요: %s", query)
            return {**state, "error": error, "is_query_only": True, "messages": messages}

        order_type = analysis.get("order_type", "BUY")
        if order_type:
            order_type = order_type.upper()
        else:
            order_type = "BUY"

        quantity_type = analysis.get("quantity_type", "specific")
        quantity_value = analysis.get("quantity_value", 10)

        logger.info("✅ [Trade] 분석 완료: %s, %s, %d - %s",
                   order_type, quantity_type, quantity_value if quantity_value else 0, reasoning)

        # 2. 수량 계산
        quantity = quantity_value

        # "전량 매도"인 경우 포트폴리오에서 보유 수량 조회
        if quantity_type == "all" and order_type == "SELL":
            from src.services import portfolio_service
            try:
                snapshot = await portfolio_service.get_portfolio_snapshot(
                    user_id=state.get("user_id"),
                    portfolio_id=state.get("portfolio_id")
                )
                if snapshot and snapshot.portfolio_data:
                    holdings = snapshot.portfolio_data.get("holdings", [])
                    for holding in holdings:
                        if holding.get("stock_code") == stock_code:
                            quantity = int(holding.get("quantity", 0))
                            logger.info("📊 [Trade] 보유 수량 조회: %d주", quantity)
                            break

                if quantity == 0:
                    error = f"{stock_code} 종목을 보유하고 있지 않습니다."
                    logger.warning("⚠️ [Trade] %s", error)
                    return {**state, "error": error, "messages": messages}
            except Exception as exc:
                logger.warning("⚠️ [Trade] 포트폴리오 조회 실패, 기본값 사용: %s", exc)
                quantity = 10  # fallback

        # "비율 매도"인 경우 계산
        elif quantity_type == "percentage":
            from src.services import portfolio_service
            try:
                snapshot = await portfolio_service.get_portfolio_snapshot(
                    user_id=state.get("user_id"),
                    portfolio_id=state.get("portfolio_id")
                )
                if snapshot and snapshot.portfolio_data:
                    holdings = snapshot.portfolio_data.get("holdings", [])
                    for holding in holdings:
                        if holding.get("stock_code") == stock_code:
                            total_quantity = int(holding.get("quantity", 0))
                            quantity = int(total_quantity * quantity_value / 100)
                            logger.info("📊 [Trade] %d%% 계산: %d주 / %d주",
                                       quantity_value, quantity, total_quantity)
                            break
            except Exception as exc:
                logger.warning("⚠️ [Trade] 비율 계산 실패: %s", exc)

        if quantity <= 0:
            error = "주문 수량이 0 이하입니다."
            logger.warning("⚠️ [Trade] %s", error)
            return {**state, "error": error, "messages": messages}

    except Exception as exc:
        logger.error("❌ [Trade] 주문 분석 실패: %s", exc)
        # Fallback: 기존 state에서 가져오기
        order_type = (state.get("order_type") or "BUY").upper()
        quantity = state.get("quantity", 10)

    # 3. 주문 생성
    try:
        order = await trading_service.create_pending_order(
            user_id=state.get("user_id"),
            portfolio_id=state.get("portfolio_id"),
            stock_code=stock_code,
            order_type=order_type,
            quantity=int(quantity),
            order_price=state.get("order_price"),
            order_price_type=state.get("order_price_type"),
            notes=state.get("order_note") or query,
        )
    except PortfolioNotFoundError as exc:
        logger.error("❌ [Trade] 포트폴리오가 존재하지 않습니다: %s", exc)
        return {**state, "error": str(exc), "messages": messages}
    except Exception as exc:  # pragma: no cover - 방어 로깅
        logger.exception("❌ [Trade] 주문 생성 실패: %s", exc)
        return {**state, "error": str(exc), "messages": messages}

    logger.info("✅ [Trade] 주문 생성 완료: %s (%s %d주)", order["order_id"], order_type, quantity)

    return {
        "trade_prepared": True,
        "trade_order_id": order["order_id"],
        "trade_summary": order,
        "portfolio_id": order.get("portfolio_id") or state.get("portfolio_id"),
        "order_type": order_type,  # State에 저장 (다른 노드에서 참조)
        "quantity": quantity,
        "messages": messages,
    }


async def approval_trade_node(state: TradingState) -> dict:
    """
    매매 승인 노드 (HITL Interrupt Point)

    자동화 레벨에 따라 승인 여부를 결정합니다:
    - Level 1 (Pilot): 자동 승인
    - Level 2 (Copilot): 사용자 승인 필요
    - Level 3 (Advisor): 사용자 승인 필요
    """
    # 이미 승인된 경우 스킵
    if state.get("trade_approved"):
        logger.info("⏭️ [Trade] 이미 승인된 주문입니다")
        return {}

    # automation_level 직접 확인: 1이면 무조건 자동 승인
    automation_level = state.get("automation_level", 2)
    if automation_level == 1:
        logger.info("✅ [Trade] 자동화 레벨 1 (Pilot) - 매매 자동 승인")
        return {
            "trade_approved": True,
            "approval_type": "automatic",
            "skip_hitl": True,
        }

    config_raw = state.get("hitl_config") or PRESET_COPILOT.model_dump()
    hitl_config = HITLConfig.model_validate(config_raw)
    trade_phase = hitl_config.phases.trade
    risk_level = state.get("risk_level", "medium")


    # Pilot 조건부 자동 승인 (legacy)
    if trade_phase == "conditional" and risk_level == "low":
        logger.info("✅ [Trade] 조건부 자동 승인 (낮은 리스크)")
        return {
            "trade_approved": True,
            "approval_type": "automatic",
            "skip_hitl": True,
        }

    summary = state.get("trade_summary") or {}
    order_details = {
        "type": "trade_approval",
        "order_id": state.get("trade_order_id", "UNKNOWN"),
        "query": state.get("query", ""),
        "stock_code": summary.get("stock_code") or state.get("stock_code"),
        "quantity": summary.get("order_quantity") or state.get("quantity"),
        "order_type": summary.get("order_type") or state.get("order_type"),
        "order_price": summary.get("order_price") or state.get("order_price"),
        "estimated_price": summary.get("order_price") or state.get("order_price"),
        "total_amount": (summary.get("order_quantity") or state.get("quantity") or 0)
        * (summary.get("order_price") or state.get("order_price") or 0),
        "risk_level": risk_level,
        "risk_factors": state.get("risk_factors", []),
        "message": "매매 주문을 승인하시겠습니까?",
    }

    if not trade_phase:
        logger.info("✅ [Trade] HITL 불필요 - 자동 승인 (preset=%s)", hitl_config.preset)
        return {"trade_approved": True}

    logger.info("🔔 [Trade] 사용자 승인을 요청합니다 (preset=%s)", hitl_config.preset)

    # LangGraph interrupt: payload 대신 order_details만 반환
    user_response = interrupt(order_details)

    logger.info("🟢 [Trade] 사용자 결정 수신: %s", user_response)

    decision = (user_response or {}).get("decision")
    messages = list(state.get("messages", []))

    if decision == "approved":
        return {
            "trade_approved": True,
            "approval_type": "manual",
            "user_notes": user_response.get("notes"),
            "messages": messages,
        }
    if decision == "rejected":
        return {
            "trade_approved": False,
            "rejection_reason": user_response.get("reason"),
            "messages": messages,
        }
    if decision == "modified":
        modifications = user_response.get("modifications", {})
        return {
            "trade_approved": True,
            "approval_type": "modified",
            "modified_quantity": modifications.get("quantity", state.get("quantity")),
            "user_notes": user_response.get("notes"),
            "messages": messages,
        }

    logger.warning("⚠️ [Trade] 알 수 없는 사용자 결정, 거래를 중단합니다: %s", user_response)
    return {
        "trade_approved": False,
        "rejection_reason": "unknown_decision",
        "messages": messages,
    }


async def execute_trade_node(state: TradingState) -> dict:
    """3단계: 승인된 주문을 실제로 실행하고 결과를 반환."""
    if state.get("trade_executed"):
        logger.info("⏭️ [Trade] 이미 실행된 주문입니다")
        return {}

    if not state.get("trade_approved"):
        warning = "거래가 승인되지 않았습니다."
        logger.warning("⚠️ [Trade] %s", warning)
        return {"error": warning}

    order_id = state.get("trade_order_id")
    if not order_id:
        error = "주문 ID가 존재하지 않아 실행할 수 없습니다."
        logger.error("❌ [Trade] %s", error)
        return {"error": error}

    logger.info("💰 [Trade] 주문 실행 시작: %s", order_id)

    try:
        result = await trading_service.execute_order(
            order_id,
            execution_price=state.get("execution_price") or state.get("order_price"),
            automation_level=state.get("automation_level", 2),
        )
    except OrderNotFoundError as exc:
        logger.error("❌ [Trade] 주문을 찾을 수 없습니다: %s", exc)
        return {"error": str(exc)}
    except Exception as exc:  # pragma: no cover - 방어
        logger.exception("❌ [Trade] 주문 실행 실패: %s", exc)
        return {"error": str(exc)}

    if result.get("status") == "rejected":
        logger.warning("⚠️ [Trade] 주문이 거부되었습니다: %s", result.get("error"))
        return {"trade_result": result, "error": result.get("error")}

    messages = list(state.get("messages", []))
    summary = _format_trade_summary(result)
    messages.append(AIMessage(content=summary))

    # MasterState(GraphState)로 결과 전달
    # agent_results는 간단한 요약만 포함 (프론트엔드 직렬화 문제 방지)
    return {
        "trade_executed": True,
        "trade_result": result,  # TradingState 내부용
        "portfolio_snapshot": result.get("portfolio_snapshot"),
        "agent_results": {  # MasterState 공유용
            "trading": {
                "status": result.get("status"),
                "summary": summary,
                "order_id": result.get("order_id"),
                "kis_order_no": result.get("kis_order_no"),
                "kis_executed": result.get("kis_executed", False),
            }
        },
        "messages": messages,
    }


def _format_trade_summary(result: Dict[str, Any]) -> str:
    order_type = str(result.get("order_type", "BUY")).upper()
    quantity = int(result.get("quantity") or 0)
    price = float(result.get("price") or 0)
    total = float(result.get("total") or price * quantity)
    return f"{order_type} {quantity}주 @ {price:,.0f}원 (총 {total:,.0f}원)"
