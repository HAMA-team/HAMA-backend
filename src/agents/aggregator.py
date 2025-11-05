"""
Aggregator - 답변 개인화

에이전트 결과를 사용자 프로파일에 맞게 조절하여 최종 응답 생성
"""
import json
import logging
from typing import Dict, Any, Optional

from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from src.config.settings import settings
from src.utils.llm_factory import get_llm

logger = logging.getLogger(__name__)


async def personalize_response(
    agent_results: Dict[str, Any],
    user_profile: Dict[str, Any],
    routing_decision: Optional[Dict[str, Any]] = None,
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """
    에이전트 결과를 사용자 프로파일에 맞게 개인화

    Args:
        agent_results: 각 에이전트의 원본 결과
            예: {"research": {...}, "strategy": {...}}
        user_profile: 사용자 프로파일
        routing_decision: Router 판단 (depth_level, personalization 등)

    Returns:
        개인화된 최종 응답
    """
    logger.info("🎨 [Aggregator] 답변 개인화 시작")

    # 프로파일 정보 추출
    expertise_level = user_profile.get("expertise_level", "intermediate")
    technical_level = user_profile.get("technical_level", "intermediate")
    wants_explanations = user_profile.get("wants_explanations", True)
    wants_analogies = user_profile.get("wants_analogies", False)

    # Router 판단 정보
    depth_level = "detailed"
    personalization_settings = {}
    if routing_decision:
        depth_level = routing_decision.get("depth_level", "detailed")
        personalization = routing_decision.get("personalization")
        if hasattr(personalization, "model_dump"):
            personalization_settings = personalization.model_dump()
        elif isinstance(personalization, dict):
            personalization_settings = personalization

    # 개인화 프롬프트 구성
    personalization_prompt = ChatPromptTemplate.from_messages([
        ("system", """당신은 투자 분석 결과를 사용자에게 맞게 전달하는 Aggregator입니다.

**사용자 프로파일:**
- 투자 경험: {expertise_level}
- 기술적 이해도: {technical_level}
- 용어 설명 필요: {wants_explanations}
- 비유 선호: {wants_analogies}

**개인화 원칙:**

⚠️ **중요: 절대로 예시의 숫자나 가격을 사용하지 마세요. 반드시 에이전트 결과의 실제 데이터만 사용하세요.**

1. **초보자 (beginner):**
   - 전문 용어 설명 추가
   - 비유 사용 (예: "PER은 주식의 가격표 같은 것")
   - 단순화된 표현
   - 핵심만 1-2개
   - 결론을 명확하게

2. **중급자 (intermediate):**
   - 주요 지표 중심 (3-5개)
   - 간단한 설명만
   - 근거 포함
   - 비교 분석 (업종 평균)

3. **전문가 (expert):**
   - 원데이터 제공
   - 계산 과정 포함
   - 모든 지표
   - 민감도 분석
   - 정량적 근거

**답변 깊이 수준: {depth_level}**
- brief: 1-2문장, 핵심만
- detailed: 3-5개 지표, 근거 포함
- comprehensive: 모든 지표, 계산 과정

**에이전트 결과:**
{agent_results}

위 결과를 사용자 프로파일에 맞게 재구성하세요.
응답은 Markdown 형식으로 작성하세요.
"""),
        ("human", "사용자에게 맞게 답변을 작성해주세요.")
    ])

    def _serialize(value: Any) -> Any:
        """
        LangChain 메시지 등 JSON 직렬화 불가 객체를 안전한 형태로 변환
        """
        if isinstance(value, BaseMessage):
            return {
                "type": value.type,
                "content": value.content,
            }
        if isinstance(value, dict):
            return {key: _serialize(val) for key, val in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_serialize(item) for item in value]
        return value

    serializable_results = _serialize(agent_results)

    # LLM 호출 (환경에 맞는 provider/model 사용)
    llm = get_llm(
        temperature=0.3,
        model=settings.llm_model_name,
    )
    personalization_chain = personalization_prompt | llm

    prompt_inputs = {
        "expertise_level": expertise_level,
        "technical_level": technical_level,
        "wants_explanations": "예" if wants_explanations else "아니오",
        "wants_analogies": "예" if wants_analogies else "아니오",
        "depth_level": depth_level,
        "agent_results": json.dumps(serializable_results, ensure_ascii=False, indent=2),
    }

    try:
        if config is not None:
            response_message = await personalization_chain.ainvoke(prompt_inputs, config=config)
        else:
            response_message = await personalization_chain.ainvoke(prompt_inputs)

        personalized_response = (
            response_message.content
            if hasattr(response_message, "content")
            else str(response_message)
        )

        logger.info("✅ [Aggregator] 개인화 완료")

        return {
            "success": True,
            "response": personalized_response,
            "metadata": {
                "expertise_level": expertise_level,
                "depth_level": depth_level,
                "personalization_applied": True
            }
        }

    except Exception as e:
        logger.error(f"❌ [Aggregator] 에러: {e}")

        # Fallback: 원본 결과 반환
        fallback_response = json.dumps(serializable_results, ensure_ascii=False, indent=2)

        return {
            "success": False,
            "response": fallback_response,
            "error": str(e),
            "metadata": {
                "expertise_level": expertise_level,
                "depth_level": depth_level,
                "personalization_applied": False
            }
        }


async def aggregate_multi_agent_results(
    query: str,
    agent_results: Dict[str, Any],
    user_profile: Dict[str, Any],
    routing_decision: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    여러 에이전트 결과 통합 및 개인화

    Args:
        query: 사용자 질문
        agent_results: 각 에이전트 결과
            예: {
                "research": {...},
                "strategy": {...},
                "risk": {...}
            }
        user_profile: 사용자 프로파일
        routing_decision: Router 판단

    Returns:
        통합 및 개인화된 최종 응답
    """
    logger.info(f"🔗 [Aggregator] 다중 에이전트 결과 통합: {list(agent_results.keys())}")

    # 1. 결과 통합
    # TODO: 에이전트 간 결과 조합 로직 (현재는 단순 병합)

    # 2. 개인화
    personalized = await personalize_response(
        agent_results=agent_results,
        user_profile=user_profile,
        routing_decision=routing_decision
    )

    return {
        **personalized,
        "query": query,
        "agents_called": list(agent_results.keys())
    }
