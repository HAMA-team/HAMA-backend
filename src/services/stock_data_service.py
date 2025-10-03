"""주가 데이터 서비스 (FinanceDataReader)"""

from datetime import datetime, timedelta
from typing import Optional, List
import FinanceDataReader as fdr
import pandas as pd

from src.services.cache_manager import cache_manager
from src.config.settings import settings


class StockDataService:
    """
    주가 데이터 서비스

    - FinanceDataReader를 사용한 주가 데이터 조회
    - 캐싱 지원
    """

    def __init__(self):
        self.cache = cache_manager

    async def get_stock_price(
        self, stock_code: str, days: int = 30
    ) -> Optional[pd.DataFrame]:
        """
        주가 데이터 조회

        Args:
            stock_code: 종목 코드 (예: "005930")
            days: 조회 기간 (일)

        Returns:
            DataFrame: 주가 데이터 (Open, High, Low, Close, Volume)
        """
        # 캐시 키
        cache_key = f"stock_price:{stock_code}:{days}"

        # 캐시 확인
        cached = await self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ 캐시 히트: {cache_key}")
            return pd.DataFrame(cached)

        # FinanceDataReader 호출
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        try:
            df = fdr.DataReader(stock_code, start=start_date, end=end_date)

            if df is not None and len(df) > 0:
                # 캐싱 (60초 TTL)
                await self.cache.set(
                    cache_key, df.to_dict("records"), ttl=settings.CACHE_TTL_MARKET_DATA
                )
                print(f"✅ 주가 데이터 조회 성공: {stock_code}")
                return df
            else:
                print(f"⚠️ 주가 데이터 없음: {stock_code}")
                return None

        except Exception as e:
            print(f"❌ 주가 데이터 조회 실패: {stock_code}, {e}")
            return None

    async def get_stock_listing(self, market: str = "KOSPI") -> Optional[pd.DataFrame]:
        """
        종목 리스트 조회

        Args:
            market: 시장 (KOSPI, KOSDAQ, KONEX)

        Returns:
            DataFrame: 종목 리스트 (Code, Name, Market, etc.)
        """
        # 캐시 키
        cache_key = f"stock_listing:{market}"

        # 캐시 확인
        cached = await self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ 캐시 히트: {cache_key}")
            return pd.DataFrame(cached)

        # FinanceDataReader 호출
        try:
            df = fdr.StockListing(market)

            if df is not None and len(df) > 0:
                # 캐싱 (1일 TTL)
                await self.cache.set(cache_key, df.to_dict("records"), ttl=86400)
                print(f"✅ 종목 리스트 조회 성공: {market}, {len(df)}개")
                return df
            else:
                print(f"⚠️ 종목 리스트 없음: {market}")
                return None

        except Exception as e:
            print(f"❌ 종목 리스트 조회 실패: {market}, {e}")
            return None

    async def get_stock_by_name(self, name: str, market: str = "KOSPI") -> Optional[str]:
        """
        종목명으로 종목 코드 찾기

        Args:
            name: 종목명 (예: "삼성전자")
            market: 시장 (KOSPI, KOSDAQ, KONEX)

        Returns:
            str: 종목 코드 (예: "005930")
        """
        df = await self.get_stock_listing(market)

        if df is None:
            return None

        # 종목명으로 검색
        result = df[df["Name"].str.contains(name, na=False)]

        if len(result) == 0:
            print(f"⚠️ 종목을 찾을 수 없음: {name}")
            return None

        # 첫 번째 결과 반환
        stock_code = result.iloc[0]["Code"]
        print(f"✅ 종목 코드 찾기 성공: {name} -> {stock_code}")
        return stock_code

    async def calculate_returns(
        self, stock_code: str, days: int = 30
    ) -> Optional[pd.DataFrame]:
        """
        수익률 계산

        Args:
            stock_code: 종목 코드
            days: 조회 기간 (일)

        Returns:
            DataFrame: 원본 데이터 + 수익률 (Daily_Return, Cumulative_Return)
        """
        df = await self.get_stock_price(stock_code, days)

        if df is None or len(df) == 0:
            return None

        # 일일 수익률 계산
        df["Daily_Return"] = df["Close"].pct_change() * 100

        # 누적 수익률 계산
        df["Cumulative_Return"] = ((1 + df["Close"].pct_change()).cumprod() - 1) * 100

        return df

    async def get_multiple_stocks(
        self, stock_codes: List[str], days: int = 30
    ) -> dict[str, pd.DataFrame]:
        """
        여러 종목 데이터 조회

        Args:
            stock_codes: 종목 코드 리스트
            days: 조회 기간 (일)

        Returns:
            dict: {종목코드: DataFrame}
        """
        results = {}

        for stock_code in stock_codes:
            df = await self.get_stock_price(stock_code, days)
            if df is not None:
                results[stock_code] = df

        return results


# 싱글톤 인스턴스
stock_data_service = StockDataService()
