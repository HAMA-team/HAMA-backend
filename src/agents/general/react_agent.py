"""
ReAct 기반 General Agent 생성기
"""
from langgraph.prebuilt import create_react_agent

from src.config.settings import settings
from src.utils.llm_factory import get_llm

from .tools import lookup_stock, get_stock_quote, web_search


def create_general_react_agent(temperature: float = 0.2):
    """
    General Agent용 ReAct 에이전트를 생성합니다.
    """
    llm = get_llm(
        temperature=temperature,
        model=settings.llm_model_name,
        max_tokens=settings.MAX_TOKENS,
    )

    system_prompt = """당신은 투자 교육 및 시장 정보 안내를 담당하는 General Agent입니다.

## 역할
- 투자 개념 설명, 지표 정의, 시장 상황 등을 명확히 안내합니다.
- 종목 관련 질문이 오면 반드시 `lookup_stock` → `get_stock_quote` 순으로 종목 정보와 주가를 확인합니다.
- 최신 소식이나 참고 자료가 필요하면 `web_search` 도구를 사용해 근거를 확보합니다.

## 도구 사용 규칙
1. 종목명이 등장하면 `lookup_stock`으로 종목 코드 확인 후 `get_stock_quote`으로 현재 가격을 조회하세요.
2. 뉴스, 시장 상황, 용어 정의가 필요한 경우에는 `web_search`를 활용하여 출처를 확보하세요.
3. 도구 호출 결과는 반드시 답변에 반영하고, 출처가 있는 경우 마지막에 `title - url` 형식으로 나열하세요.

## 최종 응답 형식
최종 응답은 반드시 JSON 문자열 형태로 출력하세요:
{
  "answer": "사용자에게 전달할 한국어 답변 (마크다운 허용)",
  "sources": [
    {"title": "자료 제목", "url": "https://..."}
  ],
  "confidence": "high|medium|low"
}
confidence는 도구 활용 여부와 답변 근거의 명확성에 따라 판단하세요.
"""

    tools = [
        lookup_stock,
        get_stock_quote,
        web_search,
    ]

    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_prompt,
    )


__all__ = ["create_general_react_agent"]
