"""
LangGraph 기반 마스터 에이전트

StateGraph를 사용한 에이전트 오케스트레이션
"""
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import interrupt
from langchain_core.messages import AIMessage, HumanMessage
import logging

from src.agents.research import research_agent
from src.agents.strategy import strategy_agent
from src.agents.risk import risk_agent
from src.agents.portfolio import portfolio_agent
from src.agents.monitoring import monitoring_agent
from src.agents.education import education_agent
from src.schemas.agent import AgentInput, AgentOutput
from src.schemas.graph_state import GraphState

logger = logging.getLogger(__name__)


# ==================== Intent Categories ====================

class IntentCategory:
    """Intent categories"""
    STOCK_ANALYSIS = "stock_analysis"
    TRADE_EXECUTION = "trade_execution"
    PORTFOLIO_EVALUATION = "portfolio_evaluation"
    REBALANCING = "rebalancing"
    PERFORMANCE_CHECK = "performance_check"
    MARKET_STATUS = "market_status"
    GENERAL_QUESTION = "general_question"


# ==================== Node Functions ====================

def analyze_intent_node(state: GraphState) -> GraphState:
    """
    의도 분석 노드
    사용자 쿼리를 분석하여 의도를 파악

    LangGraph 표준: messages에서 마지막 사용자 메시지 추출
    """
    # messages에서 마지막 메시지 추출
    last_message = state["messages"][-1]
    query = last_message.content if hasattr(last_message, 'content') else str(last_message)
    query_lower = query.lower()

    # 키워드 기반 의도 분석 (우선순위 순서 중요!)
    # 1. 리밸런싱 (가장 구체적)
    if any(word in query_lower for word in ["리밸런싱", "재구성", "재배분", "조정", "비중"]):
        intent = IntentCategory.REBALANCING
    # 2. 매매 실행
    elif any(word in query_lower for word in ["매수", "매도", "사", "팔"]):
        intent = IntentCategory.TRADE_EXECUTION
    # 3. 수익률/현황 조회
    elif any(word in query_lower for word in ["수익률", "현황"]):
        intent = IntentCategory.PERFORMANCE_CHECK
    # 4. 포트폴리오 관련 (리밸런싱 제외)
    elif any(word in query_lower for word in ["포트폴리오", "자산배분"]):
        intent = IntentCategory.PORTFOLIO_EVALUATION
    # 5. 종목 분석
    elif any(word in query_lower for word in ["분석", "어때", "평가", "투자"]):
        intent = IntentCategory.STOCK_ANALYSIS
    # 6. 시장 상황
    elif "시장" in query_lower:
        intent = IntentCategory.MARKET_STATUS
    # 7. 일반 질문
    else:
        intent = IntentCategory.GENERAL_QUESTION

    logger.info(f"🔍 의도 감지: {intent} (쿼리: '{query}')")

    return {
        **state,
        "intent": intent,
    }


def determine_agents_node(state: GraphState) -> GraphState:
    """
    에이전트 결정 노드
    의도에 따라 호출할 에이전트 결정
    """
    intent = state["intent"]

    routing_map = {
        IntentCategory.STOCK_ANALYSIS: ["research_agent", "strategy_agent", "risk_agent"],
        IntentCategory.TRADE_EXECUTION: ["strategy_agent", "risk_agent"],
        IntentCategory.PORTFOLIO_EVALUATION: ["portfolio_agent", "risk_agent"],
        IntentCategory.REBALANCING: ["portfolio_agent", "strategy_agent", "risk_agent"],
        IntentCategory.PERFORMANCE_CHECK: ["portfolio_agent"],
        IntentCategory.MARKET_STATUS: ["research_agent", "monitoring_agent"],
        IntentCategory.GENERAL_QUESTION: ["education_agent"],
    }

    agents = routing_map.get(intent, ["education_agent"])
    logger.info(f"🎯 호출할 에이전트: {agents}")

    return {
        **state,
        "agents_to_call": agents,
    }


async def call_agents_node(state: GraphState) -> GraphState:
    """
    에이전트 호출 노드
    결정된 에이전트들을 병렬로 호출
    """
    agents_to_call = state["agents_to_call"]

    agent_registry = {
        "research_agent": research_agent,
        "strategy_agent": strategy_agent,
        "risk_agent": risk_agent,
        "portfolio_agent": portfolio_agent,
        "monitoring_agent": monitoring_agent,
        "education_agent": education_agent,
    }

    # messages에서 query 추출
    last_message = state["messages"][-1]
    query = last_message.content if hasattr(last_message, 'content') else str(last_message)

    # AgentInput 생성
    agent_input = AgentInput(
        request_id=state["conversation_id"],
        automation_level=state["automation_level"],
        context={
            "query": query,
            "intent": state["intent"],
        }
    )

    # 에이전트 호출
    results = {}
    for agent_id in agents_to_call:
        agent = agent_registry.get(agent_id)
        if agent:
            try:
                output = await agent.execute(agent_input)
                if output.status == "success":
                    results[agent_id] = output.data
            except Exception as e:
                logger.error(f"Agent {agent_id} failed: {str(e)}")

    logger.info(f"✅ 호출 완료된 에이전트: {list(results.keys())}")

    return {
        **state,
        "agent_results": results,
        "agents_called": list(results.keys()),
    }


def check_risk_node(state: GraphState) -> GraphState:
    """
    리스크 체크 노드
    에이전트 결과에서 리스크 수준 추출
    """
    agent_results = state.get("agent_results", {})

    # risk_agent 결과에서 리스크 레벨 추출
    risk_level = None
    if "risk_agent" in agent_results:
        risk_data = agent_results["risk_agent"]
        risk_level = risk_data.get("risk_level")

    logger.info(f"⚠️ 리스크 레벨: {risk_level}")

    return {
        **state,
        "risk_level": risk_level,
    }


def check_hitl_node(state: GraphState) -> GraphState:
    """
    HITL 트리거 체크 노드
    자동화 레벨과 리스크를 고려하여 HITL 필요 여부 판단
    """
    intent = state["intent"]
    automation_level = state["automation_level"]
    risk_level = state.get("risk_level")

    hitl_required = False

    # Trade execution always requires approval in Level 2+
    if intent == IntentCategory.TRADE_EXECUTION and automation_level >= 2:
        hitl_required = True

    # Rebalancing requires approval in Level 2+
    if intent == IntentCategory.REBALANCING and automation_level >= 2:
        hitl_required = True

    # High risk always triggers HITL
    if risk_level in ["high", "critical"]:
        hitl_required = True

    # Level 3 (Advisor) requires approval for most actions
    if automation_level == 3 and intent not in [
        IntentCategory.GENERAL_QUESTION,
        IntentCategory.PERFORMANCE_CHECK
    ]:
        hitl_required = True

    logger.info(f"🤝 HITL 필요: {hitl_required} (레벨={automation_level}, 의도={intent})")

    return {
        **state,
        "hitl_required": hitl_required,
    }


# ==================== Trade Execution Nodes (HITL 패턴) ====================

def prepare_trade_node(state: GraphState) -> GraphState:
    """
    1단계: 거래 준비 (부작용)

    패턴 2: 노드 분리 - interrupt 전 부작용 격리
    """
    # 재실행 방지 플래그 체크
    if state.get("trade_prepared"):
        logger.info("⏭️ [Trade] 이미 준비됨, 스킵")
        return state

    logger.info("📝 [Trade] 거래 준비 중...")

    # TODO: 실제 DB에 주문 생성
    # order_id = db.create_order({
    #     "stock": state["query"],  # 실제로는 파싱 필요
    #     "quantity": 10,
    #     "status": "pending"
    # })

    # Mock 구현
    import uuid
    order_id = f"ORDER_{str(uuid.uuid4())[:8]}"

    logger.info(f"✅ [Trade] 주문 생성: {order_id}")

    return {
        **state,
        "trade_prepared": True,
        "trade_order_id": order_id,
    }


def approval_trade_node(state: GraphState) -> GraphState:
    """
    2단계: HITL 승인 (interrupt 발생)

    패턴 2: 노드 분리 - interrupt만 포함, 부작용 없음
    이 노드는 재실행되어도 안전함
    """
    # 이미 승인되었으면 스킵
    if state.get("trade_approved"):
        logger.info("⏭️ [Trade] 이미 승인됨, 스킵")
        return state

    logger.info("🔔 [Trade] 사용자 승인 요청 중...")

    order_id = state.get("trade_order_id", "UNKNOWN")

    # messages에서 query 추출
    last_message = state["messages"][-1]
    query = last_message.content if hasattr(last_message, 'content') else str(last_message)

    # 🔴 Interrupt 발생 - 사용자 승인 대기
    approval = interrupt({
        "type": "trade_approval",
        "order_id": order_id,
        "query": query,
        "automation_level": state["automation_level"],
        "message": f"매매 주문 '{order_id}'을(를) 승인하시겠습니까?"
    })

    logger.info(f"✅ [Trade] 승인 완료: {approval}")

    # TODO: DB 업데이트
    # db.update(order_id, {"approved": True, "approved_by": approval.get("user_id")})

    return {
        **state,
        "trade_approved": True,
    }


def execute_trade_node(state: GraphState) -> GraphState:
    """
    3단계: 거래 실행 (부작용)

    패턴 3: 멱등성 보장 - 중복 실행 방지
    """
    # 이미 실행되었으면 스킵
    if state.get("trade_executed"):
        logger.info("⏭️ [Trade] 이미 실행됨, 스킵")
        return state

    order_id = state.get("trade_order_id")

    # 승인 확인
    if not state.get("trade_approved"):
        logger.warning("⚠️ [Trade] 승인되지 않음, 실행 불가")
        return state

    logger.info(f"💰 [Trade] 거래 실행 중... (주문: {order_id})")

    # TODO: 멱등성 체크
    # existing = db.get_order(order_id)
    # if existing and existing["status"] == "executed":
    #     return {...state, "trade_result": existing["result"]}

    # TODO: 실제 API 호출 (한국투자증권)
    # with db.transaction():
    #     result = kis_api.execute_trade(...)
    #     db.update(order_id, {"status": "executed", "result": result})

    # Mock 실행
    result = {
        "order_id": order_id,
        "status": "executed",
        "executed_at": "2025-10-04 10:30:00",
        "price": 70000,
        "quantity": 10,
        "total": 700000
    }

    logger.info(f"✅ [Trade] 거래 실행 완료: {result}")

    return {
        **state,
        "trade_executed": True,
        "trade_result": result,
    }


# ==================== Aggregation ====================

def aggregate_results_node(state: GraphState) -> GraphState:
    """
    결과 통합 노드
    모든 에이전트 결과를 통합하여 최종 응답 생성

    LangGraph 표준: AIMessage를 messages에 추가
    """
    agent_results = state.get("agent_results", {})

    # 요약 생성
    summary_parts = []

    if "research_agent" in agent_results:
        research = agent_results["research_agent"]
        stock_name = research.get("stock_name", "종목")
        rating = research.get("rating", "N/A")
        summary_parts.append(f"{stock_name} 분석 완료 (평가: {rating}/5)")

    if "strategy_agent" in agent_results:
        strategy = agent_results["strategy_agent"]
        action = strategy.get("action", "N/A")
        confidence = strategy.get("confidence", 0)
        summary_parts.append(f"매매 의견: {action} (신뢰도: {confidence})")

    if "risk_agent" in agent_results:
        risk = agent_results["risk_agent"]
        risk_level = risk.get("risk_level", "N/A")
        summary_parts.append(f"리스크 수준: {risk_level}")

    # 매매 실행 결과 포함
    if state.get("trade_executed") and state.get("trade_result"):
        trade = state["trade_result"]
        summary_parts.append(f"매매 실행 완료 (주문: {trade.get('order_id')})")

    summary = " | ".join(summary_parts) if summary_parts else "분석 완료"

    # 최종 응답 구성
    final_response = {
        "summary": summary,
        "details": agent_results,
        "intent": state["intent"],
        "agents_called": state.get("agents_called", []),
        "hitl_required": state.get("hitl_required", False),
        "risk_level": state.get("risk_level"),
        "trade_result": state.get("trade_result"),  # 매매 결과 추가
    }

    # ⭐ LangGraph 표준: AIMessage 추가
    ai_message = AIMessage(content=summary)

    return {
        **state,
        "messages": [ai_message],  # add_messages reducer가 자동 병합
        "summary": summary,
        "final_response": final_response,
    }


# ==================== Router Functions ====================

def route_after_determine_agents(state: GraphState) -> str:
    """
    의도에 따라 다음 노드 결정

    TRADE_EXECUTION → 매매 실행 플로우
    기타 → 일반 에이전트 호출
    """
    intent = state.get("intent")

    if intent == IntentCategory.TRADE_EXECUTION:
        logger.info("🔀 [Router] 매매 실행 플로우로 분기")
        return "prepare_trade"
    else:
        logger.info("🔀 [Router] 일반 에이전트 호출 플로우")
        return "call_agents"


def should_continue(state: GraphState) -> str:
    """
    다음 노드 결정
    """
    # 모든 처리가 완료되면 END
    return END


# ==================== Build Graph ====================

def build_graph(automation_level: int = 2):
    """
    LangGraph StateGraph 구성

    Args:
        automation_level: 자동화 레벨 (1-3)
            - Level 1 (Pilot): 거의 자동
            - Level 2 (Copilot): 매매/리밸런싱 승인 필요 (기본값)
            - Level 3 (Advisor): 모든 결정 승인 필요
    """
    # 그래프 생성 - LangGraph 표준 GraphState 사용
    workflow = StateGraph(GraphState)

    # 기본 노드
    workflow.add_node("analyze_intent", analyze_intent_node)
    workflow.add_node("determine_agents", determine_agents_node)
    workflow.add_node("call_agents", call_agents_node)
    workflow.add_node("check_risk", check_risk_node)
    workflow.add_node("check_hitl", check_hitl_node)
    workflow.add_node("aggregate_results", aggregate_results_node)

    # 매매 실행 노드 (3단계 분리)
    workflow.add_node("prepare_trade", prepare_trade_node)
    workflow.add_node("approval_trade", approval_trade_node)
    workflow.add_node("execute_trade", execute_trade_node)

    # 기본 플로우
    workflow.set_entry_point("analyze_intent")
    workflow.add_edge("analyze_intent", "determine_agents")

    # 조건부 분기: TRADE_EXECUTION이면 매매 플로우, 아니면 일반 플로우
    workflow.add_conditional_edges(
        "determine_agents",
        route_after_determine_agents,
        {
            "prepare_trade": "prepare_trade",  # 매매 실행 플로우
            "call_agents": "call_agents",      # 일반 플로우
        }
    )

    # 일반 플로우
    workflow.add_edge("call_agents", "check_risk")
    workflow.add_edge("check_risk", "check_hitl")
    workflow.add_edge("check_hitl", "aggregate_results")

    # 매매 실행 플로우
    workflow.add_edge("prepare_trade", "approval_trade")
    workflow.add_edge("approval_trade", "execute_trade")
    workflow.add_edge("execute_trade", "aggregate_results")

    # 종료
    workflow.add_edge("aggregate_results", END)

    # Checkpointer 설정
    # TODO: Production에서는 AsyncSqliteSaver 사용
    # checkpointer = AsyncSqliteSaver.from_conn_string("data/checkpoints.db")
    checkpointer = MemorySaver()  # 테스트용

    # 자동화 레벨별 interrupt 설정
    interrupt_nodes = []

    if automation_level >= 2:  # Copilot (기본값)
        interrupt_nodes.append("approval_trade")  # 매매 승인 필요

    # TODO: Level 3 (Advisor)는 추가 interrupt 필요
    # if automation_level == 3:
    #     interrupt_nodes.extend(["create_strategy", "build_portfolio"])

    logger.info(f"🔧 [Graph] Checkpointer 설정 완료")
    logger.info(f"🔧 [Graph] Interrupt 노드: {interrupt_nodes}")

    # 그래프 컴파일
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_nodes if interrupt_nodes else None
    )

    return app


# Global compiled graph (Level 2 기본값)
graph_app = build_graph(automation_level=2)


# ==================== Main Interface ====================

async def run_graph(
    query: str,
    automation_level: int = 2,
    request_id: str = None,
    thread_id: str = None
) -> Dict[str, Any]:
    """
    그래프 실행 함수

    Args:
        query: 사용자 질의
        automation_level: 자동화 레벨 (1-3)
        request_id: 요청 ID
        thread_id: 대화 스레드 ID (HITL 재개 시 필요)

    Returns:
        최종 응답 딕셔너리
    """
    import uuid

    if not request_id:
        request_id = str(uuid.uuid4())

    if not thread_id:
        thread_id = request_id  # 기본값: request_id를 thread_id로 사용

    # 자동화 레벨에 맞는 그래프 빌드
    app = build_graph(automation_level=automation_level)

    # Checkpointer 설정
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    # 초기 상태 - LangGraph 표준: messages 사용
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "user_id": "user_001",  # TODO: 실제 인증 시스템 연동
        "conversation_id": thread_id,
        "automation_level": automation_level,
        "intent": None,
        "agent_results": {},
        "agents_to_call": [],
        "agents_called": [],
        "risk_level": None,
        "hitl_required": False,
        # 매매 실행 플래그
        "trade_prepared": False,
        "trade_approved": False,
        "trade_executed": False,
        "trade_order_id": None,
        "trade_result": None,
        # 결과
        "summary": None,
        "final_response": None,
    }

    # 그래프 실행
    result = await app.ainvoke(initial_state, config=config)

    return result.get("final_response", {})