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
from pydantic import BaseModel, Field, ConfigDict

from src.config.settings import settings
from src.utils.llm_factory import get_claude_llm
from src.utils.text_utils import ensure_plain_text

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


class WorkerParams(BaseModel):
    """워커 파라미터 (OpenAI Structured Output 호환)"""

    model_config = ConfigDict(extra="forbid")

    stock_code: Optional[str] = Field(
        default=None, description="종목 코드 (예: '005930')"
    )
    stock_name: Optional[str] = Field(
        default=None, description="종목명 (예: '삼성전자')"
    )
    index_name: Optional[str] = Field(
        default=None, description="지수명 (예: '코스피', '코스닥')"
    )

    def __getitem__(self, item: str) -> Any:
        """dict 호환을 위한 키 기반 접근 지원"""
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        """dict.get과 동일한 동작 제공"""
        return getattr(self, item, default)


class RoutingDecision(BaseModel):
    """Router의 판단 결과"""

    model_config = ConfigDict(extra="forbid")

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
        description="단순 조회 워커 이름 (stock_price 또는 index_price). 데이터 조회가 필요하지 않으면 이 필드를 생략하세요."
    )
    worker_params: Optional[WorkerParams] = Field(
        default=None,
        description="워커 파라미터. worker_action이 있을 때만 필요합니다."
    )

    # 8. 직접 답변 (간단한 질문인 경우 Router가 직접 응답)
    direct_answer: Optional[str] = Field(
        default=None,
        description="일반 질문/용어 정의인 경우 이 필드에 최종 답변을 작성하세요. agents_to_call이 빈 리스트이고 worker_action이 없을 때 필수입니다."
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
    query: Any,
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
    normalized_query = ensure_plain_text(query)

    if conversation_history is None:
        conversation_history = []

    # 빈 쿼리 검증
    query = normalized_query.strip()
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

    # 대화 히스토리 포맷팅 (있을 경우)
    conversation_context = ""
    if conversation_history and len(conversation_history) > 0:
        history_lines = []
        for msg in conversation_history:
            role = "사용자" if msg["role"] == "user" else "AI"
            content = ensure_plain_text(msg.get("content"))
            if not content.strip():
                continue
            history_lines.append(f"{role}: {content}")
        conversation_context = "\n".join(history_lines)
        logger.info(f"📜 [Router] 대화 히스토리 포맷팅 완료 ({len(conversation_history)}개 메시지)")
        logger.info(f"  히스토리 내용:\n{conversation_context[:500]}{'...' if len(conversation_context) > 500 else ''}")

    router_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """당신은 투자 질문을 분석하여 적절한 처리 방법을 결정하는 라우터입니다.

<user_context>
투자 경험: {user_expertise}
투자 성향: {investment_style}
</user_context>

{conversation_context_block}

<instructions>
사용자 질문을 분석하여 다음 중 하나를 선택하세요:

1. **워커 직접 호출** (단순 데이터 조회)
   - 언제: 주가, 지수 같은 단일 데이터만 필요할 때
   - 설정: agents_to_call=[], worker_action="stock_price" 또는 "index_price", worker_params 지정
   - 예: "삼성전자 주가?"

2. **에이전트 호출** (분석/전략 수립)
   - 언제: 종목 분석, 투자 전략, 리스크 평가 등이 필요할 때
   - 설정: agents_to_call=["research", "strategy", ...], worker_action 생략
   - 가능한 에이전트: research, strategy, risk, trading, portfolio
   - 예: "삼성전자 분석해줘" → ["research"]

3. **직접 답변** (일반 지식/용어 설명)
   - 언제: 투자 관련 일반 지식, 용어 정의, 시스템 안내
   - 설정: agents_to_call=[], direct_answer="답변 내용"
   - 예: "PER이 뭐야?", "장 운영 시간은?"

<thinking_process>
다음 순서로 판단하세요:

1. 질문 의도 파악
   - 데이터 조회? → 워커
   - 분석/판단? → 에이전트
   - 일반 지식? → 직접 답변

2. 복잡도 결정
   - simple: 단순 조회/정의
   - moderate: 일반적 분석
   - expert: 심층 분석 또는 의사결정

3. 종목 추출
   - 종목명이 언급되었는가?
   - stock_names에 리스트로 저장

4. 사용자 맞춤화
   - 초보자 → 더 자세한 설명 필요 (include_explanations=true)
   - 전문가 → 핵심만 제공 (technical_level="advanced")
</thinking_process>

<output_rules>
- 필요 없는 필드는 JSON에서 완전히 생략 (null, "None" 사용 금지)
- reasoning은 구체적이고 명확하게 작성
- stock_names는 질문에서 실제 언급된 종목만 포함
- depth_level은 복잡도와 일치시킬 것 (simple→brief, moderate→detailed, expert→comprehensive)
</output_rules>
</instructions>

<examples>
예시 1 - 워커 호출:
입력: "삼성전자 주가 얼마야?"
출력: {{"query_complexity": "simple", "user_intent": "quick_info", "stock_names": ["삼성전자"], "agents_to_call": [], "depth_level": "brief", "worker_action": "stock_price", "worker_params": {{"stock_name": "삼성전자"}}, "reasoning": "단순 주가 조회이므로 워커 직접 호출"}}

예시 2 - 에이전트 호출:
입력: "삼성전자 매수해도 될까?"
출력: {{"query_complexity": "expert", "user_intent": "trading", "stock_names": ["삼성전자"], "agents_to_call": ["research", "strategy"], "depth_level": "comprehensive", "reasoning": "매수 판단을 위해 종목 분석 및 전략 수립 필요"}}

예시 3 - 직접 답변:
입력: "PER이 뭐야?"
출력: {{"query_complexity": "simple", "user_intent": "definition", "stock_names": null, "agents_to_call": [], "depth_level": "brief", "direct_answer": "PER(주가수익비율)은 주가를 주당순이익으로 나눈 값으로, 주가가 1주당 수익의 몇 배로 거래되는지를 나타냅니다.", "reasoning": "용어 정의 질문이므로 직접 답변"}}
</examples>
""",
            ),
            ("human", "질문: {query}"),
        ]
    )

    # Router 전용 LLM 초기화 (Claude Sonnet 4.5 사용)
    from src.utils.llm_factory import get_router_llm

    try:
        llm = get_router_llm(temperature=0, max_tokens=2000)
    except Exception as e:
        logger.error(f"❌ [Router] Claude 초기화 실패: {e}")
        raise RuntimeError("Router LLM 초기화 실패 (Claude Sonnet 4.5)")

    structured_llm = llm.with_structured_output(RoutingDecision)
    router_chain = router_prompt | structured_llm

    logger.info(f"🧭 [Router] 질문 분석 시작: {query[:50]}...")

    # 대화 히스토리 블록 구성
    conversation_context_block = ""
    if conversation_context:
        conversation_context_block = f"""<conversation_history>
이전 대화 내역:
{conversation_context}
</conversation_history>

위 대화 내용을 참고하여 현재 질문의 맥락을 파악하세요. 사용자가 이전 대화를 언급하는 경우(예: "방금", "아까", "그것") 히스토리를 활용하여 답변하세요."""

    prompt_inputs = {
        "query": query,
        "user_expertise": user_expertise,
        "investment_style": investment_style,
        "conversation_context_block": conversation_context_block,
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
            simple_llm = get_claude_llm(
                temperature=0.7,
                max_tokens=500,
            )

            # 대화 히스토리 포함 프롬프트 (맥락 참고)
            simple_messages = [
                ("system", """당신은 친절한 투자 도우미입니다.
사용자의 간단한 질문에 명확하고 간결하게 답변하세요.

답변 원칙:
- 1-3문장으로 핵심만 전달
- 전문 용어는 쉽게 풀어서 설명
- 투자 관련 질문이 아니어도 친절하게 답변
- 한국어로 자연스럽게 작성
- 이전 대화 내용을 참고하여 맥락에 맞는 답변 제공
- 사용자가 "방금", "아까", "그것" 등으로 이전 대화를 언급하면 대화 히스토리를 활용하여 구체적으로 답변""")
            ]

            # 대화 히스토리가 있으면 실제 메시지로 추가
            if conversation_history:
                logger.info(f"💬 [Router] simple_llm에 대화 히스토리 {len(conversation_history)}개 추가")
                for msg in conversation_history:
                    role = "human" if msg["role"] == "user" else "ai"
                    content = ensure_plain_text(msg.get("content"))
                    if not content.strip():
                        continue
                    simple_messages.append((role, content))

            # 현재 질문 추가
            simple_messages.append(("human", "{query}"))

            simple_prompt = ChatPromptTemplate.from_messages(simple_messages)
            simple_chain = simple_prompt | simple_llm

            try:
                simple_inputs = {
                    "query": query,
                }

                if config is not None:
                    answer_msg = await simple_chain.ainvoke(simple_inputs, config=config)
                else:
                    answer_msg = await simple_chain.ainvoke(simple_inputs)

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
