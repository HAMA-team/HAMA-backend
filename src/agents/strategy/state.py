"""
Strategy Agent State 정의

Langgraph 서브그래프를 위한 State
ReAct 패턴 기반 동적 Specialist 선택
"""
from typing import TypedDict, Optional, List, Annotated, Literal

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class StrategyState(TypedDict):
    """
    Strategy Agent 서브그래프 State (ReAct 패턴)

    ReAct Flow:
    1. query_intent_classifier: 쿼리 의도 분석 및 분석 깊이 결정
    2. planner: 필요한 Specialist 선택 및 실행 계획 수립
    3. task_router: 다음 Specialist 선택
    4. specialists: 동적으로 선택된 Specialist 실행
       - market_specialist: 시장 사이클 분석
       - sector_specialist: 섹터 로테이션 전략
       - asset_specialist: 자산 배분 결정
       - buy_specialist: 매수 점수 산정 (1-10점)
       - sell_specialist: 매도 판단 (익절/손절/홀드)
       - risk_reward_specialist: 손절가/목표가 계산
    5. synthesis: 최종 투자 전략 Dashboard 생성
    """

    # Supervisor 패턴 호환성
    messages: Annotated[List[BaseMessage], add_messages]
    """메시지 스택 (Supervisor 패턴 필수)"""

    # 입력
    request_id: str
    """요청 ID"""

    query: str
    """사용자 쿼리"""

    user_preferences: Optional[dict]
    """사용자 선호도"""

    user_profile: Optional[dict]
    """사용자 프로필 (투자 경험, 선호 깊이 등)"""

    risk_tolerance: str
    """리스크 허용도 (conservative, moderate, aggressive)"""

    # ReAct 제어 필드
    analysis_depth: Literal["quick", "standard", "comprehensive"]
    """분석 깊이 (quick: 1-2개, standard: 2-4개, comprehensive: 4-6개 Specialist)"""

    focus_areas: List[str]
    """집중 영역 리스트 (예: ["buy_decision", "risk_reward"])"""

    depth_reason: Optional[str]
    """분석 깊이 결정 근거"""

    # Task Loop (Deep Agent 패턴)
    pending_tasks: List[dict]
    """실행 대기 중인 작업 큐"""

    completed_tasks: List[dict]
    """완료된 작업 리스트"""

    current_task: Optional[dict]
    """현재 실행 중인 작업"""

    task_notes: List[str]
    """작업 진행 노트"""

    # Specialist별 분석 결과
    market_outlook: Optional[dict]
    """시장 전망 (market_specialist 결과)"""

    sector_strategy: Optional[dict]
    """섹터 전략 (sector_specialist 결과)"""

    asset_allocation: Optional[dict]
    """자산 배분 (asset_specialist 결과)"""

    buy_score: Optional[int]
    """매수 점수 1-10 (buy_specialist 결과)"""

    buy_analysis: Optional[dict]
    """매수 분석 전체 결과 (buy_specialist 상세 정보)"""

    sell_decision: Optional[dict]
    """매도 판단 (sell_specialist 결과)"""

    risk_reward: Optional[dict]
    """손절가/목표가 (risk_reward_specialist 결과)"""

    blueprint: Optional[dict]
    """최종 Strategic Blueprint (synthesis 결과)"""

    # 메타데이터
    error: Optional[str]
    """에러 메시지"""
