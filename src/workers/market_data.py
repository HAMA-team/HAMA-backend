"""
Market Data Worker: 단순 시장 데이터 조회

LangGraph 서브그래프 없이 빠르게 시장 데이터를 조회합니다.

지원 기능:
- 주가 현재가 조회
- 지수 (코스피/코스닥) 조회
"""
import logging
from typing import Any, Dict, Optional

from src.constants.kis_constants import INDEX_CODES
from src.services.kis_service import kis_service

logger = logging.getLogger(__name__)


async def get_stock_price(stock_code: str, stock_name: Optional[str] = None) -> Dict[str, Any]:
    """
    주식 현재가 조회 (Worker)

    Args:
        stock_code: 종목 코드 (예: "005930")
        stock_name: 종목명 (예: "삼성전자") - 선택적

    Returns:
        {
            "worker": "stock_price",
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "current_price": 72000,
            "change_price": 1000,
            "change_rate": 1.41,
            "open_price": 71000,
            "high_price": 72500,
            "low_price": 70500,
            "volume": 15234567,
            "message": "삼성전자의 현재가는 72,000원입니다. 전일 대비 +1,000원(+1.41%) 상승했습니다."
        }
    """
    logger.info(f"⚡ [Worker:StockPrice] 주가 조회: {stock_code} ({stock_name or 'Unknown'})")

    try:
        # KIS Service로 실시간 시세 조회
        price_data = await kis_service.get_stock_price(stock_code)

        # 응답 포맷팅
        current_price = price_data.get("current_price", 0)
        change_price = price_data.get("change_price", 0)
        change_rate = price_data.get("change_rate", 0.0)

        # 종목명 우선순위: KIS API 응답 > 파라미터로 받은 stock_name > stock_code
        # 빈 문자열 처리를 위해 or 연산자 사용
        stock_name_result = price_data.get("stock_name") or stock_name or stock_code

        # 등락 방향 표시
        if change_price > 0:
            change_symbol = "+"
            change_direction = "상승"
        elif change_price < 0:
            change_symbol = ""
            change_direction = "하락"
        else:
            change_symbol = ""
            change_direction = "보합"

        # 사용자 친화적 메시지 생성 (시가, 고가, 저가 포함)
        open_price = price_data.get("open_price", 0)
        high_price = price_data.get("high_price", 0)
        low_price = price_data.get("low_price", 0)
        volume = price_data.get("volume", 0)

        message = (
            f"{stock_name_result}의 현재가는 {current_price:,}원입니다. "
            f"전일 대비 {change_symbol}{change_price:,}원({change_symbol}{change_rate:.2f}%) {change_direction}했습니다.\n"
            f"시가 {open_price:,}원, 고가 {high_price:,}원, 저가 {low_price:,}원, 거래량 {volume:,}주"
        )

        return {
            "worker": "stock_price",
            "stock_code": stock_code,
            "stock_name": stock_name_result,
            "current_price": current_price,
            "change_price": change_price,
            "change_rate": change_rate,
            "open_price": open_price,
            "high_price": high_price,
            "low_price": low_price,
            "volume": volume,
            "message": message,
        }

    except Exception as e:
        logger.error(f"❌ [Worker:StockPrice] 주가 조회 실패: {e}")
        return {
            "worker": "stock_price",
            "error": str(e),
            "message": f"죄송합니다. {stock_name or stock_code}의 주가 정보를 가져오는 중 오류가 발생했습니다.",
        }


async def get_index_price(index_name: str) -> Dict[str, Any]:
    """
    지수 현재가 조회 (Worker)

    Args:
        index_name: 지수명 (예: "코스피", "KOSPI", "코스닥", "KOSDAQ")

    Returns:
        {
            "worker": "index_price",
            "index_name": "코스피",
            "index_code": "0001",
            "current_price": 2650.5,
            "change": 10.5,
            "change_rate": 0.42,
            "volume": 500000000,
            "message": "코스피 지수는 2,650.5입니다. 전일 대비 +10.5(+0.42%) 상승했습니다."
        }
    """
    logger.info(f"⚡ [Worker:IndexPrice] 지수 조회: {index_name}")

    # 지수명 정규화
    index_name_upper = index_name.upper().strip()

    # 한글 → 영문 매핑
    if "코스피" in index_name:
        if "200" in index_name:
            index_name_upper = "KOSPI200"
        else:
            index_name_upper = "KOSPI"
    elif "코스닥" in index_name:
        index_name_upper = "KOSDAQ"

    # 지수 코드 매핑
    index_code = INDEX_CODES.get(index_name_upper)

    if not index_code:
        logger.warning(f"⚠️ [Worker:IndexPrice] 지원하지 않는 지수: {index_name}")
        return {
            "worker": "index_price",
            "error": f"지원하지 않는 지수: {index_name}",
            "message": f"죄송합니다. '{index_name}' 지수는 지원하지 않습니다. 코스피, 코스닥, 코스피200 중 하나를 선택해주세요.",
        }

    try:
        # KIS Service로 실시간 지수 조회
        index_data = await kis_service.get_index_price(index_code)

        if not index_data:
            return {
                "worker": "index_price",
                "error": "지수 데이터 없음",
                "message": f"죄송합니다. {index_name_upper} 지수 정보를 가져올 수 없습니다.",
            }

        # 응답 포맷팅
        current_price = index_data.get("current_price", 0.0)
        change = index_data.get("change", 0.0)
        change_rate = index_data.get("change_rate", 0.0)

        # 등락 방향 표시
        if change > 0:
            change_symbol = "+"
            change_direction = "상승"
        elif change < 0:
            change_symbol = ""
            change_direction = "하락"
        else:
            change_symbol = ""
            change_direction = "보합"

        # 사용자 친화적 메시지 생성
        message = (
            f"{index_name_upper} 지수는 {current_price:,.2f}입니다. "
            f"전일 대비 {change_symbol}{change:,.2f}({change_symbol}{change_rate:.2f}%) {change_direction}했습니다."
        )

        return {
            "worker": "index_price",
            "index_name": index_name_upper,
            "index_code": index_code,
            "current_price": current_price,
            "change": change,
            "change_rate": change_rate,
            "volume": index_data.get("volume", 0),
            "message": message,
        }

    except Exception as e:
        logger.error(f"❌ [Worker:IndexPrice] 지수 조회 실패: {e}")
        return {
            "worker": "index_price",
            "error": str(e),
            "message": f"죄송합니다. {index_name_upper} 지수 정보를 가져오는 중 오류가 발생했습니다.",
        }
