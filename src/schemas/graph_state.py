"""
Langgraph GraphState 정의

Langgraph 표준 패턴을 준수하는 State 정의
- messages 필드 (add_messages reducer)
- 대화 히스토리 자동 관리
- LangChain 도구 통합 가능
"""
from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional
from langgraph.graph.message import add_messages
from langgraph.managed import RemainingSteps
from langchain_core.messages import BaseMessage
import operator

from src.schemas.hitl_config import HITLConfig


class GraphState(TypedDict):
    """
    Master Graph State - Langgraph 표준 준수

    주요 특징:
    - messages: Langgraph 표준 필드 (대화 히스토리)
    - add_messages: 자동 메시지 병합 reducer
    - 기존 AgentState 필드 모두 포함 (하위 호환성)
    """

    # ==================== Langgraph 표준 필드 ====================

    messages: Annotated[Sequence[BaseMessage], add_messages]
    """대화 메시지 리스트 (HumanMessage, AIMessage 등)"""

    remaining_steps: RemainingSteps
    """ReAct 에이전트의 남은 실행 스텝 수 (Supervisor 패턴 필수)"""

    # ==================== 사용자 컨텍스트 ====================

    user_id: str
    """사용자 ID"""

    conversation_id: str
    """대화 스레드 ID (checkpointer thread_id와 동일)"""

    hitl_config: HITLConfig | Dict[str, Any]
    """자동화 레벨 프리셋 및 단계별 HITL 설정"""

    intervention_required: bool
    """
    분석/전략 단계부터 HITL 필요 여부
    - False: 매매만 HITL 필요 (기본값)
    - True: 분석/전략/포트폴리오도 HITL 필요
    """

    user_profile: Optional[Dict[str, Any]]
    """사용자 프로파일 (preferred_depth, expertise_level, technical_level, trading_style 등)"""

    # ==================== 의도 및 라우팅 ====================

    intent: Optional[str]
    """사용자 의도 (stock_analysis, trade_execution 등)"""

    stock_code: Optional[str]
    """종목 코드 (LLM이 추출)"""

    stock_name: Optional[str]
    """종목 이름 (LLM이 추출)"""

    intent_confidence: Optional[float]
    """Intent 분석 신뢰도 (0.0-1.0)"""

    query: Optional[str]
    """원본 사용자 질문 (서브그래프 fallback용)"""

    agents_to_call: List[str]
    """호출할 에이전트 목록"""

    agents_called: Annotated[List[str], operator.add]
    """호출 완료된 에이전트 목록 (누적)"""

    supervisor_reasoning: Optional[str]
    """Supervisor의 에이전트 선택 이유"""

    routing_decision: Optional[Dict[str, Any]]
    """Router 프롬프트 출력 전체 (디버깅/감사 로그용)"""

    depth_level: Optional[str]
    """분석 깊이 (brief/detailed/comprehensive)"""

    personalization: Optional[Dict[str, Any]]
    """개인화 설정 (사용자 전문성, 지표 강조 등)"""

    worker_action: Optional[str]
    """직접 호출할 워커 이름 (stock_price/index_price 등)"""

    worker_params: Optional[Dict[str, Any]]
    """워커 파라미터"""

    direct_answer: Optional[str]
    """Router가 직접 생성한 답변"""

    clarification_needed: Optional[bool]
    """추가 정보가 필요한 경우 True"""

    clarification_message: Optional[str]
    """질의 명확화를 위한 안내 문구"""

    # ==================== 에이전트 결과 ====================

    agent_results: Annotated[Dict[str, Any], operator.or_]
    """에이전트별 실행 결과 (병합)"""

    # ==================== 리스크 및 HITL ====================

    risk_level: Optional[str]
    """리스크 수준 (low, medium, high, critical)"""

    hitl_required: bool
    """HITL 승인 필요 여부"""

    # ==================== 매매 실행 상태 플래그 ====================

    trade_prepared: bool
    """거래 준비 완료 여부"""

    trade_approved: bool
    """거래 승인 완료 여부"""

    trade_executed: bool
    """거래 실행 완료 여부"""

    trade_approval_id: Optional[str]
    """거래 승인 요청 ID"""

    trade_action: Optional[str]
    """매매 방향: "buy" | "sell" """

    trade_quantity: Optional[int]
    """매매 수량"""

    trade_price: Optional[int]
    """매매 가격 (지정가 주문 시)"""

    trade_order_type: Optional[str]
    """주문 유형: "market" | "limit" """

    trade_total_amount: Optional[int]
    """총 금액 (quantity * price)"""

    trade_order_id: Optional[str]
    """주문 ID"""

    trade_result: Optional[Dict[str, Any]]
    """거래 실행 결과"""

    user_modifications: Optional[Dict[str, Any]]
    """사용자 수정사항 (HITL modify 시 사용)"""

    # ==================== 최종 결과 (하위 호환성) ====================

    summary: Optional[str]
    """요약 텍스트 (기존 호환용)"""

    final_response: Optional[Dict[str, Any]]
    """최종 응답 데이터 (기존 호환용)"""

    conversation_history: Optional[List[Dict[str, Any]]]
    """최근 대화 히스토리 (Router 컨텍스트용)"""
