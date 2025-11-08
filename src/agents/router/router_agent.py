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
        description="호출할 에이전트 리스트: research, strategy, risk, trading, portfolio (간단한 질문은 빈 리스트)"
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

    # 7. 워커 직접 호출 (단순 데이터 조회)
    worker_action: Optional[str] = Field(
        default=None,
        description="단순 조회 워커: stock_price | index_price | None. agents_to_call이 빈 리스트이고 데이터 조회가 필요한 경우만 사용."
    )
    worker_params: Optional[dict] = Field(
        default=None,
        description="워커 파라미터 (stock_code, stock_name, index_name 등)"
    )

    # 8. 직접 답변 (간단한 질문인 경우 Router가 직접 응답)
    direct_answer: Optional[str] = Field(
        default=None,
        description="간단한 질문이면 Router가 직접 생성한 답변. agents_to_call이 빈 리스트이고 worker_action도 None일 때만 사용."
    )

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
        logger.warning("⚠️ [Router] 빈 질문 감지 - Supervisor가 직접 처리")
        return RoutingDecision(
            query_complexity="simple",
            user_intent="general_inquiry",
            stock_names=None,
            agents_to_call=[],
            depth_level="brief",
            personalization=PersonalizationSettings(
                adjust_for_expertise=True,
                include_explanations=True,
                use_analogies=True,
                technical_level="basic",
            ),
            reasoning="빈 질문이므로 Supervisor가 직접 처리",
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
                """투자 질문을 분석하여 적절한 에이전트 또는 워커로 라우팅합니다.

**우선순위 1: 워커 직접 호출 (빠른 단순 조회)**
agents_to_call = [], worker_action 설정:
- "삼성전자 현재가?", "SK하이닉스 주가?" → worker_action="stock_price", worker_params={{"stock_code": "005930", "stock_name": "삼성전자"}}
- "코스피 지수?", "코스닥 얼마야?" → worker_action="index_price", worker_params={{"index_name": "코스피"}}

**우선순위 2: 에이전트 호출 (분석/전략/실행)**
- research: 종목 분석 요청 ("삼성전자 분석해줘", "재무제표 분석")
- strategy: 투자 전략/타이밍 ("언제 사야해?", "매수 타이밍")
- risk: 리스크 평가 ("위험도는?", "손실 가능성")
- portfolio: 포트폴리오 조회/관리 ("보유 현황", "리밸런싱")
- trading: 매매 실행 ("매수", "매도")

**우선순위 3: Router 직접 답변**
agents_to_call = [], worker_action = None, direct_answer 생성:
- 일반 질문/용어 정의 ("PER이 뭐야?", "안녕?")

**종목명 추출:**
질문에서 기업명을 추출하세요 (예: "lg 화학" → ["LG화학"]).
종목이 없으면 None.

**복잡도:**
- simple: 단순 정보 조회 (현재가, 지수)
- moderate: 분석 필요 (재무, 기술적 분석)
- expert: 심층 분석 (전략 수립, 리스크 평가)

**사용자:** {user_expertise} 수준, {investment_style} 성향

JSON 형식으로 출력하세요.
""",
            ),
            ("human", "질문: {query}"),
        ]
    )

    # Router 전용 LLM 초기화 (OpenAI → Anthropic fallback)
    router_provider = settings.ROUTER_MODEL_PROVIDER.lower()

    llm = None
    if router_provider == "openai":
        try:
            # max_completion_tokens: structured output + reasoning tokens 모두 포함
            # o1 모델은 reasoning_tokens를 많이 사용하므로 충분한 여유 필요
            llm = ChatOpenAI(
                model=settings.ROUTER_MODEL,
                temperature=0,
                max_completion_tokens=2500,  # 증가: structured output(500) + reasoning(2000)
                api_key=settings.OPENAI_API_KEY,
            )
            logger.info(f"🤖 [Router] OpenAI 모델 사용: {settings.ROUTER_MODEL}")
        except Exception as e:
            logger.warning(f"⚠️ [Router] OpenAI 초기화 실패, Anthropic으로 fallback: {e}")

    if llm is None:  # OpenAI 실패 또는 anthropic 설정
        try:
            llm = ChatAnthropic(
                model=settings.ROUTER_MODEL or "claude-3-5-sonnet-20241022",
                temperature=0,
                max_tokens=2000,  # structured output 고려
                api_key=settings.ANTHROPIC_API_KEY,
            )
            logger.info(f"🤖 [Router] Anthropic 모델 사용: {settings.ROUTER_MODEL or 'claude-3-5-sonnet-20241022'}")
        except Exception as e:
            logger.error(f"❌ [Router] Anthropic 초기화 실패: {e}")
            raise RuntimeError("Router LLM 초기화 실패 (OpenAI, Anthropic 모두 실패)")

    structured_llm = llm.with_structured_output(RoutingDecision)
    router_chain = router_prompt | structured_llm

    logger.info(f"🧭 [Router] 질문 분석 시작: {query[:50]}...")

    prompt_inputs = {
        "query": query,
        "user_expertise": user_expertise,
        "investment_style": investment_style,
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
        logger.info(f"  - 워커: {result.worker_action} (params: {result.worker_params})")
        logger.info(f"  - 깊이: {result.depth_level}")
        logger.info(f"  - 근거: {result.reasoning}")

        # 간단한 질문이면 Router가 직접 답변 생성 (워커 호출이 없는 경우만)
        if not result.agents_to_call and not result.worker_action:
            logger.info("💬 [Router] 간단한 질문 - 직접 답변 생성")

            # 간단한 답변용 LLM (structured output 없음, 빠른 모델)
            simple_llm = ChatOpenAI(
                model="gpt-4o-mini",  # 빠르고 저렴한 모델
                temperature=0.7,
                max_completion_tokens=500,  # 간단한 답변용
                api_key=settings.OPENAI_API_KEY,
            )

            simple_prompt = ChatPromptTemplate.from_messages([
                ("system", """당신은 친절한 투자 도우미입니다.
사용자의 간단한 질문에 명확하고 간결하게 답변하세요.

답변 원칙:
- 1-3문장으로 핵심만 전달
- 전문 용어는 쉽게 풀어서 설명
- 투자 관련 질문이 아니어도 친절하게 답변
- 한국어로 자연스럽게 작성"""),
                ("human", "{query}")
            ])

            simple_chain = simple_prompt | simple_llm

            try:
                if config is not None:
                    answer_msg = await simple_chain.ainvoke({"query": query}, config=config)
                else:
                    answer_msg = await simple_chain.ainvoke({"query": query})

                direct_answer = answer_msg.content
                result.direct_answer = direct_answer
                logger.info(f"✅ [Router] 직접 답변: {direct_answer[:100]}...")
            except Exception as e:
                logger.error(f"❌ [Router] 직접 답변 생성 실패: {e}")
                result.direct_answer = "죄송합니다. 답변 생성 중 오류가 발생했습니다."
        elif result.worker_action:
            logger.info(f"⚡ [Router] 워커 호출: {result.worker_action}")

        return result

    except Exception as e:
        logger.error(f"❌ [Router] 에러: {e}")
        raise
