"""
한국은행(BOK) 경제통계 서비스

주요 지표:
- 기준금리
- CPI (소비자물가지수)
- 환율 (원/달러)
- GDP (국내총생산) - 분기별
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from src.config.settings import settings


class BOKService:
    """한국은행 경제통계시스템 API 서비스"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.BOK_API_KEY
        self.base_url = base_url or settings.BOK_BASE_URL

    def get_base_rate(
        self,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """
        기준금리 조회

        Args:
            start_date: 시작일 (YYYYMM)
            end_date: 종료일 (YYYYMM)

        Returns:
            기준금리 데이터 리스트
        """
        if not self.api_key:
            raise RuntimeError("BOK API key가 설정되지 않았습니다. 환경 변수 BOK_API_KEY를 확인하세요.")

        if not start_date:
            # 최근 1년
            end_date = datetime.now().strftime("%Y%m")
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m")

        # 통계표코드: 722Y001, 주기: M (월간), 통계항목코드: 0101000
        url = f"{self.base_url}/StatisticSearch/{self.api_key}/json/kr/1/100/722Y001/M/{start_date}/{end_date}/0101000"

        response = requests.get(url)
        data = response.json()

        if "StatisticSearch" in data:
            return data["StatisticSearch"]["row"]

        return []

    def get_cpi(
        self,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """
        소비자물가지수(CPI) 조회

        Args:
            start_date: 시작일 (YYYYMM)
            end_date: 종료일 (YYYYMM)

        Returns:
            CPI 데이터 리스트
        """
        if not self.api_key:
            raise RuntimeError("BOK API key가 설정되지 않았습니다. 환경 변수 BOK_API_KEY를 확인하세요.")

        if not start_date:
            # 최근 2년
            end_date = datetime.now().strftime("%Y%m")
            start_date = (datetime.now() - timedelta(days=730)).strftime("%Y%m")

        # 통계표코드: 901Y009, 주기: M (월간), 통계항목코드: 0 (전체)
        url = f"{self.base_url}/StatisticSearch/{self.api_key}/json/kr/1/100/901Y009/M/{start_date}/{end_date}/0"

        response = requests.get(url)
        data = response.json()

        if "StatisticSearch" in data:
            return data["StatisticSearch"]["row"]

        return []

    def get_exchange_rate(
        self,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """
        환율 (원/달러) 조회

        Args:
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)

        Returns:
            환율 데이터 리스트
        """
        if not self.api_key:
            raise RuntimeError("BOK API key가 설정되지 않았습니다. 환경 변수 BOK_API_KEY를 확인하세요.")

        if not start_date:
            # 최근 30일
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

        # 통계표코드: 731Y001, 주기: D (일간), 통계항목코드: 0000001 (매매기준율)
        url = f"{self.base_url}/StatisticSearch/{self.api_key}/json/kr/1/100/731Y001/D/{start_date}/{end_date}/0000001"

        response = requests.get(url)
        data = response.json()

        if "StatisticSearch" in data:
            return data["StatisticSearch"]["row"]

        return []

    def get_macro_indicators(self) -> Dict:
        """
        주요 거시경제 지표 종합 조회

        Returns:
            {
                "base_rate": float,  # 최근 기준금리
                "cpi": float,  # 최근 CPI
                "exchange_rate": float,  # 최근 환율
                "base_rate_trend": str,  # "상승" | "하락" | "유지"
                "cpi_yoy": float,  # CPI 전년동월대비 증감률
            }
        """
        # 최근 데이터 조회
        base_rate_data = self.get_base_rate()
        cpi_data = self.get_cpi()
        exchange_data = self.get_exchange_rate()

        result = {
            "base_rate": None,
            "cpi": None,
            "exchange_rate": None,
            "base_rate_trend": "유지",
            "cpi_yoy": None,
        }

        # 기준금리
        if base_rate_data and len(base_rate_data) >= 2:
            latest = float(base_rate_data[-1]["DATA_VALUE"])
            prev = float(base_rate_data[-2]["DATA_VALUE"])
            result["base_rate"] = latest

            if latest > prev:
                result["base_rate_trend"] = "상승"
            elif latest < prev:
                result["base_rate_trend"] = "하락"

        # CPI
        if cpi_data and len(cpi_data) >= 13:  # 전년동월대비 계산
            latest = float(cpi_data[-1]["DATA_VALUE"])
            year_ago = float(cpi_data[-13]["DATA_VALUE"])
            result["cpi"] = latest
            result["cpi_yoy"] = ((latest - year_ago) / year_ago) * 100

        # 환율
        if exchange_data:
            result["exchange_rate"] = float(exchange_data[-1]["DATA_VALUE"])

        return result


# Global instance
bok_service = BOKService()
