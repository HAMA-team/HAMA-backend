"""
Research Agent 도구 정의

LangGraph ReAct 패턴에서 사용할 도구들
"""
import logging
from typing import Optional

from langchain_core.tools import tool

from src.services.stock_data_service import stock_data_service
from src.services.dart_service import dart_service

logger = logging.getLogger(__name__)


@tool
async def get_stock_price(stock_code: str, days: int = 1) -> dict:
    """
    주가 데이터 조회

    Args:
        stock_code: 종목 코드 (예: "005930")
        days: 조회할 일수 (기본 1일, 최근 가격만)

    Returns:
        주가 데이터 (현재가, 거래량, 등락률 등)

    Examples:
        - 현재가만: get_stock_price("005930", days=1)
        - 최근 30일: get_stock_price("005930", days=30)
    """
    logger.info(f"🔧 [Tool/get_stock_price] {stock_code}, days={days}")

    try:
        price_df = await stock_data_service.get_stock_price(stock_code, days=days)

        if price_df is None or len(price_df) == 0:
            return {
                "success": False,
                "error": f"주가 데이터 조회 실패: {stock_code}"
            }

        # 최신 데이터
        latest = price_df.iloc[-1]

        # 변화율 계산 (days > 1인 경우)
        change_pct = None
        if len(price_df) > 1:
            first_close = price_df.iloc[0]["Close"]
            change_pct = ((latest["Close"] - first_close) / first_close) * 100

        result = {
            "success": True,
            "stock_code": stock_code,
            "days": len(price_df),
            "current_price": float(latest["Close"]),
            "volume": int(latest["Volume"]),
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
            "change_pct": round(change_pct, 2) if change_pct else None,
            "source": "FinanceDataReader"
        }

        logger.info(f"✅ [Tool/get_stock_price] 조회 완료: {result['current_price']:,.0f}원")
        return result

    except Exception as e:
        logger.error(f"❌ [Tool/get_stock_price] 에러: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool
async def get_basic_ratios(stock_code: str, metrics: Optional[list[str]] = None) -> dict:
    """
    기본 재무 비율 조회 (PER, PBR, ROE 등)

    Args:
        stock_code: 종목 코드
        metrics: 조회할 지표 리스트 (예: ["PER", "PBR", "ROE"])
                 None이면 모든 기본 지표 반환

    Returns:
        재무 비율 데이터

    Examples:
        - PER만: get_basic_ratios("005930", metrics=["PER"])
        - 전체: get_basic_ratios("005930")
    """
    logger.info(f"🔧 [Tool/get_basic_ratios] {stock_code}, metrics={metrics}")

    try:
        # 1. 고유번호 조회
        corp_code = await dart_service.search_corp_code_by_stock_code(stock_code)
        if not corp_code:
            return {
                "success": False,
                "error": f"DART 고유번호 찾기 실패: {stock_code}"
            }

        # 2. 재무제표 조회 (최근 1년)
        financial_data = await dart_service.get_financial_statement(
            corp_code, bsns_year="2023"
        )

        if not financial_data:
            return {
                "success": False,
                "error": "재무제표 조회 실패"
            }

        # 3. 기본 비율 계산 (간단한 계산, 실제로는 더 정교해야 함)
        # TODO: 실제 비율 계산 로직 구현 (현재는 Mock)
        all_ratios = {
            "PER": 8.5,  # Mock 데이터
            "PBR": 1.2,
            "ROE": 15.3,
            "debt_ratio": 45.2,
            "current_ratio": 1.8
        }

        # 필터링
        if metrics:
            filtered_ratios = {k: v for k, v in all_ratios.items() if k in metrics}
        else:
            filtered_ratios = all_ratios

        result = {
            "success": True,
            "stock_code": stock_code,
            "corp_code": corp_code,
            "ratios": filtered_ratios,
            "source": "DART"
        }

        logger.info(f"✅ [Tool/get_basic_ratios] 조회 완료: {list(filtered_ratios.keys())}")
        return result

    except Exception as e:
        logger.error(f"❌ [Tool/get_basic_ratios] 에러: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool
async def get_financial_statement(stock_code: str, years: int = 3) -> dict:
    """
    상세 재무제표 조회 (손익계산서, 재무상태표, 현금흐름표)

    Args:
        stock_code: 종목 코드
        years: 조회할 년수 (기본 3년)

    Returns:
        재무제표 전체 데이터

    Examples:
        - 최근 3년: get_financial_statement("005930", years=3)
        - 최근 5년: get_financial_statement("005930", years=5)
    """
    logger.info(f"🔧 [Tool/get_financial_statement] {stock_code}, years={years}")

    try:
        # 1. 고유번호 조회
        corp_code = await dart_service.search_corp_code_by_stock_code(stock_code)
        if not corp_code:
            return {
                "success": False,
                "error": f"DART 고유번호 찾기 실패: {stock_code}"
            }

        # 2. 재무제표 조회 (현재는 1년치만 구현됨, 추후 years 파라미터 적용)
        financial_data = await dart_service.get_financial_statement(
            corp_code, bsns_year="2023"
        )

        if not financial_data:
            return {
                "success": False,
                "error": "재무제표 조회 실패"
            }

        result = {
            "success": True,
            "stock_code": stock_code,
            "corp_code": corp_code,
            "years": years,
            "statements": financial_data,
            "source": "DART"
        }

        logger.info(f"✅ [Tool/get_financial_statement] 조회 완료")
        return result

    except Exception as e:
        logger.error(f"❌ [Tool/get_financial_statement] 에러: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool
async def get_company_info(stock_code: str) -> dict:
    """
    기업 기본 정보 조회 (기업명, 업종, 대표자 등)

    Args:
        stock_code: 종목 코드

    Returns:
        기업 정보
    """
    logger.info(f"🔧 [Tool/get_company_info] {stock_code}")

    try:
        # 1. 고유번호 조회
        corp_code = await dart_service.search_corp_code_by_stock_code(stock_code)
        if not corp_code:
            return {
                "success": False,
                "error": f"DART 고유번호 찾기 실패: {stock_code}"
            }

        # 2. 기업 정보 조회
        company_info = await dart_service.get_company_info(corp_code)

        if not company_info:
            return {
                "success": False,
                "error": "기업 정보 조회 실패"
            }

        result = {
            "success": True,
            "stock_code": stock_code,
            "corp_code": corp_code,
            "info": company_info,
            "source": "DART"
        }

        logger.info(f"✅ [Tool/get_company_info] 조회 완료")
        return result

    except Exception as e:
        logger.error(f"❌ [Tool/get_company_info] 에러: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool
async def calculate_dcf_valuation(stock_code: str) -> dict:
    """
    DCF 밸류에이션 계산 (전문가용)

    현금흐름 할인 모델로 적정 주가 계산

    Args:
        stock_code: 종목 코드

    Returns:
        DCF 계산 결과 (적정가, WACC, FCF 추정 등)

    Note:
        - 계산 시간이 오래 걸릴 수 있음
        - 전문가 수준 분석에만 사용 권장
    """
    logger.info(f"🔧 [Tool/calculate_dcf_valuation] {stock_code}")

    try:
        # TODO: 실제 DCF 계산 로직 구현
        # 현재는 Mock 데이터

        result = {
            "success": True,
            "stock_code": stock_code,
            "intrinsic_value": 85000,  # Mock
            "current_price": 75000,
            "upside": 13.3,
            "wacc": 8.0,
            "terminal_growth_rate": 3.0,
            "fcf_projection": [12000, 13500, 15000, 16500, 18000],
            "sensitivity_analysis": {
                "wacc_range": [7.0, 8.0, 9.0],
                "value_range": [92000, 85000, 78000]
            },
            "source": "DCF Model"
        }

        logger.info(f"✅ [Tool/calculate_dcf_valuation] 계산 완료: 적정가 {result['intrinsic_value']:,}원")
        return result

    except Exception as e:
        logger.error(f"❌ [Tool/calculate_dcf_valuation] 에러: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@tool
async def get_sector_comparison(stock_code: str, sector: str) -> dict:
    """
    업종 평균과 비교 분석

    Args:
        stock_code: 종목 코드
        sector: 업종명 (예: "반도체", "배터리")

    Returns:
        업종 평균 대비 비교 데이터
    """
    logger.info(f"🔧 [Tool/get_sector_comparison] {stock_code}, sector={sector}")

    try:
        # TODO: 실제 업종 비교 로직 구현
        # 현재는 Mock 데이터

        result = {
            "success": True,
            "stock_code": stock_code,
            "sector": sector,
            "stock_ratios": {
                "PER": 8.5,
                "PBR": 1.2,
                "ROE": 15.3
            },
            "sector_avg": {
                "PER": 12.0,
                "PBR": 1.5,
                "ROE": 12.0
            },
            "comparison": {
                "PER": "저평가 (-29%)",
                "PBR": "저평가 (-20%)",
                "ROE": "우수 (+27%)"
            },
            "source": "Sector Analysis"
        }

        logger.info(f"✅ [Tool/get_sector_comparison] 비교 완료")
        return result

    except Exception as e:
        logger.error(f"❌ [Tool/get_sector_comparison] 에러: {e}")
        return {
            "success": False,
            "error": str(e)
        }
