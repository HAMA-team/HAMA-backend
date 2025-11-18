"""
Research SubGraph 전용 Tools

Research SubGraph 노드들이 사용하는 서비스 호출을 Tool로 래핑하여
LangGraph 이벤트 추적이 가능하도록 합니다.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from langchain_core.tools import tool
from pydantic.v1 import BaseModel, Field

logger = logging.getLogger(__name__)


# ==================== Input Schemas ====================

class StockPriceInput(BaseModel):
    """주가 데이터 조회 입력"""
    stock_code: str = Field(description="6자리 종목 코드")
    days: int = Field(default=30, description="조회 기간 (일)")


class StockByNameInput(BaseModel):
    """종목명으로 코드 검색 입력"""
    stock_name: str = Field(description="종목명")
    market: str = Field(default="KOSPI", description="시장 (KOSPI/KOSDAQ/KONEX)")


class CorpCodeInput(BaseModel):
    """기업 고유번호 검색 입력"""
    stock_code: str = Field(description="6자리 종목 코드")


class FinancialStatementInput(BaseModel):
    """재무제표 조회 입력"""
    corp_code: str = Field(description="DART 기업 고유번호")
    bsns_year: str = Field(description="사업연도 (YYYY 형식)")


class CompanyInfoInput(BaseModel):
    """기업 정보 조회 입력"""
    corp_code: str = Field(description="DART 기업 고유번호")


class FundamentalDataInput(BaseModel):
    """기본 재무 데이터 조회 입력"""
    stock_code: str = Field(description="6자리 종목 코드")


class MarketCapDataInput(BaseModel):
    """시가총액 데이터 조회 입력"""
    stock_code: str = Field(description="6자리 종목 코드")


class MarketIndexInput(BaseModel):
    """시장 지수 조회 입력"""
    index_name: str = Field(default="KOSPI", description="지수명 (KOSPI/KOSDAQ)")
    days: int = Field(default=30, description="조회 기간 (일)")


class InvestorFlowInput(BaseModel):
    """투자자 별 매매 흐름 조회 입력"""
    stock_code: str = Field(description="6자리 종목 코드")


# ==================== Stock Data Tools ====================

@tool(args_schema=StockPriceInput)
async def get_stock_price_tool(stock_code: str, days: int = 30) -> Dict[str, Any]:
    """
    주가 데이터를 조회합니다 (pykrx/FinanceDataReader).

    Args:
        stock_code: 6자리 종목 코드
        days: 조회 기간 (일)

    Returns:
        dict: {
            "stock_code": str,
            "days": int,
            "prices": List[dict],  # [{date, Open, High, Low, Close, Volume}, ...]
            "latest_close": float,
            "latest_volume": int,
            "source": str
        }
    """
    try:
        from src.services.stock_data_service import stock_data_service

        logger.info(f"📊 [Tool] 주가 데이터 조회: {stock_code} (최근 {days}일)")
        price_df = await stock_data_service.get_stock_price(stock_code, days=days)

        if price_df is None or len(price_df) == 0:
            raise RuntimeError(f"주가 데이터 조회 실패: {stock_code}")

        return {
            "stock_code": stock_code,
            "days": len(price_df),
            "prices": price_df.reset_index().to_dict("records"),
            "latest_close": float(price_df.iloc[-1]["Close"]),
            "latest_volume": int(price_df.iloc[-1]["Volume"]),
            "source": "pykrx/FinanceDataReader",
        }
    except Exception as e:
        logger.error(f"❌ [Tool] 주가 조회 실패: {stock_code}, {e}")
        return {"error": str(e), "stock_code": stock_code}


@tool(args_schema=StockByNameInput)
async def get_stock_by_name_tool(stock_name: str, market: str = "KOSPI") -> Optional[str]:
    """
    종목명으로 종목 코드를 검색합니다.

    Args:
        stock_name: 종목명 (예: "삼성전자")
        market: 시장 (KOSPI/KOSDAQ/KONEX)

    Returns:
        str: 6자리 종목 코드 또는 None
    """
    try:
        from src.services.stock_data_service import stock_data_service

        logger.info(f"🔍 [Tool] 종목 검색: {stock_name} ({market})")
        code = await stock_data_service.get_stock_by_name(stock_name, market=market)
        return code
    except Exception as e:
        logger.error(f"❌ [Tool] 종목 검색 실패: {stock_name}, {e}")
        return None


@tool(args_schema=FundamentalDataInput)
async def get_fundamental_data_tool(stock_code: str) -> Dict[str, Any]:
    """
    기본 재무 데이터를 조회합니다 (PER, PBR, EPS, BPS 등).

    Args:
        stock_code: 6자리 종목 코드

    Returns:
        dict: {
            "PER": float,
            "PBR": float,
            "EPS": float,
            "BPS": float,
            ...
        }
    """
    try:
        from src.services.stock_data_service import stock_data_service

        logger.info(f"📈 [Tool] 기본 재무 데이터 조회: {stock_code}")
        data = await stock_data_service.get_fundamental_data(stock_code)
        return data or {}
    except Exception as e:
        logger.error(f"❌ [Tool] 기본 재무 데이터 조회 실패: {stock_code}, {e}")
        return {"error": str(e)}


@tool(args_schema=MarketCapDataInput)
async def get_market_cap_data_tool(stock_code: str) -> Dict[str, Any]:
    """
    시가총액 데이터를 조회합니다.

    Args:
        stock_code: 6자리 종목 코드

    Returns:
        dict: 시가총액 관련 데이터
    """
    try:
        from src.services.stock_data_service import stock_data_service

        logger.info(f"💰 [Tool] 시가총액 조회: {stock_code}")
        data = await stock_data_service.get_market_cap_data(stock_code)
        return data or {}
    except Exception as e:
        logger.error(f"❌ [Tool] 시가총액 조회 실패: {stock_code}, {e}")
        return {"error": str(e)}


@tool(args_schema=MarketIndexInput)
async def get_market_index_tool(index_name: str = "KOSPI", days: int = 30) -> Dict[str, Any]:
    """
    시장 지수 데이터를 조회합니다.

    Args:
        index_name: 지수명 (KOSPI/KOSDAQ)
        days: 조회 기간 (일)

    Returns:
        dict: 시장 지수 데이터
    """
    try:
        from src.services.stock_data_service import stock_data_service

        logger.info(f"📊 [Tool] 시장 지수 조회: {index_name} (최근 {days}일)")
        market_df = await stock_data_service.get_market_index(index_name, days=days)

        if market_df is None or len(market_df) == 0:
            raise RuntimeError(f"시장 지수 조회 실패: {index_name}")

        return {
            "index_name": index_name,
            "days": len(market_df),
            "data": market_df.reset_index().to_dict("records"),
            "latest_close": float(market_df.iloc[-1]["Close"]),
        }
    except Exception as e:
        logger.error(f"❌ [Tool] 시장 지수 조회 실패: {index_name}, {e}")
        return {"error": str(e)}


@tool(args_schema=InvestorFlowInput)
async def get_investor_flow_tool(stock_code: str) -> Dict[str, Any]:
    """KIS 투자자별 매매 흐름 데이터를 반환합니다."""
    try:
        from src.services.stock_data_service import stock_data_service

        logger.info(f"📡 [Tool] 투자자 흐름 조회: {stock_code}")
        data = await stock_data_service.get_investor_flow(stock_code)
        return data or {"stock_code": stock_code, "source": "KIS", "message": "자료 없음"}

    except Exception as e:
        logger.error(f"❌ [Tool] 투자자 흐름 조회 실패: {stock_code}, {e}")
        return {"error": str(e), "stock_code": stock_code}


# ==================== DART Tools ====================

@tool(args_schema=CorpCodeInput)
async def search_corp_code_tool(stock_code: str) -> Optional[str]:
    """
    종목 코드로 DART 기업 고유번호를 검색합니다.

    Args:
        stock_code: 6자리 종목 코드

    Returns:
        str: DART 기업 고유번호 (8자리) 또는 None
    """
    try:
        from src.services.dart_service import dart_service

        logger.info(f"🔍 [Tool] DART 기업 고유번호 검색: {stock_code}")
        corp_code = await dart_service.search_corp_code_by_stock_code(stock_code)
        return corp_code
    except Exception as e:
        logger.error(f"❌ [Tool] DART 기업 고유번호 검색 실패: {stock_code}, {e}")
        return None


@tool(args_schema=FinancialStatementInput)
async def get_financial_statement_tool(corp_code: str, bsns_year: str) -> Dict[str, Any]:
    """
    재무제표를 조회합니다 (DART API).

    Args:
        corp_code: DART 기업 고유번호
        bsns_year: 사업연도 (YYYY 형식)

    Returns:
        dict: 재무제표 데이터
    """
    try:
        from src.services.dart_service import dart_service

        logger.info(f"📋 [Tool] 재무제표 조회: {corp_code} ({bsns_year}년)")
        data = await dart_service.get_financial_statement(corp_code, bsns_year=bsns_year)
        return data or {}
    except Exception as e:
        logger.error(f"❌ [Tool] 재무제표 조회 실패: {corp_code}, {e}")
        return {"error": str(e)}


@tool(args_schema=CompanyInfoInput)
async def get_company_info_tool(corp_code: str) -> Dict[str, Any]:
    """
    기업 정보를 조회합니다 (DART API).

    Args:
        corp_code: DART 기업 고유번호

    Returns:
        dict: 기업 정보 (회사명, 업종, CEO 등)
    """
    try:
        from src.services.dart_service import dart_service

        logger.info(f"🏢 [Tool] 기업 정보 조회: {corp_code}")
        data = await dart_service.get_company_info(corp_code)
        return data or {}
    except Exception as e:
        logger.error(f"❌ [Tool] 기업 정보 조회 실패: {corp_code}, {e}")
        return {"error": str(e)}


# ==================== Macro Data Tools ====================

@tool
async def get_macro_summary_tool() -> Dict[str, Any]:
    """
    거시경제 데이터 요약을 조회합니다 (BOK API).

    Returns:
        dict: {
            "base_rate": float,           # 기준금리
            "base_rate_trend": str,       # 추세 (상승/하락/유지)
            "cpi": float,                 # 소비자물가지수
            "cpi_yoy": float,             # 전년대비 증감률
            "exchange_rate": float,       # 원/달러 환율
            ...
        }
    """
    try:
        from src.services.macro_data_service import macro_data_service

        logger.info("🌍 [Tool] 거시경제 데이터 조회")
        data = macro_data_service.macro_summary()

        # 데이터가 비어있으면 새로고침
        if not data.get("base_rate"):
            logger.info("📡 [Tool] 거시경제 데이터 새로고침")
            await macro_data_service.refresh_all()
            data = macro_data_service.macro_summary()

        return data
    except Exception as e:
        logger.error(f"❌ [Tool] 거시경제 데이터 조회 실패: {e}")
        return {"error": str(e)}


# ==================== Tool 리스트 ====================

def get_research_tools() -> List:
    """Research SubGraph에서 사용할 모든 tools를 반환합니다."""
    return [
        # Stock Data Tools
        get_stock_price_tool,
        get_stock_by_name_tool,
        get_fundamental_data_tool,
        get_market_cap_data_tool,
        get_market_index_tool,
        get_investor_flow_tool,
        # DART Tools
        search_corp_code_tool,
        get_financial_statement_tool,
        get_company_info_tool,
        # Macro Tools
        get_macro_summary_tool,
    ]


__all__ = [
    "get_research_tools",
    "get_stock_price_tool",
    "get_stock_by_name_tool",
    "get_fundamental_data_tool",
    "get_market_cap_data_tool",
    "get_market_index_tool",
    "get_investor_flow_tool",
    "search_corp_code_tool",
    "get_financial_statement_tool",
    "get_company_info_tool",
    "get_macro_summary_tool",
]
