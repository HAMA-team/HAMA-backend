"""주가 데이터 서비스 (DB Repository + 외부 API + Realtime Cache)"""

import asyncio
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
from pykrx import stock as krx_stock
import FinanceDataReader as fdr

from src.config.settings import settings
from src.repositories import (
    stock_price_repository,
    stock_repository,
    stock_indicator_repository,
)
from src.services.cache_manager import cache_manager
from src.utils.indicators import calculate_all_indicators


class StockDataService:
    """
    주가 데이터 서비스

    - pykrx 기반 시세/종목 데이터 조회
    - FinanceDataReader를 fallback으로 활용하여 안정성 확보
    - 실시간 데이터는 Redis 캐시 우선 조회
    - 캐싱 지원
    """

    def __init__(self):
        self.cache = cache_manager
        # realtime_cache_service는 순환 import 방지를 위해 메서드 내에서 import

    async def _listing_from_db(self, market: Optional[str]) -> Optional[pd.DataFrame]:
        def _fetch():
            target = None
            if market:
                if market.upper() == "ALL":
                    target = None
                else:
                    target = market
            return stock_repository.list_by_market(target)

        rows = await asyncio.to_thread(_fetch)
        if not rows:
            return None

        records: List[Dict[str, Any]] = []
        for row in rows:
            records.append(
                {
                    "Code": row.stock_code,
                    "Name": row.stock_name,
                    "Market": row.market,
                    "Industry": row.industry or row.sector,
                }
            )

        df = pd.DataFrame(records)
        if df.empty:
            return None
        df = df.sort_values("Name")
        return df

    async def _listing_from_fdr(self, market: str) -> Optional[pd.DataFrame]:
        def _fetch() -> Optional[pd.DataFrame]:
            target = market.upper()
            if target == "ALL":
                target = "KRX"

            try:
                listing = fdr.StockListing(target)
            except Exception:
                return None

            if listing is None or listing.empty:
                return None

            df = listing.copy()
            if "Symbol" in df.columns:
                df = df.rename(columns={"Symbol": "Code"})
            if "Sector" in df.columns and "Industry" not in df.columns:
                df["Industry"] = df["Sector"]
            if "Market" not in df.columns or df["Market"].isna().all():
                df["Market"] = "KRX" if market.upper() == "ALL" else market.upper()

            available = [col for col in ("Code", "Name", "Market", "Industry") if col in df.columns]
            df = df[available].copy()

            if "Market" not in df.columns:
                df["Market"] = "KRX" if market.upper() == "ALL" else market.upper()
            if "Industry" not in df.columns:
                df["Industry"] = None

            df["Code"] = df["Code"].astype(str).str.zfill(6)
            drop_cols = ["Code"]
            if "Name" in df.columns:
                drop_cols.append("Name")
            df = df.dropna(subset=drop_cols)
            if market.upper() != "ALL":
                df["Market"] = market.upper()

            df = df.drop_duplicates(subset=["Code"])
            df = df.sort_values("Name")
            return df

        return await asyncio.to_thread(_fetch)

    async def _save_listing_to_db(self, market: str, df: pd.DataFrame) -> None:
        records: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            records.append(
                {
                    "stock_code": row["Code"],
                    "stock_name": row["Name"],
                    "market": row.get("Market", market),
                    "sector": row.get("Industry"),
                    "industry": row.get("Industry"),
                }
            )
        if records:
            await asyncio.to_thread(stock_repository.upsert_many, records)

    @staticmethod
    def _cache_listing_payload(df: pd.DataFrame) -> List[Dict[str, Any]]:
        return df.to_dict("records")

    async def _prices_from_db(self, stock_code: str, days: int) -> Optional[pd.DataFrame]:
        start = (datetime.now() - timedelta(days=days + 5)).date()

        rows = await asyncio.to_thread(
            stock_price_repository.get_prices_since,
            stock_code,
            start,
        )
        if not rows:
            return None

        records: List[Dict[str, Any]] = []
        for row in rows:
            if row.date is None:
                continue
            records.append(
                {
                    "Date": row.date,
                    "Open": float(row.open_price) if row.open_price is not None else None,
                    "High": float(row.high_price) if row.high_price is not None else None,
                    "Low": float(row.low_price) if row.low_price is not None else None,
                    "Close": float(row.close_price) if row.close_price is not None else None,
                    "Volume": int(row.volume) if row.volume is not None else 0,
                    "Change": float(row.change_amount) if row.change_amount is not None else None,
                }
            )

        if not records:
            return None

        df = pd.DataFrame(records)
        df = df.dropna(subset=["Close"])
        if df.empty:
            return None

        df = df.sort_values("Date")
        df = df.set_index("Date")
        return df

    async def _save_prices_to_db(self, stock_code: str, df: pd.DataFrame) -> None:
        if df.empty:
            return

        records: List[Dict[str, Any]] = []
        for idx, row in df.iterrows():
            price_date = idx.date() if isinstance(idx, datetime) else idx
            if isinstance(price_date, datetime):
                price_date = price_date.date()
            records.append(
                {
                    "date": price_date,
                    "open_price": float(row.get("Open")) if not pd.isna(row.get("Open")) else None,
                    "high_price": float(row.get("High")) if not pd.isna(row.get("High")) else None,
                    "low_price": float(row.get("Low")) if not pd.isna(row.get("Low")) else None,
                    "close_price": float(row.get("Close")) if not pd.isna(row.get("Close")) else None,
                    "volume": int(row.get("Volume")) if not pd.isna(row.get("Volume")) else None,
                    "change_amount": float(row.get("Change")) if not pd.isna(row.get("Change")) else None,
                }
            )

        if records:
            await asyncio.to_thread(stock_price_repository.upsert_many, stock_code, records)

    async def _save_latest_indicators(self, stock_code: str, df: pd.DataFrame) -> None:
        if df.empty:
            return

        indicators = calculate_all_indicators(df)
        if not indicators:
            return

        latest_idx = df.index[-1]
        if isinstance(latest_idx, datetime):
            ref_date = latest_idx.date()
        else:
            ref_date = latest_idx

        ma = indicators.get("moving_averages", {})
        bb = indicators.get("bollinger_bands", {})
        macd = indicators.get("macd", {})
        volume = indicators.get("volume", {})
        rsi = indicators.get("rsi", {})

        payload = {
            "ma5": ma.get("MA5"),
            "ma20": ma.get("MA20"),
            "ma60": ma.get("MA60"),
            "ma120": ma.get("MA120"),
            "rsi14": rsi.get("value"),
            "macd": macd.get("macd"),
            "macd_signal": macd.get("signal"),
            "macd_histogram": macd.get("histogram"),
            "bollinger_upper": bb.get("upper"),
            "bollinger_middle": bb.get("middle"),
            "bollinger_lower": bb.get("lower"),
            "current_volume": volume.get("current_volume"),
            "average_volume": volume.get("avg_volume"),
            "volume_ratio": volume.get("volume_ratio"),
            "is_high_volume": "Y" if volume.get("is_high_volume") else "N",
        }

        await asyncio.to_thread(
            stock_indicator_repository.upsert,
            stock_code,
            ref_date,
            payload,
        )

    @staticmethod
    def _cache_prices_payload(df: pd.DataFrame) -> List[Dict[str, Any]]:
        reset = df.reset_index()
        if "Date" not in reset.columns:
            reset = reset.rename(columns={"index": "Date"})

        def _serialize(value: Any) -> Any:
            if isinstance(value, (datetime, date)):
                return value.isoformat()
            return value

        for column in reset.columns:
            reset[column] = reset[column].apply(_serialize)

        return reset.to_dict("records")

    async def get_realtime_price(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        실시간 주가 조회 (Redis 캐시 우선)

        Args:
            stock_code: 종목 코드 (예: "005930")

        Returns:
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "price": 72000,
                "change": 1000,
                "change_rate": 1.41,
                "volume": 15234567,
                "timestamp": "2025-10-27T..."
            }
            없으면 None
        """
        # 순환 import 방지
        from src.services.realtime_cache_service import realtime_cache_service

        # 1. Redis 캐시 우선 조회
        cached = await realtime_cache_service.get_cached_price(stock_code)

        if cached:
            print(f"✅ [Realtime] 캐시 히트: {stock_code}")
            return cached

        # 2. 캐시 미스 → KIS API Fallback
        print(f"⚠️ [Realtime] 캐시 미스 → API 호출: {stock_code}")

        try:
            from src.services.kis_service import kis_service

            price_data = await kis_service.get_stock_price(stock_code)

            if price_data:
                # API 응답을 캐시 형식으로 변환
                return {
                    "stock_code": stock_code,
                    "stock_name": price_data.get("stock_name", ""),
                    "price": price_data.get("current_price", 0),
                    "change": price_data.get("change_price", 0),
                    "change_rate": price_data.get("change_rate", 0.0),
                    "volume": price_data.get("volume", 0),
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                return None

        except Exception as e:
            print(f"❌ [Realtime] API 호출 실패: {stock_code} - {e}")
            return None

    async def get_stock_price(
        self, stock_code: str, days: int = 30
    ) -> Optional[pd.DataFrame]:
        """
        주가 데이터 조회 (pykrx 사용)

        Args:
            stock_code: 종목 코드 (예: "005930")
            days: 조회 기간 (일)

        Returns:
            DataFrame: 주가 데이터 (Open, High, Low, Close, Volume)
        """
        # 캐시 키
        cache_key = f"stock_price:{stock_code}:{days}"

        # 캐시 확인
        cached = self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ 캐시 히트: {cache_key}")
            cached_df = pd.DataFrame(cached)
            if "Date" in cached_df.columns:
                cached_df["Date"] = pd.to_datetime(cached_df["Date"])
                cached_df = cached_df.set_index("Date")
            return cached_df

        # DB 조회
        db_df = await self._prices_from_db(stock_code, days)
        if db_df is not None and not db_df.empty:
            self.cache.set(
                cache_key,
                self._cache_prices_payload(db_df),
                ttl=settings.CACHE_TTL_MARKET_DATA,
            )
            await self._save_latest_indicators(stock_code, db_df)
            return db_df

        # pykrx 호출 - 날짜 형식 변환 ("YYYYMMDD")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        try:
            # pykrx.stock.get_market_ohlcv() 사용
            df = await asyncio.to_thread(
                krx_stock.get_market_ohlcv,
                start_str,
                end_str,
                stock_code
            )

            if df is not None and len(df) > 0:
                # pykrx 컬럼명을 영어로 변경 (표준화)
                df.columns = ["Open", "High", "Low", "Close", "Volume", "Change"]

                # 캐싱 (60초 TTL)
                self.cache.set(
                    cache_key,
                    self._cache_prices_payload(df),
                    ttl=settings.CACHE_TTL_MARKET_DATA,
                )
                await self._save_prices_to_db(stock_code, df)
                await self._save_latest_indicators(stock_code, df)
                print(f"✅ 주가 데이터 조회 성공 (pykrx): {stock_code}")
                return df
            else:
                print(f"⚠️ 주가 데이터 없음: {stock_code}")
                return None

        except Exception as e:
            print(f"❌ 주가 데이터 조회 실패 (pykrx): {stock_code}, {e}")
            return None

    async def get_stock_listing(self, market: str = "KOSPI") -> Optional[pd.DataFrame]:
        """
        종목 리스트 조회 (pykrx 기본, FinanceDataReader fallback)

        Args:
            market: 시장 (KOSPI, KOSDAQ, KONEX)

        Returns:
            DataFrame: 종목 리스트 (Code, Name, Market)
        """
        # 캐시 키
        cache_key = f"stock_listing:{market}"

        # 캐시 확인
        cached = self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ 캐시 히트: {cache_key}")
            cached_df = pd.DataFrame(cached)
            return cached_df

        # DB 조회
        db_listing = await self._listing_from_db(market)
        if db_listing is not None and not db_listing.empty:
            self.cache.set(
                cache_key,
                self._cache_listing_payload(db_listing),
                ttl=86400,
            )
            return db_listing

        pykrx_error: Optional[Exception] = None
        pykrx_df: Optional[pd.DataFrame] = None

        # pykrx 호출
        try:
            today_str = datetime.now().strftime("%Y%m%d")

            ticker_list = await asyncio.to_thread(
                krx_stock.get_market_ticker_list,
                today_str,
                market=market
            )

            if ticker_list:
                data = []
                for ticker in ticker_list:
                    name = await asyncio.to_thread(
                        krx_stock.get_market_ticker_name,
                        ticker
                    )
                    data.append(
                        {
                            "Code": ticker,
                            "Name": name,
                            "Market": market,
                        }
                    )

                pykrx_df = pd.DataFrame(data)
            else:
                print(f"⚠️ pykrx 종목 리스트 없음: {market}")

        except Exception as e:
            pykrx_error = e
            print(f"❌ 종목 리스트 조회 실패 (pykrx): {market}, {e}")

        if pykrx_df is not None and not pykrx_df.empty:
            self.cache.set(
                cache_key,
                self._cache_listing_payload(pykrx_df),
                ttl=86400,
            )
            await self._save_listing_to_db(market, pykrx_df)
            print(f"✅ 종목 리스트 조회 성공 (pykrx): {market}, {len(pykrx_df)}개")
            return pykrx_df

        # pykrx가 실패하거나 빈 결과일 때 FinanceDataReader로 대체
        fdr_df = await self._listing_from_fdr(market)
        if fdr_df is not None and not fdr_df.empty:
            self.cache.set(
                cache_key,
                self._cache_listing_payload(fdr_df),
                ttl=86400,
            )
            await self._save_listing_to_db(market, fdr_df)

            fallback_reason = "pykrx 결과 없음"
            if pykrx_error:
                fallback_reason = f"pykrx 오류: {pykrx_error}"
            print(f"✅ 종목 리스트 조회 성공 (FinanceDataReader 대체, {fallback_reason}): {market}, {len(fdr_df)}개")
            return fdr_df

        return None

    async def get_stock_by_name(self, name: str, market: str = "KOSPI") -> Optional[str]:
        """
        종목명으로 종목 코드 찾기 (퍼지 매칭 지원)

        Args:
            name: 종목명 (예: "삼성전자", "sk 하이닉스")
            market: 시장 (KOSPI, KOSDAQ, KONEX)

        Returns:
            str: 종목 코드 (예: "005930")
        """
        df = await self.get_stock_listing(market)

        if df is None:
            return None

        # 검색어 정규화 (띄어쓰기 제거, 소문자 변환)
        search_term = name.strip().replace(" ", "").lower()

        # 1차 시도: 정확히 일치하는 종목 찾기
        exact_match = df[df["Name"].str.lower() == search_term]
        if len(exact_match) > 0:
            stock_code = exact_match.iloc[0]["Code"]
            print(f"✅ 종목 코드 찾기 성공 (정확 일치): {name} -> {stock_code}")
            return stock_code

        # 2차 시도: 띄어쓰기 제거 후 매칭
        df_copy = df.copy()
        df_copy["Name_Normalized"] = df_copy["Name"].str.replace(" ", "").str.lower()
        normalized_match = df_copy[df_copy["Name_Normalized"] == search_term]
        if len(normalized_match) > 0:
            stock_code = normalized_match.iloc[0]["Code"]
            print(f"✅ 종목 코드 찾기 성공 (정규화 매칭): {name} -> {stock_code}")
            return stock_code

        # 3차 시도: 부분 포함 검색 (원본)
        contains_match = df[df["Name"].str.contains(name, na=False, case=False)]
        if len(contains_match) > 0:
            stock_code = contains_match.iloc[0]["Code"]
            print(f"✅ 종목 코드 찾기 성공 (부분 매칭): {name} -> {stock_code}")
            return stock_code

        # 4차 시도: 정규화된 이름으로 부분 포함 검색
        normalized_contains = df_copy[df_copy["Name_Normalized"].str.contains(search_term, na=False)]
        if len(normalized_contains) > 0:
            stock_code = normalized_contains.iloc[0]["Code"]
            print(f"✅ 종목 코드 찾기 성공 (정규화 부분 매칭): {name} -> {stock_code}")
            return stock_code

        print(f"⚠️ 종목을 찾을 수 없음: {name} (시장: {market})")
        return None

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
        self, index_name: str = "KOSPI", days: int = 60, max_retries: int = 3
    ) -> Optional[pd.DataFrame]:
        """
        시장 지수 데이터 조회 (pykrx 사용)

        Args:
            index_name: 지수 이름 ("KOSPI", "KOSDAQ", "KRX100")
            days: 조회 기간 (일)
            max_retries: 최대 재시도 횟수

        Returns:
            DataFrame: 지수 데이터 (Open, High, Low, Close, Volume)

        Raises:
            Exception: 모든 재시도 실패 시
        """
        # 지수 이름 → 티커 코드 매핑
        index_ticker_map = {
            "KOSPI": "1001",
            "KOSDAQ": "2001",
            "KRX100": "1028",
        }

        ticker = index_ticker_map.get(index_name.upper())
        if not ticker:
            raise ValueError(f"지원하지 않는 지수: {index_name}. 사용 가능: {list(index_ticker_map.keys())}")

        # 캐시 키
        cache_key = f"market_index:{index_name}:{days}"

        # 캐시 확인 (1시간 TTL - Rate Limit 방지)
        cached = self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ [Index] 캐시 히트: {cache_key}")
            return pd.DataFrame(cached)

        # Retry 로직 with exponential backoff
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        for attempt in range(max_retries):
            try:
                # pykrx.stock.get_index_ohlcv() 사용 (티커 코드 사용)
                df = await asyncio.to_thread(
                    krx_stock.get_index_ohlcv,
                    start_str,
                    end_str,
                    ticker
                )

                if df is not None and len(df) > 0:
                    # pykrx 컬럼명을 영어로 변경 (표준화)
                    df.columns = ["Open", "High", "Low", "Close", "Volume"]

                    # 캐싱 (1시간 TTL - 지수는 실시간성 덜 중요)
                    self.cache.set(
                        cache_key,
                        df.to_dict("records"),
                        ttl=settings.CACHE_TTL_MARKET_INDEX
                    )
                    print(f"✅ [Index] 지수 데이터 조회 성공 (pykrx): {index_name} ({len(df)}일)")
                    return df
                else:
                    print(f"⚠️ [Index] 지수 데이터 없음: {index_name}")
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
                    error_detail = f"{index_name}, attempt {attempt + 1}/{max_retries}, {error_msg}"
                    print(f"❌ [Index] 지수 데이터 조회 실패 (pykrx): {error_detail}")

                    if attempt == max_retries - 1:
                        logger.error(f"❌ [Index] {index_name} 데이터 조회 실패 (pykrx API 이슈)")
                        return None

        return None


    async def get_fundamental_data(
        self, stock_code: str, date: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        펀더멘털 데이터 조회 (pykrx 사용)

        Args:
            stock_code: 종목 코드
            date: 조회 날짜 (YYYYMMDD), 기본값은 오늘

        Returns:
            dict: {
                "PER": 주가수익비율,
                "PBR": 주가순자산비율,
                "EPS": 주당순이익,
                "DIV": 배당수익률,
                "DPS": 주당배당금,
                "BPS": 주당순자산가치
            }
        """
        if not date:
            date = datetime.now().strftime("%Y%m%d")

        # 캐시 키
        cache_key = f"fundamental:{stock_code}:{date}"

        # 캐시 확인
        cached = self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ 캐시 히트: {cache_key}")
            return cached

        try:
            # pykrx.stock.get_market_fundamental() 사용
            df = await asyncio.to_thread(
                krx_stock.get_market_fundamental,
                date,
                date,
                stock_code
            )

            if df is not None and len(df) > 0:
                # DataFrame을 dict로 변환
                row = df.iloc[0]
                fundamental = {
                    "PER": float(row.get("PER", 0)) if pd.notna(row.get("PER")) else None,
                    "PBR": float(row.get("PBR", 0)) if pd.notna(row.get("PBR")) else None,
                    "EPS": float(row.get("EPS", 0)) if pd.notna(row.get("EPS")) else None,
                    "DIV": float(row.get("DIV", 0)) if pd.notna(row.get("DIV")) else None,
                    "DPS": float(row.get("DPS", 0)) if pd.notna(row.get("DPS")) else None,
                    "BPS": float(row.get("BPS", 0)) if pd.notna(row.get("BPS")) else None,
                }

                # 캐싱 (1일 TTL)
                self.cache.set(cache_key, fundamental, ttl=86400)
                print(f"✅ 펀더멘털 데이터 조회 성공 (pykrx): {stock_code}")
                return fundamental
            else:
                print(f"⚠️ 펀더멘털 데이터 없음: {stock_code}")
                return None

        except Exception as e:
            import traceback
            print(f"❌ 펀더멘털 데이터 조회 실패 (pykrx): {stock_code}")
            print(f"   에러 타입: {type(e).__name__}")
            print(f"   에러 메시지: {str(e)}")
            print(f"   호출 인자: date={date}, stock_code={stock_code}")
            traceback.print_exc()
            return None

    async def get_market_cap_data(
        self, stock_code: str, date: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        시가총액 및 거래 데이터 조회 (pykrx 사용)

        Args:
            stock_code: 종목 코드
            date: 조회 날짜 (YYYYMMDD), 기본값은 오늘

        Returns:
            dict: {
                "market_cap": 시가총액 (원),
                "trading_volume": 거래량,
                "trading_value": 거래대금 (원),
                "shares_outstanding": 상장주식수
            }
        """
        if not date:
            date = datetime.now().strftime("%Y%m%d")

        # 캐시 키
        cache_key = f"market_cap:{stock_code}:{date}"

        # 캐시 확인
        cached = self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ 캐시 히트: {cache_key}")
            return cached

        try:
            # pykrx.stock.get_market_cap() 사용
            df = await asyncio.to_thread(
                krx_stock.get_market_cap,
                date,
                date,
                stock_code
            )

            if df is not None and len(df) > 0:
                # DataFrame을 dict로 변환
                row = df.iloc[0]
                market_cap_data = {
                    "market_cap": int(row.get("시가총액", 0)) if pd.notna(row.get("시가총액")) else None,
                    "trading_volume": int(row.get("거래량", 0)) if pd.notna(row.get("거래량")) else None,
                    "trading_value": int(row.get("거래대금", 0)) if pd.notna(row.get("거래대금")) else None,
                    "shares_outstanding": int(row.get("상장주식수", 0)) if pd.notna(row.get("상장주식수")) else None,
                }

                # 캐싱 (1일 TTL)
                self.cache.set(cache_key, market_cap_data, ttl=86400)
                print(f"✅ 시가총액 데이터 조회 성공 (pykrx): {stock_code}")
                return market_cap_data
            else:
                print(f"⚠️ 시가총액 데이터 없음: {stock_code}")
                return None

        except Exception as e:
            import traceback
            print(f"❌ 시가총액 데이터 조회 실패 (pykrx): {stock_code}")
            print(f"   에러 타입: {type(e).__name__}")
            print(f"   에러 메시지: {str(e)}")
            print(f"   호출 인자: date={date}, stock_code={stock_code}")
            traceback.print_exc()
            return None

    async def get_investor_trading(
        self, stock_code: str, days: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        투자주체별 매매 동향 조회 (pykrx 사용)

        Args:
            stock_code: 종목 코드
            days: 조회 기간 (일)

        Returns:
            dict: {
                "foreign_net": 외국인 순매수 (최근),
                "institution_net": 기관 순매수 (최근),
                "individual_net": 개인 순매수 (최근),
                "foreign_trend": "순매수" | "순매도" | "중립",
                "institution_trend": "순매수" | "순매도" | "중립",
            }
        """
        # 캐시 키
        cache_key = f"investor_trading:{stock_code}:{days}"

        # 캐시 확인
        cached = self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ 캐시 히트: {cache_key}")
            return cached

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        try:
            # pykrx.stock.get_market_trading_value_by_date() 사용
            df = await asyncio.to_thread(
                krx_stock.get_market_trading_value_by_date,
                start_str,
                end_str,
                stock_code
            )

            if df is not None and len(df) > 0:
                # 최근 데이터 추출
                latest = df.iloc[-1]

                foreign_net = int(latest.get("외국인순매수", 0)) if pd.notna(latest.get("외국인순매수")) else 0
                institution_net = int(latest.get("기관순매수", 0)) if pd.notna(latest.get("기관순매수")) else 0
                individual_net = int(latest.get("개인순매수", 0)) if pd.notna(latest.get("개인순매수")) else 0

                # 추세 판단 (최근 7일 평균)
                recent_df = df.tail(7)
                foreign_avg = recent_df.get("외국인순매수", pd.Series([0])).mean()
                institution_avg = recent_df.get("기관순매수", pd.Series([0])).mean()

                investor_data = {
                    "foreign_net": foreign_net,
                    "institution_net": institution_net,
                    "individual_net": individual_net,
                    "foreign_trend": "순매수" if foreign_avg > 0 else "순매도" if foreign_avg < 0 else "중립",
                    "institution_trend": "순매수" if institution_avg > 0 else "순매도" if institution_avg < 0 else "중립",
                }

                # 캐싱 (1시간 TTL)
                self.cache.set(cache_key, investor_data, ttl=3600)
                print(f"✅ 투자주체별 매매 조회 성공 (pykrx): {stock_code}")
                return investor_data
            else:
                print(f"⚠️ 투자주체별 매매 데이터 없음: {stock_code}")
                return None

        except Exception as e:
            import traceback
            print(f"❌ 투자주체별 매매 조회 실패 (pykrx): {stock_code}")
            print(f"   에러 타입: {type(e).__name__}")
            print(f"   에러 메시지: {str(e)}")
            print(f"   호출 인자: start={start_str}, end={end_str}, stock_code={stock_code}")
            traceback.print_exc()
            return None


# 싱글톤 인스턴스
stock_data_service = StockDataService()


async def seed_market_data(
    market: str = "KOSPI",
    days: int = 30,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    종목 목록과 과거 주가 데이터를 DB에 선적재합니다.

    Args:
        market: 대상 시장 (KOSPI, KOSDAQ, KONEX, ALL)
        days: 저장할 과거 일수
        limit: 상위 N개 종목만 처리 (테스트용)
        enrich_from_dart: DART 고유번호를 함께 저장할지 여부
    """
    df = await stock_data_service.get_stock_listing(market)
    if df is None or df.empty:
        raise RuntimeError(f"{market} 시장의 종목 목록을 가져오지 못했습니다.")

    codes = df["Code"].dropna().astype(str).tolist()
    if limit is not None:
        codes = codes[:limit]

    total = len(codes)
    success = 0
    failures: List[str] = []

    for idx, code in enumerate(codes, start=1):
        price_df = await stock_data_service.get_stock_price(code, days=days)
        if price_df is None or price_df.empty:
            failures.append(code)
            continue

        success += 1
        if idx % 20 == 0 or idx == total:
            print(f"📦 시드 진행 상황: {idx}/{total} (성공 {success}, 실패 {len(failures)})")

    return {
        "market": market,
        "total": total,
        "success": success,
        "failed": len(failures),
        "failed_codes": failures,
    }


async def update_recent_prices_for_market(
    market: str = "ALL",
    days: int = 5,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """지정한 시장의 종목들에 대해 최근 주가/지표를 갱신"""

    listing = await stock_data_service.get_stock_listing(market)
    if listing is None or listing.empty:
        raise RuntimeError(f"{market} 시장의 종목 목록을 조회할 수 없습니다.")

    codes = listing["Code"].dropna().astype(str).tolist()
    if limit is not None:
        codes = codes[:limit]

    summary = {
        "market": market,
        "processed": 0,
        "success": 0,
        "failed": [],
    }

    for idx, code in enumerate(codes, start=1):
        df = await stock_data_service.get_stock_price(code, days=days)
        if df is None or df.empty:
            summary["failed"].append(code)
        else:
            summary["success"] += 1
        summary["processed"] = idx

    return summary
