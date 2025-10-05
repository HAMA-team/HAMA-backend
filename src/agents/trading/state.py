"""
Trading Agent State 정의

매매 실행을 위한 State
"""
from typing import TypedDict, Optional


class TradingState(TypedDict):
    """
    Trading Agent 서브그래프 State

    Flow:
    1. prepare_trade: 거래 준비 (부작용)
    2. approval_trade: HITL 승인 (interrupt)
    3. execute_trade: 거래 실행 (부작용)
    """

    # 입력
    request_id: str
    """요청 ID"""

    query: str
    """사용자 질의 (매매 요청)"""

    automation_level: int
    """자동화 레벨 (1-3)"""

    # 매매 정보 (LLM이 추출해야 할 정보)
    stock_code: Optional[str]
    """종목 코드"""

    quantity: Optional[int]
    """수량"""

    order_type: Optional[str]
    """주문 유형 (buy, sell)"""

    # 실행 플래그
    trade_prepared: bool
    """거래 준비 완료 여부"""

    trade_approved: bool
    """거래 승인 완료 여부"""

    trade_executed: bool
    """거래 실행 완료 여부"""

    # 결과
    trade_order_id: Optional[str]
    """주문 ID"""

    trade_result: Optional[dict]
    """거래 실행 결과"""

    # 메타데이터
    error: Optional[str]
    """에러 메시지"""
