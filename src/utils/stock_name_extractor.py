"""
종목명 추출 유틸리티

GPT-5 LLM을 사용하여 사용자 쿼리에서 종목명을 정확하게 추출합니다.
"""
import logging
import re
from typing import List

from src.utils.llm_factory import get_openai_llm
from src.utils.json_parser import safe_json_parse

logger = logging.getLogger(__name__)


async def extract_stock_names_from_query(query: str) -> List[str]:
    """
    사용자 쿼리에서 종목명을 추출합니다 (GPT-5 기반).

    Args:
        query: 사용자 쿼리 (예: "sk 하이닉스 전망 분석해줘", "삼성전자와 SK하이닉스 비교해줘")

    Returns:
        종목명 리스트 (예: ["SK하이닉스"], ["삼성전자", "SK하이닉스"])
        종목명이 없으면 빈 리스트 반환

    Examples:
        >>> await extract_stock_names_from_query("sk 하이닉스 전망 분석해줘")
        ["SK하이닉스"]

        >>> await extract_stock_names_from_query("삼성전자와 sk하이닉스 비교해줘")
        ["삼성전자", "SK하이닉스"]

        >>> await extract_stock_names_from_query("코스피 지수 어때?")
        []
    """
    # 1. 6자리 종목 코드가 직접 입력된 경우 (빠른 패턴 매칭)
    code_pattern = re.compile(r"\b(\d{6})\b")
    codes = code_pattern.findall(query)
    if codes:
        logger.info(f"✅ [StockExtractor] 종목 코드 발견: {codes}")
        return codes

    # 2. GPT-5 LLM으로 종목명 추출
    try:
        llm = get_openai_llm(temperature=0, max_tokens=500, model="gpt-5")

        prompt = f"""당신은 한국 주식 시장 전문가입니다. 사용자 쿼리에서 **종목명만** 추출하세요.

사용자 쿼리: "{query}"

**규칙:**
1. 종목명만 추출하세요 (예: "SK하이닉스", "삼성전자", "네이버")
2. 종목명이 아닌 단어는 제외하세요 (예: "전망", "분석", "매수", "어때" 등)
3. 띄어쓰기를 정규화하세요 (예: "sk 하이닉스" → "SK하이닉스")
4. 한국 상장 기업명만 추출하세요
5. 종목명이 없으면 빈 리스트를 반환하세요

**예시:**
- "sk 하이닉스 전망 분석해줘" → ["SK하이닉스"]
- "삼성전자와 SK하이닉스 비교해줘" → ["삼성전자", "SK하이닉스"]
- "코스피 지수 어때?" → []
- "삼성 전자 매수해도 될까?" → ["삼성전자"]

JSON 형식으로만 답변하세요:
{{
  "stock_names": ["종목명1", "종목명2", ...]
}}
"""

        response = await llm.ainvoke(prompt)
        result = safe_json_parse(response.content, "StockNameExtractor")

        if isinstance(result, dict) and "stock_names" in result:
            stock_names = result["stock_names"]
            if isinstance(stock_names, list):
                # 유효성 검증: 빈 문자열 제거, 중복 제거
                stock_names = [name.strip() for name in stock_names if name and name.strip()]
                stock_names = list(dict.fromkeys(stock_names))  # 중복 제거 (순서 유지)

                if stock_names:
                    logger.info(f"✅ [StockExtractor] LLM 추출 성공: {stock_names}")
                else:
                    logger.info(f"ℹ️ [StockExtractor] 종목명이 없음: {query}")

                return stock_names

        logger.warning(f"⚠️ [StockExtractor] LLM 응답 형식 오류: {result}")
        return []

    except Exception as e:
        logger.error(f"❌ [StockExtractor] LLM 추출 실패: {e}")
        return []
