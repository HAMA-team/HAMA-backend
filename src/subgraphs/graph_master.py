"""
Supervisor 패턴 기반 멀티 에이전트 시스템

Supervisor의 역할:
1. 간단한 조회는 직접 처리 (사용가능한 Tool을 통해)
2. 투자 용어 설명은 자연스럽게 답변 (tool 없이)
3. 복잡한 심층 분석만 전문가(SubGraph)에게 위임
4. 매매 전 리스크 분석 및 HITL 승인 관리
"""
import logging
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langgraph_sdk.schema import Interrupt

from langgraph_supervisor import create_supervisor

from src.subgraphs.research_subgraph import research_agent
from src.subgraphs.quantitative_subgraph import quantitative_agent
from src.subgraphs.tools import get_all_tools
from src.config.settings import settings
from src.schemas.graph_state import GraphState
from src.services import trading_service

logger = logging.getLogger(__name__)


# ==================== Trading Nodes ====================

async def portfolio_simulator_node(state: GraphState) -> GraphState:
    """
    포트폴리오 시뮬레이션 노드 - 매매 전/후 변화 계산

    매매 제안을 받아 포트폴리오 전/후 상태 및 리스크를 계산합니다.
    """
    from src.services.portfolio_service import portfolio_service

    stock_code = state.get("stock_code", "")
    action = state.get("trade_action", "buy")
    quantity = state.get("trade_quantity", 0)
    price = state.get("trade_price", 0)
    user_id = state.get("user_id")

    logger.info("📊 [Portfolio/Simulator] 매매 시뮬레이션: %s %s %d주 @ %d원",
                action, stock_code, quantity, price)

    try:
        simulation_result = await portfolio_service.simulate_trade(
            user_id=user_id,
            stock_code=stock_code,
            action=action,
            quantity=quantity,
            price=price,
        )

        portfolio_before = simulation_result["portfolio_before"]
        portfolio_after = simulation_result["portfolio_after"]
        risk_before = simulation_result["risk_before"]
        risk_after = simulation_result["risk_after"]

        # 변화량 계산 (로깅용)
        weight_before = next(
            (h["weight"] for h in portfolio_before.get("holdings", []) if h["stock_code"] == stock_code),
            0.0
        )
        weight_after = next(
            (h["weight"] for h in portfolio_after.get("holdings", []) if h["stock_code"] == stock_code),
            0.0
        )

        logger.info("✅ [Portfolio/Simulator] 시뮬레이션 완료")
        logger.info(f"  - 종목 비중: {weight_before*100:.1f}% → {weight_after*100:.1f}%")
        logger.info(f"  - 변동성: {risk_before.get('portfolio_volatility')} → {risk_after.get('portfolio_volatility')}")

        return {
            "portfolio_before": portfolio_before,
            "portfolio_after": portfolio_after,
            "risk_before": risk_before,
            "risk_after": risk_after,
            "messages": [AIMessage(content="매매 시뮬레이션이 완료되었습니다.")],
        }

    except Exception as exc:
        logger.error("❌ [Portfolio/Simulator] 시뮬레이션 실패: %s", exc)
        return {
            "messages": [AIMessage(content=f"시뮬레이션 실패: {exc}")],
        }


async def trade_planner_node(state: GraphState) -> GraphState:
    """
    매매 계획 노드 - 매매 제안 구조화

    request_trade tool의 결과를 trade_proposal로 구조화합니다.
    (실제 제안 생성은 Supervisor의 request_trade tool에서 이미 완료)
    """
    action = state.get("trade_action", "buy")
    stock_code = state.get("stock_code", "")
    stock_name = state.get("stock_name", stock_code)
    quantity = state.get("trade_quantity", 0)
    price = state.get("trade_price", 0)
    order_type = state.get("trade_order_type", "limit")

    logger.info("📝 [Trading/Planner] 매매 제안 생성: %s %s %d주 @ %d원",
                action, stock_code, quantity, price)

    # trade_proposal 구조화
    trade_proposal = {
        "orders": [
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "action": action,
                "quantity": quantity,
                "price": price,
                "order_type": order_type,
                "total_amount": quantity * price,
            }
        ],
        "rationale": f"{stock_name} {action} 제안",
        "created_at": datetime.now().isoformat(),
    }

    return {
        "trade_proposal": trade_proposal,
        "messages": [AIMessage(content=f"{stock_name} {action} 제안이 생성되었습니다.")],
    }


async def trade_hitl_node(state: GraphState) -> GraphState:
    """
    매매 HITL 노드 - 사용자 승인 요청

    경로 1: 첫 실행 → 전/후 비교 데이터와 함께 Interrupt 발생
    경로 2: 승인 후 재개 → 사용자 수정사항 반영 후 재시뮬레이션 또는 실행
    """
    # ========== 경로 2: 승인 후 재개 ==========
    if state.get("trade_approved"):
        logger.info("✅ [Trading/HITL] 사용자 승인 완료")

        # 사용자 수정사항 처리
        modifications = state.get("user_modifications")

        if modifications:
            logger.info("✏️ [Trading/HITL] 사용자 수정사항 반영: %s", modifications)

            # 수정 가능한 필드: quantity, price, action
            quantity = modifications.get("quantity", state.get("trade_quantity"))
            price = modifications.get("price", state.get("trade_price"))
            action = modifications.get("action", state.get("trade_action"))

            # 총 금액 재계산
            total_amount = quantity * price

            logger.info(
                f"🔄 [Trading/HITL] 수정된 주문: {action} {quantity}주 @ {price:,}원 = {total_amount:,}원"
            )
            logger.info("🔄 [Trading/HITL] 재시뮬레이션을 위해 portfolio_simulator로 이동")

            # 재시뮬레이션을 위해 trade_approved를 False로 설정
            # 조건부 edge가 portfolio_simulator로 라우팅
            return {
                "trade_quantity": quantity,
                "trade_price": price,
                "trade_action": action,
                "trade_total_amount": total_amount,
                "trade_approved": False,  # 재시뮬레이션 필요
                "user_modifications": None,  # 초기화
                "messages": [AIMessage(content=f"수정된 주문으로 재시뮬레이션을 시작합니다: {action} {quantity}주")],
            }
        else:
            # 수정 없음 - 기존 정보로 진행
            return {
                "trade_prepared": True,
                "messages": [AIMessage(content="매매 주문을 준비했습니다.")],
            }

    # ========== 경로 1: 첫 실행 (Interrupt 발생) ==========

    action = state.get("trade_action", "buy")
    stock_code = state.get("stock_code", "")
    stock_name = state.get("stock_name", stock_code)
    quantity = state.get("trade_quantity", 0)
    price = state.get("trade_price", 0)
    total_amount = quantity * price

    # 포트폴리오 전/후 데이터 가져오기
    portfolio_before = state.get("portfolio_before", {})
    portfolio_after = state.get("portfolio_after", {})
    risk_before = state.get("risk_before", {})
    risk_after = state.get("risk_after", {})

    logger.info("🛒 [Trading/HITL] 매매 승인 요청: %s %s %d주 @ %d원",
               action, stock_code, quantity, price)

    # Interrupt 발생 (사용자 승인 대기)
    approval_id = str(uuid.uuid4())

    logger.info("⚠️ [Trading/HITL] INTERRUPT 발생 - 전/후 비교 데이터 포함")

    # State 업데이트 (재개 시 사용)
    state_update: GraphState = {
        "trade_approval_id": approval_id,
        "trade_total_amount": total_amount,
        "messages": [AIMessage(content="매매 승인을 기다립니다...")],
    }

    # Interrupt payload 생성 (전/후 비교 포함)
    interrupt_payload = {
        "type": "trade_approval",
        "approval_id": approval_id,
        "action": action,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "quantity": quantity,
        "price": price,
        "total_amount": total_amount,
        "order_type": state.get("trade_order_type", "limit"),
        "modifiable_fields": ["quantity", "price", "action"],
        "message": f"{stock_name} {quantity}주를 {price:,}원에 {action}하시겠습니까?",
        # 전/후 비교 데이터 추가
        "portfolio_before": portfolio_before,
        "portfolio_after": portfolio_after,
        "risk_before": risk_before,
        "risk_after": risk_after,
    }

    raise Interrupt(state_update, value=interrupt_payload)


async def execute_trade_node(state: GraphState) -> GraphState:
    """
    매매 실행 노드

    trading_service를 통해 실제 주문 실행 (현재는 시뮬레이션)
    """
    action = state.get("trade_action", "buy")
    stock_code = state.get("stock_code", "")
    quantity = state.get("trade_quantity", 0)
    price = state.get("trade_price", 0)

    logger.info("💰 [Trading/Execute] 매매 실행: %s %s %d주 @ %d원",
               action, stock_code, quantity, price)

    try:
        # Trading Service를 통해 주문 실행
        user_id = state.get("user_id", str(uuid.UUID(int=0)))
        order_result = await trading_service.execute_order(
            user_id=user_id,
            stock_code=stock_code,
            quantity=quantity,
            action=action,
            price=price,
        )

        logger.info("✅ [Trading/Execute] 매매 완료: %s", order_result.get("order_id"))

        return {
            "trade_order_id": order_result.get("order_id"),
            "trade_result": order_result,
            "trade_executed": True,
            "messages": [AIMessage(content=f"매매 실행 완료: 주문번호 {order_result.get('order_id')}")],
        }

    except Exception as exc:
        logger.error("❌ [Trading/Execute] 매매 실패: %s", exc)
        return {
            "messages": [AIMessage(content=f"매매 실행 실패: {exc}")],
        }


# ==================== Supervisor Prompt ====================

def build_supervisor_prompt() -> str:
    """
    Supervisor 시스템 프롬프트 생성 (간결하게 유지)

    Returns:
        str: Supervisor 시스템 프롬프트
    """
    return f"""<context>
## 역할
당신은 사용자 계정을 관리하는 수석 투자 매니저입니다.

## 원칙
1. **간단한 조회** → 직접 tools 사용 (get_current_price, get_account_balance 등)
2. **투자 용어 설명** → tool 없이 자연스럽게 답변
3. **심층 분석** → 전문가에게 위임 (transfer_to_research_agent)
4. **매매 실행** → 반드시 리스크 분석 후 승인 대기

## 매매 HITL 플로우 (필수)
⚠️ 모든 매매는 사용자 승인 필요

**중요: request_trade tool 사용 (HITL 패턴)**
매매 요청 시 execute_trade가 아닌 **request_trade**를 사용하세요:

1. resolve_ticker로 종목 코드 확인
2. get_portfolio_positions() 호출
3. calculate_portfolio_risk() 호출
4. 리스크 변화를 사용자에게 명시적 보고:
   - 현재 리스크: 집중도, 변동성, VaR
   - 매매 후 예상 리스크
   - 경고 사항
5. **request_trade(ticker, action, quantity, price)** 호출
   → 자동으로 사용자 승인 프로세스가 시작됩니다
   → 승인 후 자동 실행됩니다

⚠️ execute_trade는 deprecated - request_trade를 사용하세요
</context>

<instructions>
1. 사용자 질의 분석
2. 종목명이 있으면 resolve_ticker로 코드 변환
3. 적절한 tool 선택 (각 tool의 description 참고)
4. **전문가 에이전트 결과 처리**:
   - Research Agent나 Quantitative Agent가 분석을 완료하면, 그 결과가 메시지로 전달됩니다
   - 전문가의 분석 결과를 **그대로 사용자에게 전달**하세요
   - 추가 설명이나 요약 없이, 전문가가 작성한 보고서를 최종 응답으로 사용하세요
5. 작업 완료 후 결과 기반 다음 action 자동 결정
</instructions>

<examples>
## 예시 1: 단순 조회
사용자: "삼성전자 현재가?"
→ resolve_ticker("삼성전자") → get_current_price("005930")

## 예시 2: 투자 용어 설명 (tool 없이)
사용자: "PER이 뭐야?"
→ [tool 호출 없이 직접 답변] "PER(주가수익비율)은..."

## 예시 3: 정성적 분석 위임
사용자: "삼성전자 최근 뉴스 분석해줘"
→ resolve_ticker("삼성전자")
→ transfer_to_research_agent(query="삼성전자 뉴스 분석", ticker="005930")
→ [Research Agent 분석 완료, 결과를 메시지로 수신]
→ **해당 분석 결과를 그대로 사용자에게 전달** (추가 가공 없이)

## 예시 4: 정량적 분석 위임
사용자: "삼성전자 재무제표 분석해줘"
→ resolve_ticker("삼성전자")
→ transfer_to_quantitative_agent(query="삼성전자 재무제표 분석", ticker="005930")
→ [Quantitative Agent 분석 완료, 결과를 메시지로 수신]
→ **해당 분석 결과를 그대로 사용자에게 전달** (추가 가공 없이)

## 예시 5: 매매 실행 (HITL)
사용자: "삼성전자 10주 매수해줘"
→ resolve_ticker("삼성전자")
→ get_portfolio_positions()
→ calculate_portfolio_risk(portfolio, {{"ticker": "005930", "action": "buy", "quantity": 10}})
→ [사용자에게 리스크 보고]
   "현재 포트폴리오 집중도는 30%이며, 이 매매 후 45%로 증가합니다.
    변동성은 15%에서 18%로 증가합니다.
    진행하시겠습니까?"
→ 사용자: "승인"
→ execute_trade(ticker="005930", action="buy", quantity=10)
</examples>
"""


# ==================== Supervisor 생성 ====================

def build_supervisor(intervention_required: bool = False, llm: Optional[BaseChatModel] = None):
    """
    Supervisor 생성

    Args:
        intervention_required: 분석/전략 단계부터 HITL 필요 여부 (False: 매매만 HITL, True: 모든 단계 HITL)
        llm: 사용할 LLM (None이면 설정에서 가져옴)

    Returns:
        StateGraph: Supervisor workflow (컴파일되지 않은 상태)
    """
    if llm is None:
        from src.utils.llm_factory import _build_llm, _loop_token

        provider = settings.ROUTER_MODEL_PROVIDER
        model_name = settings.ROUTER_MODEL

        logger.info(
            "🤖 [Supervisor] LLM 초기화: provider=%s, model=%s",
            provider,
            model_name,
        )

        llm = _build_llm(
            provider=provider,
            model_name=model_name,
            temperature=0.0,
            max_tokens=settings.MAX_TOKENS,
            loop_token=_loop_token(),
        )

    # Tools 수집
    tools = get_all_tools()
    logger.info(f"🔧 [Supervisor] Tools 로드 완료: {len(tools)}개")

    # Supervisor Prompt
    prompt = build_supervisor_prompt()

    # SubGraphs 등록 (이미 compile된 상태)
    agents = [
        research_agent,      # Research SubGraph (정성적 분석)
        quantitative_agent,  # Quantitative SubGraph (정량적 분석)
    ]

    logger.info(f"👥 [Supervisor] SubGraphs 로드 완료: {len(agents)}개")
    for agent in agents:
        logger.info(f"  - {agent.name}")

    # Supervisor 생성 (langgraph_supervisor 패턴)
    # create_supervisor가 자동으로 transfer_to_Research_Agent 등의 handoff tools 생성
    supervisor_workflow = create_supervisor(
        agents=agents,
        model=llm,
        tools=tools,
        prompt=prompt,
        parallel_tool_calls=True,  # 병렬 실행 허용
        state_schema=GraphState,
        output_mode="last_message",  # SubGraph 결과 중 마지막 메시지만 반환
    )

    # Trading 노드 추가 (서브그래프가 아닌 직접 노드로 등록)
    supervisor_workflow.add_node("trade_planner", trade_planner_node)
    supervisor_workflow.add_node("portfolio_simulator", portfolio_simulator_node)
    supervisor_workflow.add_node("trade_hitl", trade_hitl_node)
    supervisor_workflow.add_node("execute_trade", execute_trade_node)

    # Trading 노드 라우팅 추가 (planner → simulator → hitl → executor)
    supervisor_workflow.add_edge("trade_planner", "portfolio_simulator")
    supervisor_workflow.add_edge("portfolio_simulator", "trade_hitl")

    # trade_hitl 조건부 edge: 수정 시 재시뮬레이션, 승인 시 실행
    def should_resimulate(state: GraphState) -> str:
        """
        사용자 수정사항이 있어 재시뮬레이션이 필요한지 판단

        Returns:
            "portfolio_simulator": 재시뮬레이션 필요 (수정 발생)
            "execute_trade": 실행 진행 (승인 또는 수정 없음)
        """
        # trade_approved가 False면 재시뮬레이션 필요 (수정 발생)
        if not state.get("trade_approved", False):
            return "portfolio_simulator"
        # trade_prepared가 True면 실행 진행
        if state.get("trade_prepared", False):
            return "execute_trade"
        # 기본값: 실행 진행
        return "execute_trade"

    supervisor_workflow.add_conditional_edges(
        "trade_hitl",
        should_resimulate,
        {
            "portfolio_simulator": "portfolio_simulator",  # 재시뮬레이션
            "execute_trade": "execute_trade",  # 실행
        }
    )

    from langgraph.graph import END
    supervisor_workflow.add_edge("execute_trade", END)

    logger.info("✅ [Supervisor] 생성 완료 (intervention_required=%s, agents=%d, tools=%d, trading_nodes=4)",
                intervention_required, len(agents), len(tools))

    return supervisor_workflow


# ==================== Graph 컴파일 ====================


@lru_cache(maxsize=16)
def get_compiled_graph(intervention_required: bool, use_checkpointer: bool = True):
    """
    컴파일된 Supervisor graph 반환 (캐싱)

    Args:
        intervention_required: 분석/전략 단계부터 HITL 필요 여부
        use_checkpointer: True면 PostgreSQL checkpointer 사용, False면 미사용
                         (LangGraph Studio는 자체 persistence 제공하므로 False)

    Returns:
        CompiledStateGraph: 컴파일된 graph
    """
    supervisor_workflow = build_supervisor(intervention_required=intervention_required)

    if use_checkpointer:
        # Checkpointer 추가 (상태 관리 및 HITL 승인 처리를 위해 필수)
        from src.utils.checkpointer_factory import get_checkpointer
        checkpointer = get_checkpointer()
        compiled_graph = supervisor_workflow.compile(
            checkpointer=checkpointer
        )

        checkpointer_type = type(checkpointer).__name__
        logger.info(
            "🔧 [Graph] 컴파일 완료 (intervention_required=%s, checkpointer=%s)",
            intervention_required,
            checkpointer_type,
        )
    else:
        # LangGraph Studio 환경: checkpointer 없이 컴파일
        compiled_graph = supervisor_workflow.compile()
        logger.info(
            "🔧 [Graph] 컴파일 완료 (intervention_required=%s, checkpointer=None - LangGraph Studio mode)",
            intervention_required,
        )

    return compiled_graph


# ==================== Main Interface ====================

def build_graph(intervention_required: bool = False, use_checkpointer: bool = True, **kwargs):
    """
    Supervisor graph 생성 (기존 API 호환)

    Args:
        intervention_required: 분석/전략 단계부터 HITL 필요 여부 (False: 매매만 HITL, True: 모든 단계 HITL)
        use_checkpointer: True면 PostgreSQL checkpointer 사용 (기본값)
                         False면 미사용 (LangGraph Studio용)
        **kwargs: 기타 인자 (무시됨 - 하위 호환성 유지)

    Returns:
        CompiledStateGraph: 컴파일된 Supervisor graph

    Examples:
        >>> # API 사용 (checkpointer 필요)
        >>> graph = build_graph(intervention_required=False)

        >>> # LangGraph Studio 사용 (checkpointer 불필요)
        >>> graph = build_graph(intervention_required=True, use_checkpointer=False)
    """
    return get_compiled_graph(intervention_required=intervention_required, use_checkpointer=use_checkpointer)
