"""Portfolio Agent State 정의."""
from __future__ import annotations

from typing import TypedDict, Optional, List, Literal, Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.schemas.hitl_config import HITLConfig
from src.schemas.portfolio import PortfolioHolding


class RebalanceInstruction(TypedDict, total=False):
    """리밸런싱 실행 지시"""

    action: Literal["BUY", "SELL"]
    stock_code: str
    stock_name: str
    amount: float
    weight_delta: float


class PortfolioState(TypedDict, total=False):
    """Portfolio Agent 서브그래프 State (ReAct 패턴)"""

    messages: Annotated[List[BaseMessage], add_messages]

    # 입력
    request_id: str
    user_id: Optional[str]
    hitl_config: HITLConfig
    query: Optional[str]
    """사용자 질문 (특정 종목 조회용)"""
    stock_code: Optional[str]
    """조회할 특정 종목 코드 (analyze_query_node에서 추출)"""
    stock_code_filter: Optional[str]
    """필터링된 종목 코드 (collect_portfolio_node에서 사용)"""
    risk_profile: Optional[str]
    horizon: Optional[str]
    preferences: Optional[dict]
    view_only: Optional[bool]
    """조회 전용 모드 (True시 리밸런싱 스킵)"""

    portfolio_profile: Optional[dict]
    """사용자 프로필 / 투자 성향 캡처"""

    automation_level: Optional[int]
    """자동화 레벨 (1: Pilot, 2: Copilot, 3: Advisor)"""

    strategy_result: Optional[dict]
    """Strategy Agent 결과 (리밸런싱 시 참고)"""

    agent_results: Optional[dict]
    """다른 에이전트 결과 (MasterState 공유용)"""

    execution_results: Optional[List[dict]]
    """리밸런싱 실행 결과"""

    # ReAct 제어 필드
    intent_type: Optional[Literal["view", "analyze", "optimize", "rebalance"]]
    """작업 의도 유형"""

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

    # 현재 포트폴리오 스냅샷
    portfolio_id: Optional[str]
    total_value: Optional[float]
    current_holdings: Optional[List[PortfolioHolding]]

    # 추천 산출값
    proposed_allocation: Optional[List[PortfolioHolding]]
    expected_return: Optional[float]
    expected_volatility: Optional[float]
    sharpe_ratio: Optional[float]
    rationale: Optional[str]

    # 리밸런싱 정보
    rebalancing_needed: Optional[bool]
    trades_required: Optional[List[RebalanceInstruction]]
    hitl_required: bool

    # HITL 진행 상태 (Trading Agent와 동일한 패턴)
    rebalance_prepared: bool
    """리밸런싱 준비 완료 여부"""

    rebalance_approved: bool
    """리밸런싱 승인 여부"""

    rebalance_executed: bool
    """리밸런싱 실행 완료 여부"""

    rebalance_order_id: Optional[str]
    """리밸런싱 주문 ID"""

    # 포트폴리오 제약 조건
    max_slots: Optional[int]
    """최대 보유 종목 수 (기본 10개)"""

    max_sector_concentration: Optional[float]
    """섹터 집중도 제한 (기본 30%)"""

    max_same_industry_count: Optional[int]
    """동일 산업군 최대 종목 수 (기본 3개)"""

    market_condition: Optional[str]
    """시장 상황 (강세장/중립장/약세장)"""

    constraint_violations: Optional[List[dict]]
    """제약 조건 위반 내역"""

    # 최종 리포트
    summary: Optional[str]
    portfolio_report: Optional[dict]

    portfolio_snapshot: Optional[dict]
    """서비스에서 내려온 전체 스냅샷 (시장/프로필 포함)"""

    user_rebalance_guidance: Optional[str]
    """사용자의 리밸런싱 방향성 제시 (예: 'IT 섹터 늘려줘', '엔비디아 유망해보여')"""

    # 에러 처리
    error: Optional[str]
