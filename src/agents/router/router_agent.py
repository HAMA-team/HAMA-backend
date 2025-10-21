"""
Router Agent: 질문 분석 및 실행 계획 수립

Router의 역할:
1. 질문 복잡도 분석 (simple/moderate/expert)
2. 필요한 에이전트 선택 (research/strategy/risk/trading/portfolio/general)
3. 답변 깊이 수준 결정 (brief/detailed/comprehensive)
4. 사용자 프로파일 기반 개인화 설정
"""
import logging
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.config.settings import settings

logger = logging.getLogger(__name__)


class RoutingDecision(BaseModel):
    """Router의 판단 결과"""

    # 1. 질문 분석
    query_complexity: str = Field(
        description="질문 복잡도: simple | moderate | expert"
    )
    user_intent: str = Field(
        description="사용자 의도: quick_info | stock_analysis | trading | portfolio_management | definition | etc"
    )

    # 2. 에이전트 선택
    agents_to_call: list[str] = Field(
        description="호출할 에이전트 리스트: research, strategy, risk, trading, portfolio, general"
    )

    # 3. 답변 깊이 수준
    depth_level: str = Field(
        description="답변 깊이: brief | detailed | comprehensive"
    )

    # 4. 개인화 설정
    personalization: dict = Field(
        description="개인화 설정 (adjust_for_expertise, include_explanations, use_analogies 등)"
    )

    # 5. 근거
    reasoning: str = Field(description="판단 근거")


async def route_query(
    query: str,
    user_profile: dict,
    conversation_history: Optional[list] = None,
) -> RoutingDecision:
    """
    Router Agent: 질문을 분석하고 실행 계획 수립

    Args:
        query: 사용자 질문
        user_profile: 사용자 프로파일 (투자 성향, 경험 수준)
        conversation_history: 대화 히스토리 (최근 3턴)

    Returns:
        RoutingDecision: 라우팅 결정
    """
    if conversation_history is None:
        conversation_history = []

    # 사용자 프로파일 기본값
    user_expertise = user_profile.get("expertise_level", "intermediate")
    investment_style = user_profile.get("investment_style", "moderate")
    preferred_sectors = user_profile.get("preferred_sectors", [])
    avg_trades_per_day = user_profile.get("avg_trades_per_day", 1.0)
    technical_level = user_profile.get("technical_level", "intermediate")

    router_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """당신은 투자 질문을 분석하는 Router입니다.

**임무:**
1. 질문의 복잡도를 판단하세요 (simple/moderate/expert)
2. 필요한 에이전트를 선택하세요 (research/strategy/risk/trading/portfolio/general)
3. 답변 깊이 수준을 결정하세요 (brief/detailed/comprehensive)
4. 사용자 프로파일을 고려하여 개인화 설정을 결정하세요

**사용자 프로파일:**
- 투자 경험: {user_expertise}
- 투자 성향: {investment_style}
- 선호 섹터: {preferred_sectors}
- 평균 매매 횟수: {avg_trades_per_day}
- 기술적 이해도: {technical_level}

**질문 복잡도 판단 기준:**
- simple: 단순 정보 조회
  예: "PER이 뭐야?", "삼성전자 현재가는?", "코스피 지수는?"
- moderate: 분석 필요
  예: "삼성전자 분석해줘", "지금 매수 타이밍인가?", "내 포트폴리오 괜찮아?"
- expert: 심층 분석
  예: "삼성전자 DCF 밸류에이션", "포트폴리오 최적화", "리스크 민감도 분석"

**에이전트 선택 가이드:**
- general: 용어 정의, 일반 질문 ("PER이 뭐야?", "투자 전략이란?")
- research: 종목 분석 ("삼성전자 분석", "반도체 업종 전망")
- strategy: 투자 전략, 타이밍 ("지금 매수해야 할까?", "시장 사이클은?")
- risk: 리스크 평가 ("내 포트폴리오 리스크는?", "변동성 분석")
- portfolio: 포트폴리오 관리 ("리밸런싱 해줘", "포트폴리오 구성")
- trading: 매매 실행 ("삼성전자 10주 매수", "전량 매도")

**답변 깊이 수준:**
- brief: 핵심만 (1-2문장, 초보자용)
  예: 초보자의 간단한 질문, 빠른 정보 확인
- detailed: 상세 설명 (근거 포함, 중급자용)
  예: 중급자의 분석 요청, 일반적인 투자 질문
- comprehensive: 전문가 수준 (모든 지표, 계산 과정, 대안 포함)
  예: 전문가의 심층 분석 요청, DCF/포트폴리오 최적화

**개인화 원칙:**
- 초보자 (beginner):
  * adjust_for_expertise: True
  * include_explanations: True
  * use_analogies: True
  * technical_level: "basic"

- 중급자 (intermediate):
  * adjust_for_expertise: True
  * include_explanations: False (핵심만)
  * focus_on_metrics: ["PER", "PBR", "ROE"] (주요 지표)
  * sector_comparison: True (선호 섹터 비교)

- 전문가 (expert):
  * adjust_for_expertise: False (원데이터)
  * include_explanations: False
  * show_formulas: True (계산식)
  * include_sensitivity: True (민감도 분석)

**출력 형식:**
JSON으로 RoutingDecision 스키마에 맞게 출력하세요.
""",
            ),
            ("human", "질문: {query}\n\n이전 대화:\n{conversation_history}"),
        ]
    )

    llm = ChatOpenAI(
        model="gpt-4o", temperature=0, api_key=settings.OPENAI_API_KEY
    )
    structured_llm = llm.with_structured_output(RoutingDecision)

    # 대화 히스토리 포맷팅
    history_text = "\n".join(
        [
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in conversation_history[-3:]  # 최근 3턴만
        ]
    )
    if not history_text:
        history_text = "(없음)"

    logger.info(f"🧭 [Router] 질문 분석 시작: {query[:50]}...")

    try:
        result = await structured_llm.ainvoke(
            router_prompt.format_messages(
                query=query,
                user_expertise=user_expertise,
                investment_style=investment_style,
                preferred_sectors=", ".join(preferred_sectors)
                if preferred_sectors
                else "없음",
                avg_trades_per_day=avg_trades_per_day,
                technical_level=technical_level,
                conversation_history=history_text,
            )
        )

        logger.info(f"✅ [Router] 판단 완료:")
        logger.info(f"  - 복잡도: {result.query_complexity}")
        logger.info(f"  - 의도: {result.user_intent}")
        logger.info(f"  - 에이전트: {result.agents_to_call}")
        logger.info(f"  - 깊이: {result.depth_level}")
        logger.info(f"  - 근거: {result.reasoning}")

        return result

    except Exception as e:
        logger.error(f"❌ [Router] 에러: {e}")

        # Fallback: 기본 라우팅
        return RoutingDecision(
            query_complexity="moderate",
            user_intent="general_inquiry",
            agents_to_call=["general"],
            depth_level="detailed",
            personalization={
                "adjust_for_expertise": True,
                "include_explanations": user_expertise == "beginner",
            },
            reasoning=f"에러 발생으로 기본 라우팅 적용: {str(e)}",
        )
