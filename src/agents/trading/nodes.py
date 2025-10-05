"""
Trading Agent 노드 함수들

매매 실행 워크플로우를 위한 노드들
"""
import logging
from langgraph.types import interrupt
from langchain_core.messages import AIMessage
from src.agents.trading.state import TradingState

logger = logging.getLogger(__name__)


def prepare_trade_node(state: TradingState) -> dict:
    """
    1단계: 거래 준비 (부작용)

    패턴: 노드 분리 - interrupt 전 부작용 격리
    """
    # 재실행 방지 플래그 체크
    if state.get("trade_prepared"):
        logger.info("⏭️ [Trade] 이미 준비됨, 스킵")
        return {}

    logger.info("📝 [Trade] 거래 준비 중...")

    # TODO Phase 2: 실제 DB에 주문 생성
    # order_id = db.create_order({
    #     "stock": state["stock_code"],
    #     "quantity": state["quantity"],
    #     "status": "pending"
    # })

    # Mock 구현
    import uuid
    order_id = f"ORDER_{str(uuid.uuid4())[:8]}"

    logger.info(f"✅ [Trade] 주문 생성: {order_id}")

    # Supervisor 호환성: messages 전파
    messages = list(state.get("messages", []))

    return {
        "trade_prepared": True,
        "trade_order_id": order_id,
        "messages": messages,
    }


def approval_trade_node(state: TradingState) -> dict:
    """
    2단계: HITL 승인 (interrupt)

    패턴: 노드 분리 - interrupt만 포함, 부작용 없음
    이 노드는 재실행되어도 안전함
    """
    # 이미 승인되었으면 스킵
    if state.get("trade_approved"):
        logger.info("⏭️ [Trade] 이미 승인됨, 스킵")
        return {}

    logger.info("🔔 [Trade] 사용자 승인 요청 중...")

    order_id = state.get("trade_order_id", "UNKNOWN")
    query = state.get("query", "")
    automation_level = state.get("automation_level", 2)

    # 🔴 Interrupt 발생 - 사용자 승인 대기
    approval = interrupt({
        "type": "trade_approval",
        "order_id": order_id,
        "query": query,
        "stock_code": state.get("stock_code"),
        "quantity": state.get("quantity"),
        "order_type": state.get("order_type"),
        "automation_level": automation_level,
        "message": f"매매 주문 '{order_id}'을(를) 승인하시겠습니까?"
    })

    logger.info(f"✅ [Trade] 승인 완료: {approval}")

    # TODO Phase 2: DB 업데이트
    # db.update(order_id, {"approved": True, "approved_by": approval.get("user_id")})

    # Supervisor 호환성: messages 전파
    messages = list(state.get("messages", []))

    return {
        "trade_approved": True,
        "messages": messages,
    }


def execute_trade_node(state: TradingState) -> dict:
    """
    3단계: 거래 실행 (부작용)

    패턴: 멱등성 보장 - 중복 실행 방지
    """
    # 이미 실행되었으면 스킵
    if state.get("trade_executed"):
        logger.info("⏭️ [Trade] 이미 실행됨, 스킵")
        return {}

    order_id = state.get("trade_order_id")

    # 승인 확인
    if not state.get("trade_approved"):
        logger.warning("⚠️ [Trade] 승인되지 않음, 실행 불가")
        return {"error": "거래가 승인되지 않았습니다."}

    logger.info(f"💰 [Trade] 거래 실행 중... (주문: {order_id})")

    # TODO Phase 2: 멱등성 체크
    # existing = db.get_order(order_id)
    # if existing and existing["status"] == "executed":
    #     return {"trade_executed": True, "trade_result": existing["result"]}

    # TODO Phase 2: 실제 API 호출 (한국투자증권)
    # with db.transaction():
    #     result = kis_api.execute_trade(...)
    #     db.update(order_id, {"status": "executed", "result": result})

    # Mock 실행
    result = {
        "order_id": order_id,
        "status": "executed",
        "executed_at": "2025-10-05 10:30:00",
        "stock_code": state.get("stock_code", "005930"),
        "price": 70000,
        "quantity": state.get("quantity", 10),
        "total": 70000 * state.get("quantity", 10),
        "order_type": state.get("order_type", "buy"),
    }

    logger.info(f"✅ [Trade] 거래 실행 완료: {result}")

    # Supervisor 호환성을 위해 messages 포함
    messages = list(state.get("messages", []))
    summary = f"{result['order_type'].upper()} {result['quantity']}주 @ {result['price']:,}원 (총 {result['total']:,}원)"
    messages.append(AIMessage(content=summary))

    return {
        "trade_executed": True,
        "trade_result": result,
        "messages": messages,
    }
