"""
Langgraph GraphState 정의

Langgraph 표준 패턴을 준수하는 State 정의
- messages 필드 (add_messages reducer)
- 대화 히스토리 자동 관리
- LangChain 도구 통합 가능
"""
from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Optional, NotRequired
from langgraph.graph.message import add_messages
from langgraph.managed import RemainingSteps
from langchain_core.messages import BaseMessage
import operator


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

    remaining_steps: NotRequired[RemainingSteps]
    """ReAct 에이전트의 남은 실행 스텝 수 (Supervisor 패턴 필수)"""

    # ==================== 사용자 컨텍스트 ====================

    user_id: str
    """사용자 ID"""

    conversation_id: str
    """대화 스레드 ID (checkpointer thread_id와 동일)"""

    automation_level: int
    """자동화 레벨 (1=Pilot, 2=Copilot, 3=Advisor)"""

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

    trade_order_id: Optional[str]
    """주문 ID"""

    trade_result: Optional[Dict[str, Any]]
    """거래 실행 결과"""

    # ==================== 최종 결과 (하위 호환성) ====================

    summary: Optional[str]
    """요약 텍스트 (기존 호환용)"""

    final_response: Optional[Dict[str, Any]]
    """최종 응답 데이터 (기존 호환용)"""
