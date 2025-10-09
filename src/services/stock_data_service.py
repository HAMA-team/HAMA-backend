"""주가 데이터 서비스 (FinanceDataReader)"""

import asyncio
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

    async def get_market_index(
        self, index_code: str, days: int = 60, max_retries: int = 3
    ) -> Optional[pd.DataFrame]:
        """
        시장 지수 데이터 조회 (Rate Limit 방지 최적화)

        Args:
            index_code: 지수 코드 (예: "KS11" - KOSPI, "KQ11" - KOSDAQ)
            days: 조회 기간 (일)
            max_retries: 최대 재시도 횟수

        Returns:
            DataFrame: 지수 데이터 (Open, High, Low, Close, Volume)

        Raises:
            Exception: 모든 재시도 실패 시
        """
        # 캐시 키
        cache_key = f"market_index:{index_code}:{days}"

        # 캐시 확인 (1시간 TTL - Rate Limit 방지)
        cached = await self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ [Index] 캐시 히트: {cache_key}")
            return pd.DataFrame(cached)

        # Retry 로직 with exponential backoff
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        for attempt in range(max_retries):
            try:
                # FinanceDataReader 호출
                df = await asyncio.to_thread(
                    fdr.DataReader, index_code, start=start_date, end=end_date
                )

                if df is not None and len(df) > 0:
                    # 캐싱 (1시간 TTL - 지수는 실시간성 덜 중요)
                    await self.cache.set(
                        cache_key,
                        df.to_dict("records"),
                        ttl=settings.CACHE_TTL_MARKET_INDEX
                    )
                    print(f"✅ [Index] 지수 데이터 조회 성공: {index_code} ({len(df)}일)")
                    return df
                else:
                    print(f"⚠️ [Index] 지수 데이터 없음: {index_code}")
                    return None

            except Exception as e:
                error_msg = str(e)
                is_rate_limit = "429" in error_msg or "Too Many Requests" in error_msg

                if is_rate_limit and attempt < max_retries - 1:
                    # Exponential backoff: 1초 → 2초 → 4초
                    wait_time = 2 ** attempt
                    print(f"⚠️ [Index] Rate Limit 감지 ({attempt + 1}/{max_retries}), {wait_time}초 대기...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    # 최종 실패 또는 Rate Limit 아닌 에러
                    error_detail = f"{index_code}, attempt {attempt + 1}/{max_retries}, {error_msg}"
                    print(f"❌ [Index] 지수 데이터 조회 실패: {error_detail}")

                    if attempt == max_retries - 1:
                        # 모든 재시도 실패 - 에러 발생
                        raise Exception(
                            f"시장 지수 데이터 조회 실패 (Rate Limit): {index_code}. "
                            f"잠시 후 다시 시도해주세요."
                        )

        return None


# 싱글톤 인스턴스
stock_data_service = StockDataService()
