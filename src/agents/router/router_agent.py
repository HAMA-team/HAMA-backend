"""
Router Agent: 질문 분석 및 실행 계획 수립

Router의 역할:
1. 질문 복잡도 분석 (simple/moderate/expert)
2. 필요한 에이전트 선택 (research/strategy/risk/trading/portfolio/general)
3. 답변 깊이 수준 결정 (brief/detailed/comprehensive)
4. 사용자 프로파일 기반 개인화 설정
"""
import logging
from typing import Optional, Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field, ConfigDict

from src.config.settings import settings

logger = logging.getLogger(__name__)


class PersonalizationSettings(BaseModel):
    """Router가 생성하는 개인화 설정."""

    model_config = ConfigDict(extra="forbid")

    adjust_for_expertise: Optional[bool] = Field(
        default=None, description="사용자 전문성에 맞춰 난이도를 조정할지 여부"
    )
    include_explanations: Optional[bool] = Field(
        default=None, description="추가 설명을 포함할지 여부"
    )
    use_analogies: Optional[bool] = Field(
        default=None, description="비유를 활용할지 여부"
    )
    focus_on_metrics: Optional[list[str]] = Field(
        default=None, description="강조해야 할 핵심 지표 리스트"
    )
    sector_comparison: Optional[bool] = Field(
        default=None, description="동일 섹터 비교를 포함할지 여부"
    )
    show_formulas: Optional[bool] = Field(
        default=None, description="계산식을 노출할지 여부"
    )
    include_sensitivity: Optional[bool] = Field(
        default=None, description="민감도 분석을 포함할지 여부"
    )
    technical_level: Optional[str] = Field(
        default=None, description="설명을 제공할 기술적 난이도 (basic/intermediate/advanced)"
    )


class RoutingDecision(BaseModel):
    """Router의 판단 결과"""

    # 1. 질문 분석
    query_complexity: str = Field(
        description="질문 복잡도: simple | moderate | expert"
    )
    user_intent: str = Field(
        description="사용자 의도: quick_info | stock_analysis | trading | portfolio_management | definition | etc"
    )

    # 2. 종목 정보 추출
    stock_names: Optional[list[str]] = Field(
        default=None,
        description="질문에서 추출한 종목명 리스트 (예: ['SK하이닉스', '삼성전자']). 종목이 없으면 None."
    )

    # 3. 에이전트 선택
    agents_to_call: list[str] = Field(
        description="호출할 에이전트 리스트: research, strategy, risk, trading, portfolio, general"
    )

    # 4. 답변 깊이 수준
    depth_level: str = Field(
        description="답변 깊이: brief | detailed | comprehensive"
    )

    # 5. 개인화 설정
    personalization: PersonalizationSettings = Field(
        description="개인화 설정 (adjust_for_expertise, include_explanations, use_analogies 등)"
    )

    # 6. 근거
    reasoning: str = Field(description="판단 근거")

    def __getitem__(self, item: str) -> Any:
        """dict 호환을 위한 키 기반 접근 지원"""
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        """dict.get과 동일한 동작 제공"""
        return getattr(self, item, default)

    def keys(self):
        return self.dict().keys()

    def items(self):
        return self.dict().items()

    def values(self):
        return self.dict().values()


async def route_query(
    query: str,
    user_profile: dict,
    conversation_history: Optional[list] = None,
    config: Optional[RunnableConfig] = None,
) -> RoutingDecision:
    """
    Router Agent: 질문을 분석하고 실행 계획 수립

    Args:
        query: 사용자 질문
        user_profile: 사용자 프로파일 (투자 성향, 경험 수준)
        conversation_history: 대화 히스토리 (최근 3턴)

        config: LangChain RunnableConfig (선택적)

    Returns:
        RoutingDecision: 라우팅 결정
    """
    if conversation_history is None:
        conversation_history = []

    # 빈 쿼리 검증
    query = query.strip()
    if not query:
        logger.warning("⚠️ [Router] 빈 질문 감지 - 기본 라우팅 반환")
        return RoutingDecision(
            query_complexity="simple",
            user_intent="general_inquiry",
            stock_names=None,
            agents_to_call=["general"],
            depth_level="brief",
            personalization=PersonalizationSettings(
                adjust_for_expertise=True,
                include_explanations=True,
                use_analogies=True,
                technical_level="basic",
            ),
            reasoning="빈 질문이므로 general agent로 라우팅",
        )

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
2. **질문에서 종목명을 추출하세요** (예: "SK하이닉스", "삼성전자") - 종목이 없으면 None
3. 필요한 에이전트를 선택하세요 (research/strategy/risk/trading/portfolio/general)
4. 답변 깊이 수준을 결정하세요 (brief/detailed/comprehensive)
5. 사용자 프로파일을 고려하여 개인화 설정을 결정하세요

**종목명 추출 규칙:**
- 종목명만 추출하세요 (예: "SK하이닉스", "삼성전자", "네이버")
- 띄어쓰기를 정규화하세요 (예: "sk 하이닉스" → "SK하이닉스")
- 종목명이 아닌 단어는 제외하세요 (예: "전망", "분석", "매수", "어때" 등)
- 한국 상장 기업명만 추출하세요
- 종목명이 없으면 None을 반환하세요

**종목명 추출 예시:**
- "sk 하이닉스 전망 분석해줘" → ["SK하이닉스"]
- "삼성전자와 SK하이닉스 비교해줘" → ["삼성전자", "SK하이닉스"]
- "PER이 뭐야?" → None
- "코스피 지수는?" → None

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

    # Router 전용 LLM 초기화 (OpenAI → Anthropic fallback)
    router_provider = settings.ROUTER_MODEL_PROVIDER.lower()

    llm = None
    if router_provider == "openai":
        try:
            llm = ChatOpenAI(
                model=settings.ROUTER_MODEL,
                temperature=0,
                api_key=settings.OPENAI_API_KEY,
            )
            logger.info("🤖 [Router] OpenAI 모델 사용")
        except Exception as e:
            logger.warning(f"⚠️ [Router] OpenAI 초기화 실패, Anthropic으로 fallback: {e}")

    if llm is None:  # OpenAI 실패 또는 anthropic 설정
        try:
            llm = ChatAnthropic(
                model=settings.ROUTER_MODEL or "claude-3-5-sonnet-20241022",
                temperature=0,
                api_key=settings.ANTHROPIC_API_KEY,
            )
            logger.info("🤖 [Router] Anthropic 모델 사용")
        except Exception as e:
            logger.error(f"❌ [Router] Anthropic 초기화 실패: {e}")
            raise RuntimeError("Router LLM 초기화 실패 (OpenAI, Anthropic 모두 실패)")

    structured_llm = llm.with_structured_output(RoutingDecision)
    router_chain = router_prompt | structured_llm

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

    prompt_inputs = {
        "query": query,
        "user_expertise": user_expertise,
        "investment_style": investment_style,
        "preferred_sectors": ", ".join(preferred_sectors) if preferred_sectors else "없음",
        "avg_trades_per_day": avg_trades_per_day,
        "technical_level": technical_level,
        "conversation_history": history_text,
    }

    try:
        if config is not None:
            result = await router_chain.ainvoke(prompt_inputs, config=config)
        else:
            result = await router_chain.ainvoke(prompt_inputs)

        logger.info(f"✅ [Router] 판단 완료:")
        logger.info(f"  - 복잡도: {result.query_complexity}")
        logger.info(f"  - 의도: {result.user_intent}")
        logger.info(f"  - 종목명: {result.stock_names}")
        logger.info(f"  - 에이전트: {result.agents_to_call}")
        logger.info(f"  - 깊이: {result.depth_level}")
        logger.info(f"  - 근거: {result.reasoning}")

        return result

    except Exception as e:
        logger.error(f"❌ [Router] 에러: {e}")
        raise
