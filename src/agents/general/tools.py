"""
General Agent 전용 LangChain 도구 정의
"""
import logging
import re
from typing import Optional

from langchain_core.tools import tool

from src.services.search_service import web_search_service
from src.services.stock_data_service import stock_data_service
from src.utils.stock_name_extractor import extract_stock_names_from_query

logger = logging.getLogger(__name__)


def _normalize_stock_query(value: str) -> str:
    return value.strip().upper()


def _is_stock_code(value: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", value.strip()))


@tool
async def lookup_stock(query: str) -> dict:
    """
    종목 코드/이름 조회 도구 (LLM 기반 종목명 추출 지원).

    Args:
        query: 종목명 또는 6자리 종목 코드 (예: "SK하이닉스", "삼성전자", "005930")

    Returns:
        {
            "success": bool,
            "stock_code": Optional[str],
            "stock_name": Optional[str],
            "market": Optional[str],
            "message": str
        }
    """
    # 1. LLM 기반 종목명 추출 (GPT-5 사용)
    stock_names = await extract_stock_names_from_query(query)

    if not stock_names:
        return {
            "success": False,
            "stock_code": None,
            "stock_name": None,
            "market": None,
            "message": f"'{query}'에서 종목명을 찾을 수 없습니다.",
        }

    # 2. 첫 번째 종목명으로 검색 (향후 다중 종목 지원 가능)
    stock_name = stock_names[0]

    # 6자리 코드인 경우 그대로 사용
    if _is_stock_code(stock_name):
        return {
            "success": True,
            "stock_code": stock_name,
            "stock_name": None,
            "market": None,
            "message": "입력값을 종목 코드로 인식했습니다.",
        }

    # 3. 종목명으로 검색 (모든 시장에서 검색)
    markets = ["KOSPI", "KOSDAQ", "KONEX"]
    for market in markets:
        try:
            code = await stock_data_service.get_stock_by_name(stock_name, market=market)
        except Exception as exc:  # pragma: no cover - 외부 API 실패
            logger.debug("⚠️ [lookup_stock] 종목 검색 실패 (%s/%s): %s", stock_name, market, exc)
            continue

        if code:
            return {
                "success": True,
                "stock_code": code,
                "stock_name": stock_name,
                "market": market,
                "message": f"{market} 시장에서 '{stock_name}'을(를) 찾았습니다.",
            }

    return {
        "success": False,
        "stock_code": None,
        "stock_name": None,
        "market": None,
        "message": f"'{stock_name}'에 해당하는 종목을 찾지 못했습니다.",
    }


@tool
async def get_stock_quote(stock_code: str) -> dict:
    """
    최신 주가/거래 데이터 조회 도구.

    Args:
        stock_code: 6자리 종목 코드

    Returns:
        {
            "success": bool,
            "stock_code": str,
            "latest_close": float,
            "change": float,
            "change_pct": float,
            "open": float,
            "high": float,
            "low": float,
            "volume": int
        }
    """
    normalized = _normalize_stock_query(stock_code)
    if not _is_stock_code(normalized):
        return {
            "success": False,
            "error": "유효한 6자리 종목 코드가 아닙니다.",
        }

    try:
        price_df = await stock_data_service.get_stock_price(normalized, days=2)
    except Exception as exc:  # pragma: no cover - 외부 API 실패
        logger.error("❌ [get_stock_quote] 주가 조회 실패: %s", exc)
        return {
            "success": False,
            "error": str(exc),
        }

    if price_df is None or len(price_df) == 0:
        return {
            "success": False,
            "error": "주가 데이터를 찾을 수 없습니다.",
        }

    latest = price_df.iloc[-1]
    prev = price_df.iloc[-2] if len(price_df) > 1 else None

    latest_close = float(latest.get("Close", 0.0))
    change = None
    change_pct = None
    if prev is not None:
        prev_close = float(prev.get("Close", 0.0))
        change = latest_close - prev_close
        if prev_close:
            change_pct = (change / prev_close) * 100

    return {
        "success": True,
        "stock_code": normalized,
        "latest_close": latest_close,
        "open": float(latest.get("Open", 0.0)),
        "high": float(latest.get("High", 0.0)),
        "low": float(latest.get("Low", 0.0)),
        "volume": int(latest.get("Volume", 0)),
        "change": change,
        "change_pct": change_pct,
    }


@tool
async def web_search(query: str, max_results: int = 5) -> dict:
    """
    DuckDuckGo 기반 웹 검색 도구.

    Args:
        query: 검색어
        max_results: 최대 결과 수 (기본 5)

    Returns:
        {
            "success": bool,
            "results": [
                {"title": str, "url": str, "snippet": str, "rank": int}
            ]
        }
    """
    if not query.strip():
        return {
            "success": False,
            "error": "검색어가 비어 있습니다.",
        }

    results = await web_search_service.search(query, max_results=max_results, force=True)
    return {
        "success": True,
        "results": results,
    }


__all__ = [
    "lookup_stock",
    "get_stock_quote",
    "web_search",
]
