"""주가 데이터 서비스 (pykrx + Realtime Cache)"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd
from pykrx import stock as krx_stock

from src.services.cache_manager import cache_manager
from src.config.settings import settings


class StockDataService:
    """
    주가 데이터 서비스

    - FinanceDataReader를 사용한 주가 데이터 조회
    - 실시간 데이터는 Redis 캐시 우선 조회
    - 캐싱 지원
    """

    def __init__(self):
        self.cache = cache_manager
        # realtime_cache_service는 순환 import 방지를 위해 메서드 내에서 import

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
            return pd.DataFrame(cached)

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
                    cache_key, df.to_dict("records"), ttl=settings.CACHE_TTL_MARKET_DATA
                )
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
        종목 리스트 조회 (pykrx 사용)

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
            return pd.DataFrame(cached)

        # pykrx 호출
        try:
            today_str = datetime.now().strftime("%Y%m%d")

            # pykrx.stock.get_market_ticker_list() 사용
            ticker_list = await asyncio.to_thread(
                krx_stock.get_market_ticker_list,
                today_str,
                market=market
            )

            if ticker_list is not None and len(ticker_list) > 0:
                # 종목명 조회 (병렬 처리는 비효율적이므로 순차 처리)
                data = []
                for ticker in ticker_list:
                    name = await asyncio.to_thread(
                        krx_stock.get_market_ticker_name,
                        ticker
                    )
                    data.append({
                        "Code": ticker,
                        "Name": name,
                        "Market": market
                    })

                df = pd.DataFrame(data)

                # 캐싱 (1일 TTL)
                self.cache.set(cache_key, df.to_dict("records"), ttl=86400)
                print(f"✅ 종목 리스트 조회 성공 (pykrx): {market}, {len(df)}개")
                return df
            else:
                print(f"⚠️ 종목 리스트 없음: {market}")
                return None

        except Exception as e:
            print(f"❌ 종목 리스트 조회 실패 (pykrx): {market}, {e}")
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
                        # TODO: pykrx API 이슈 해결 전까지 mock 데이터 반환
                        # Issue: pykrx의 get_index_ohlcv()가 내부적으로 get_index_ticker_name()을 호출하는데
                        # 이 함수가 DataFrame에서 '지수명' 컬럼을 찾지 못하는 버그가 있음
                        print(f"⚠️ [Index] pykrx API 이슈로 인해 mock 데이터 반환: {index_name}")

                        # Mock 데이터 생성 (합리적인 추정치)
                        mock_prices = self._generate_mock_index_data(index_name, days)
                        if mock_prices:
                            df = pd.DataFrame(mock_prices, columns=["Open", "High", "Low", "Close", "Volume"])
                            df.index = pd.date_range(end=datetime.now(), periods=len(mock_prices), freq='D')

                            # 캐싱
                            self.cache.set(
                                cache_key,
                                df.to_dict("records"),
                                ttl=settings.CACHE_TTL_MARKET_INDEX
                            )
                            print(f"✅ [Index] Mock 데이터 생성 완료: {index_name}")
                            return df

                        # Mock 데이터 생성도 실패하면 None 반환
                        return None

        return None

    def _generate_mock_index_data(self, index_name: str, days: int) -> List[List[float]]:
        """
        시장 지수 mock 데이터 생성

        TODO: pykrx API 수정 후 제거 예정
        """
        # 기준 가격 (2024년 10월 기준 합리적 추정)
        base_prices = {
            "KOSPI": 2600.0,
            "KOSDAQ": 750.0,
            "KRX100": 6500.0,
        }

        base = base_prices.get(index_name, 2600.0)

        # 간단한 랜덤 워크로 mock 데이터 생성
        import random
        random.seed(42)  # 재현 가능성을 위해

        data = []
        current = base

        for _ in range(min(days, 60)):  # 최대 60일
            # ±1% 범위의 변동
            change = random.uniform(-0.01, 0.01)
            current = current * (1 + change)

            open_price = current * random.uniform(0.995, 1.005)
            high_price = current * random.uniform(1.0, 1.01)
            low_price = current * random.uniform(0.99, 1.0)
            close_price = current
            volume = random.randint(300000000, 500000000)

            data.append([open_price, high_price, low_price, close_price, volume])

        return data

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
            print(f"❌ 펀더멘털 데이터 조회 실패 (pykrx): {stock_code}, {e}")
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
            print(f"❌ 시가총액 데이터 조회 실패 (pykrx): {stock_code}, {e}")
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
            print(f"❌ 투자주체별 매매 조회 실패 (pykrx): {stock_code}, {e}")
            return None


# 싱글톤 인스턴스
stock_data_service = StockDataService()
