"""
Trading Agent State 정의

매매 실행을 위한 State (단순화된 구조)
"""
from typing import TypedDict, Optional, List, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.schemas.hitl_config import HITLConfig


class TradingState(TypedDict):
    """
    Trading Agent 서브그래프 State (단순화된 구조)

    Flow:
    1. prepare_trade: LLM으로 query 분석 + 주문 생성
    2. approval_trade: HITL 승인 대기
    3. execute_trade: 실제 주문 실행
    """

    # Supervisor 패턴 호환성
    messages: Annotated[List[BaseMessage], add_messages]
    """메시지 스택 (Supervisor 패턴 필수)"""

    # 입력
    request_id: str
    """요청 ID"""

    user_id: Optional[str]
    """사용자 ID"""

    portfolio_id: Optional[str]
    """포트폴리오 ID"""

    query: str
    """사용자 질의 (매매 요청)"""

    hitl_config: HITLConfig
    """자동화 레벨/단계별 HITL 설정"""

    automation_level: Optional[int]
    """자동화 레벨 (1: Pilot, 2: Copilot, 3: Advisor)"""

    # 매매 정보 (prepare_trade에서 LLM이 추출)
    stock_code: Optional[str]
    """종목 코드"""

    quantity: Optional[int]
    """수량"""

    order_type: Optional[str]
    """주문 유형 (BUY, SELL)"""

    order_price: Optional[float]
    """주문 가격 (지정가)"""

    order_price_type: Optional[str]
    """주문 가격 유형 (market, limit)"""

    order_note: Optional[str]
    """주문 메모"""

    trade_summary: Optional[dict]
    """주문 생성 요약 데이터"""

    # 실행 플래그
    trade_prepared: bool
    """거래 준비 완료 여부 (prepare_trade 완료)"""

    trade_approved: bool
    """거래 승인 완료 여부 (approval_trade 완료)"""

    trade_executed: bool
    """거래 실행 완료 여부 (execute_trade 완료)"""

    skip_hitl: Optional[bool]
    """HITL 건너뛰기 여부 (automation_level=1일 때 자동 승인)"""

    approval_type: Optional[str]
    """승인 유형 (automatic, manual, modified)"""

    user_notes: Optional[str]
    """사용자 승인 메모"""

    rejection_reason: Optional[str]
    """거부 사유"""

    modified_quantity: Optional[int]
    """사용자가 수정한 수량"""

    # 결과
    trade_order_id: Optional[str]
    """주문 ID"""

    trade_result: Optional[dict]
    """거래 실행 결과"""

    portfolio_snapshot: Optional[dict]
    """거래 이후 최신 포트폴리오 스냅샷"""

    agent_results: Optional[dict]
    """MasterState 공유용 결과 (trading 키로 전달)"""

    # 메타데이터
    error: Optional[str]
    """에러 메시지"""

    is_query_only: Optional[bool]
    """조회 요청 여부 (매매가 아닌 보유 수량 조회인 경우)"""

    risk_level: Optional[str]
    """리스크 레벨 (low, medium, high)"""

    risk_factors: Optional[List[str]]
    """리스크 요인 리스트"""
