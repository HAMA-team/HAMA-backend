"""
LangGraph Supervisor 패턴 기반 마스터 에이전트

Master Agent의 역할 (순수 조율자):
1. 사용자 질의를 LLM으로 분석
2. 적절한 에이전트들 선택 (LLM 기반 동적 라우팅)
3. 에이전트 실행 (병렬 가능)
4. 결과 통합

중요: Master는 비즈니스 로직을 수행하지 않음!
      모든 실제 작업은 서브그래프(에이전트)가 수행
      HITL도 각 서브그래프 내부에서 처리
"""
from typing import Dict, Any
from langgraph_supervisor import create_supervisor
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import logging

# Compiled Agents import
from src.agents.research import research_agent
from src.agents.strategy import strategy_agent
from src.agents.risk import risk_agent
from src.agents.trading import trading_agent
from src.agents.general import general_agent

# Legacy agents (TODO: 서브그래프로 전환)
from src.agents.portfolio import portfolio_agent
from src.agents.monitoring import monitoring_agent

logger = logging.getLogger(__name__)


# ==================== Supervisor 구성 ====================

def build_supervisor(automation_level: int = 2):
    """
    LangGraph Supervisor 패턴 기반 Master Agent

    Args:
        automation_level: 자동화 레벨
            - 1 (Pilot): 거의 자동
            - 2 (Copilot): 매매/리밸런싱 승인 필요 (기본값)
            - 3 (Advisor): 모든 결정 승인 필요

    Returns:
        StateGraph: Supervisor 그래프
    """
    # LLM 초기화
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Supervisor 프롬프트
    supervisor_prompt = f"""당신은 투자 에이전트 팀을 관리하는 Supervisor입니다.

**사용 가능한 에이전트:**

1. **research_agent** (종목 분석)
   - 기업 재무 분석 (재무제표, 비율)
   - 기술적 분석 (차트, 지표)
   - 뉴스 감정 분석
   - 종합 평가 및 등급 산출

2. **strategy_agent** (투자 전략)
   - 시장 사이클 분석
   - 섹터 로테이션 전략
   - 자산 배분 결정
   - Strategic Blueprint 생성

3. **risk_agent** (리스크 평가)
   - 포트폴리오 리스크 측정 (VaR, 변동성)
   - 집중도 리스크 분석
   - 리스크 경고 및 권고사항 생성

4. **trading_agent** (매매 실행)
   - 매매 주문 생성 및 실행
   - ⚠️ automation_level {automation_level}에서는 승인 필요

5. **portfolio_agent** (포트폴리오 관리)
   - 포트폴리오 구성 및 최적화
   - 리밸런싱 제안

6. **monitoring_agent** (시장 모니터링)
   - 가격 변동 추적
   - 이벤트 감지 (거래량 급증, VI 발동)
   - 정기 리포트 생성

7. **general_agent** (일반 질의응답)
   - 투자 용어 설명 (PER, PBR 등)
   - 일반 시장 질문 응답
   - 투자 전략 교육

**중요 규칙:**

1. **병렬 실행 가능**: 여러 에이전트를 동시에 호출할 수 있습니다.
   예: 종목 분석 시 research + strategy + risk 동시 호출

2. **에이전트 조합 예시:**
   - "삼성전자 분석해줘" → research_agent + strategy_agent + risk_agent
   - "내 포트폴리오 리밸런싱" → portfolio_agent + risk_agent
   - "PER이 뭐야?" → general_agent
   - "삼성전자 10주 매수" → trading_agent

3. **HITL (Human-in-the-Loop):**
   - 각 에이전트가 내부적으로 HITL을 처리합니다.
   - 현재 automation_level: {automation_level}
   - trading_agent는 레벨 2+ 에서 자동 승인 요청

4. **필요한 에이전트만 선택:**
   - 불필요한 에이전트는 호출하지 마세요.
   - 사용자 요청을 정확히 분석하세요.

사용자 요청을 분석하고, 적절한 에이전트들을 선택하세요.
"""

    # Supervisor 생성
    supervisor = create_supervisor(
        agents=[
            research_agent,
            strategy_agent,
            risk_agent,
            trading_agent,
            general_agent,
            # portfolio_agent,  # TODO: 서브그래프로 전환
            # monitoring_agent,
        ],
        model=llm,
        parallel_tool_calls=True,  # ⭐ 병렬 실행 활성화
        prompt=supervisor_prompt,
    )

    logger.info(f"✅ [Supervisor] 생성 완료 (자동화 레벨: {automation_level})")

    return supervisor


# ==================== 그래프 빌드 ====================

def build_graph(automation_level: int = 2):
    """
    최종 그래프 빌드

    Args:
        automation_level: 자동화 레벨

    Returns:
        Compiled graph
    """
    supervisor = build_supervisor(automation_level)

    # 컴파일 (checkpointer 설정)
    app = supervisor.compile(
        checkpointer=MemorySaver(),  # TODO: AsyncSqliteSaver로 변경
    )

    logger.info(f"🔧 [Graph] 컴파일 완료")

    return app


# Global compiled graph (필요 시 lazy 초기화)
# graph_app = build_graph(automation_level=2)  # 주석 처리: lazy init


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
        thread_id = request_id

    # Supervisor 그래프 빌드
    app = build_graph(automation_level=automation_level)

    # Config
    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    # 초기 State
    initial_state = {
        "messages": [HumanMessage(content=query)],
    }

    logger.info(f"🚀 [Graph] 실행 시작: {query[:50]}...")

    # 실행 (Supervisor가 모든 조율 수행)
    result = await app.ainvoke(initial_state, config=config)

    logger.info(f"✅ [Graph] 실행 완료")

    # 최종 응답 추출
    final_message = result["messages"][-1]

    return {
        "message": final_message.content if hasattr(final_message, 'content') else str(final_message),
        "messages": result.get("messages", []),
    }
