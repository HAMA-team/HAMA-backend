"""
General Agent 노드 함수들

일반 질의응답을 위한 노드
"""
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from src.agents.general.state import GeneralState

logger = logging.getLogger(__name__)


async def answer_question_node(state: GeneralState) -> dict:
    """
    일반 질문 응답 노드 (LLM)

    투자 용어, 개념, 일반 시장 질문에 답변

    TODO Phase 2:
    - RAG 연동 (투자 용어 사전)
    - 벡터 DB 검색 (유사 질문)
    """
    query = state.get("query", "")

    logger.info(f"💬 [General] 질문 응답 중: {query[:50]}...")

    try:
        # LLM 초기화 (API 키 확인)
        from src.config.settings import settings
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "test-key-not-used":
            raise ValueError("OPENAI_API_KEY not configured")

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

        # 시스템 프롬프트
        system_prompt = """당신은 투자 교육 전문가입니다.

역할:
- 투자 용어를 쉽게 설명
- 시장 개념을 이해하기 쉽게 전달
- 투자 전략을 교육
- 일반적인 시장 질문에 답변

중요:
- 간단명료하게 답변하세요.
- 전문 용어는 풀어서 설명하세요.
- 예시를 들어 설명하세요.
- 투자 권유는 하지 마세요.

예시:
Q: PER이 뭐야?
A: PER(주가수익비율)은 주가를 주당순이익(EPS)으로 나눈 값입니다.
   예를 들어, 주가가 10,000원이고 EPS가 1,000원이면 PER은 10배입니다.
   낮을수록 저평가, 높을수록 고평가로 볼 수 있지만, 업종마다 적정 수준이 다릅니다.
"""

        # LLM 호출
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ]

        response = await llm.ainvoke(messages)

        answer = response.content

        logger.info(f"✅ [General] 응답 완료")

        # Supervisor 호환성을 위해 messages 포함
        messages = list(state.get("messages", []))
        messages.append(AIMessage(content=answer))

        return {
            "answer": answer,
            "sources": [],  # TODO: RAG 연동 시 추가
            "messages": messages,
        }

    except Exception as e:
        logger.warning(f"⚠️ [General] LLM 호출 실패 (mock 응답 사용): {e}")

        # Mock 응답 생성
        mock_answers = {
            "per": "PER(주가수익비율)은 주가를 주당순이익(EPS)로 나눈 값입니다. 낮을수록 저평가된 것으로 볼 수 있습니다.",
            "pbr": "PBR(주가순자산비율)은 주가를 주당순자산(BPS)로 나눈 값입니다. 1 미만이면 순자산 대비 저평가로 볼 수 있습니다.",
            "default": f"'{query}' 관련 질문에 대한 답변입니다. (테스트 환경에서는 mock 응답이 제공됩니다)"
        }

        # 키워드 기반 mock 응답 선택
        answer = mock_answers.get("default")
        for keyword, response in mock_answers.items():
            if keyword in query.lower():
                answer = response
                break

        # Mock 응답을 messages에 포함
        messages = list(state.get("messages", []))
        messages.append(AIMessage(content=answer))

        return {
            "answer": answer,
            "sources": [],
            "messages": messages,
        }
