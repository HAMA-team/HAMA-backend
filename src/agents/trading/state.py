"""
Trading Agent State 정의

매매 실행을 위한 State (ReAct 패턴)
"""
from typing import TypedDict, Optional, List, Annotated, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.schemas.hitl_config import HITLConfig


class TradingState(TypedDict):
    """
    Trading Agent 서브그래프 State (ReAct 패턴)

    Flow:
    1. Intent Classifier: 매매 의도 분석 및 정보 추출
    2. Planner: Specialist 선택
    3. Task Router: 작업 선택
    4. Specialists: 매매 분석 (buy/sell/risk_reward)
    5. Approval: HITL 승인
    6. Execute: 거래 실행
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

    # Research 결과 (Buy/Sell Specialist가 참조)
    research_result: Optional[dict]
    """Research Agent의 consensus 결과"""

    # ReAct 제어 필드
    analysis_depth: Optional[Literal["quick", "standard", "comprehensive"]]
    """분석 깊이"""

    focus_areas: Optional[List[str]]
    """집중 영역 리스트"""

    depth_reason: Optional[str]
    """분석 깊이 결정 근거"""

    pending_tasks: Optional[List[dict]]
    """실행 대기 중인 작업 큐"""

    completed_tasks: Optional[List[dict]]
    """완료된 작업 리스트"""

    current_task: Optional[dict]
    """현재 실행 중인 작업"""

    task_notes: Optional[List[str]]
    """작업 진행 노트"""

    # 매매 정보 (LLM이 추출해야 할 정보)
    stock_code: Optional[str]
    """종목 코드"""

    quantity: Optional[int]
    """수량"""

    order_type: Optional[str]
    """주문 유형 (buy, sell)"""

    order_price: Optional[float]
    """주문 가격 (지정가)"""

    trade_summary: Optional[dict]
    """주문 생성 요약 데이터"""

    buy_score: Optional[int]
    """매수 점수 (1-10점, 8점 이상 강력 매수)"""

    buy_rationale: Optional[str]
    """매수 근거 및 전략"""

    sell_rationale: Optional[str]
    """매도 근거 및 전략"""

    target_price: Optional[float]
    """목표가 (원)"""

    stop_loss: Optional[float]
    """손절가 (원)"""

    risk_reward_ratio: Optional[float]
    """Risk/Reward 비율 (예: 2.0이면 1 리스크당 2 리워드)"""

    investment_period: Optional[str]
    """투자 기간 (단기/중기/장기)"""

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

    portfolio_snapshot: Optional[dict]
    """거래 이후 최신 포트폴리오 스냅샷"""

    # 메타데이터
    error: Optional[str]
    """에러 메시지"""
