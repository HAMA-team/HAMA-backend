"""주가 데이터 서비스 (DB Repository + 외부 API + Realtime Cache)"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import FinanceDataReader as fdr
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.config.settings import settings
from src.repositories import (
    stock_price_repository,
    stock_repository,
    stock_indicator_repository,
)
from src.services.kis_service import kis_service
from src.utils.indicators import calculate_all_indicators
from src.utils.llm_factory import get_claude_llm

logger = logging.getLogger(__name__)


class StockMatchResult(BaseModel):
    """LLM이 반환하는 종목 매칭 결과"""
    matched_stock_code: Optional[str] = Field(
        default=None,
        description="매칭된 종목 코드 (예: '035420'). 매칭 실패 시 null"
    )
    matched_stock_name: Optional[str] = Field(
        default=None,
        description="매칭된 종목명 (예: 'NAVER'). 매칭 실패 시 null"
    )
    confidence: float = Field(
        description="매칭 신뢰도 (0.0~1.0)"
    )
    reasoning: str = Field(
        description="매칭 판단 근거"
    )


class StockDataService:
    """
    주가 데이터 서비스

    - pykrx 기반 시세/종목 데이터 조회
    - FinanceDataReader를 fallback으로 활용하여 안정성 확보
    - 실시간 데이터는 Redis 캐시 우선 조회
    - 캐싱 지원
    """

    def __init__(self):
        pass

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
        """종목 리스트를 DB에 저장 (DataFrame 타입 체크 포함)"""
        records: List[Dict[str, Any]] = []
        for idx, row in df.iterrows():
            try:
                # Code, Name 필수 필드 검증
                stock_code = row.get("Code")
                stock_name = row.get("Name")

                # None, DataFrame, Series 타입 체크
                if stock_code is None or isinstance(stock_code, (pd.DataFrame, pd.Series)):
                    logger.warning(f"⚠️ [DB] 잘못된 stock_code 타입: {type(stock_code).__name__} at index {idx}")
                    continue

                if stock_name is None or isinstance(stock_name, (pd.DataFrame, pd.Series)):
                    logger.warning(f"⚠️ [DB] 잘못된 stock_name 타입: {type(stock_name).__name__} for {stock_code}")
                    continue

                # 문자열로 변환
                stock_code_str = str(stock_code).strip()
                stock_name_str = str(stock_name).strip()

                if not stock_code_str or not stock_name_str:
                    logger.warning(f"⚠️ [DB] 빈 필드: code={stock_code_str}, name={stock_name_str}")
                    continue

                records.append(
                    {
                        "stock_code": stock_code_str,
                        "stock_name": stock_name_str,
                        "market": str(row.get("Market", market)),
                        "sector": str(row.get("Industry")) if pd.notna(row.get("Industry")) else None,
                        "industry": str(row.get("Industry")) if pd.notna(row.get("Industry")) else None,
                    }
                )
            except Exception as row_error:
                logger.error(f"❌ [DB] 레코드 변환 오류 at index {idx}: {row_error}")
                continue

        if records:
            logger.info(f"💾 [DB] 종목 {len(records)}개 저장 시작...")
            await asyncio.to_thread(stock_repository.upsert_many, records)
            logger.info(f"✅ [DB] 종목 {len(records)}개 저장 완료")
        else:
            logger.warning("⚠️ [DB] 저장할 유효한 레코드 없음")

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

    async def get_realtime_price(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        실시간 주가 조회 (KIS API 직접 호출)

        Args:
            stock_code: 종목 코드 (예: "005930")
        """
        from src.services.kis_service import kis_service

        try:
            price_data = await kis_service.get_stock_price(stock_code)
        except Exception as exc:  # pragma: no cover - 네트워크 예외 로깅
            logger.error("❌ [Realtime] 실시간 시세 조회 실패: %s - %s", stock_code, exc)
            return None

        if not price_data:
            logger.warning("⚠️ [Realtime] 시세 데이터를 찾을 수 없음: %s", stock_code)
            return None

        return {
            "stock_code": stock_code,
            "stock_name": price_data.get("stock_name", ""),
            "price": price_data.get("current_price", 0),
            "change": price_data.get("change_price", 0),
            "change_rate": price_data.get("change_rate", 0.0),
            "volume": price_data.get("volume", 0),
            "timestamp": datetime.now().isoformat(),
        }

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
        # DB 조회
        db_df = await self._prices_from_db(stock_code, days)
        if db_df is not None and not db_df.empty:
            await self._save_latest_indicators(stock_code, db_df)
            return db_df

        # pykrx 호출 - 날짜 형식 변환 ("YYYYMMDD")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        # 1순위: KIS API
        try:
            logger.info(f"📊 [KIS API] 주가 조회 시도: {stock_code}")
            df = await kis_service.get_stock_daily_price(stock_code, start_str, end_str)

            if df is not None and len(df) > 0:
                # KIS API는 이미 표준 컬럼명 사용 (Open, High, Low, Close, Volume)
                await self._save_prices_to_db(stock_code, df)
                await self._save_latest_indicators(stock_code, df)
                logger.info(f"✅ 주가 데이터 조회 성공 (KIS API): {stock_code}")
                return df

        except Exception as e:
            logger.warning(f"⚠️ KIS API 주가 조회 실패, FinanceDataReader fallback 시도: {stock_code} - {e}")

        # 2순위: FinanceDataReader fallback
        try:
            logger.info(f"📊 [FinanceDataReader] 주가 조회 시도: {stock_code}")
            df = await asyncio.to_thread(
                fdr.DataReader,
                stock_code,
                start_str,
                end_str
            )

            if df is not None and len(df) > 0:
                # FinanceDataReader 컬럼명 표준화 (필요 시)
                if "Change" in df.columns:
                    df = df[["Open", "High", "Low", "Close", "Volume"]]

                await self._save_prices_to_db(stock_code, df)
                await self._save_latest_indicators(stock_code, df)
                logger.info(f"✅ 주가 데이터 조회 성공 (FinanceDataReader): {stock_code}")
                return df
            else:
                logger.warning(f"⚠️ 주가 데이터 없음: {stock_code}")
                return None

        except Exception as e:
            logger.error(f"❌ 주가 데이터 조회 실패 (모든 소스): {stock_code}, {e}")
            return None

    async def get_stock_listing(self, market: str = "KOSPI") -> Optional[pd.DataFrame]:
        """
        종목 리스트 조회 (FinanceDataReader 사용)

        Args:
            market: 시장 (KOSPI, KOSDAQ, KONEX)

        Returns:
            DataFrame: 종목 리스트 (Code, Name, Market)
        """
        # DB 조회
        db_listing = await self._listing_from_db(market)
        if db_listing is not None and not db_listing.empty:
            return db_listing

        # FinanceDataReader로 종목 리스트 조회
        fdr_df = await self._listing_from_fdr(market)
        if fdr_df is not None and not fdr_df.empty:
            await self._save_listing_to_db(market, fdr_df)
            logger.info(f"✅ 종목 리스트 조회 성공 (FinanceDataReader): {market}, {len(fdr_df)}개")
            return fdr_df

        logger.warning(f"⚠️ 종목 리스트 조회 실패: {market}")
        return None

    async def _match_stock_with_llm(
        self, user_input: str, candidates_df: pd.DataFrame, market: str
    ) -> Optional[str]:
        """
        LLM을 사용하여 종목명 매칭 (의미적 유사도 기반)

        Args:
            user_input: 사용자 입력 종목명 (예: "네이버", "삼전", "SK하이닉")
            candidates_df: 후보 종목 DataFrame (Code, Name 컬럼 필요)
            market: 시장명 (캐싱 키 생성용)

        Returns:
            종목 코드 (매칭 성공 시) 또는 None
        """
        # 후보 종목 선정 전략:
        # LLM에게 충분한 컨텍스트를 제공하되, 너무 많으면 비용/성능 문제
        # 상위 300개 종목을 사용 (시가총액 순으로 정렬되어 있다고 가정)
        MAX_CANDIDATES = 300

        if len(candidates_df) > MAX_CANDIDATES:
            candidates_df = candidates_df.head(MAX_CANDIDATES)
            logger.info(f"📋 [LLM Matching] 상위 {MAX_CANDIDATES}개 종목 사용")
        else:
            logger.info(f"📋 [LLM Matching] 전체 {len(candidates_df)}개 종목 사용")

        # 후보 종목 리스트 생성 (Code: Name 형식)
        candidates_list = [
            f"{row['Code']}: {row['Name']}"
            for _, row in candidates_df.iterrows()
        ]
        candidates_text = "\n".join(candidates_list)

        # LLM 프롬프트
        prompt = ChatPromptTemplate.from_messages([
            ("system", """당신은 한국 주식 종목명 매칭 전문가입니다.

사용자가 입력한 종목명과 가장 유사한 종목을 찾아주세요.

<matching_rules>
1. 동일 기업의 다양한 표현 매칭:
   - "네이버" ↔ "NAVER"
   - "삼전" ↔ "삼성전자"
   - "SK하이닉" ↔ "SK하이닉스"

2. 오타/약어 허용:
   - "엔에이버" → "NAVER"
   - "카카오뱅크" → "카카오뱅크"

3. 신뢰도 기준:
   - 0.9 이상: 확실한 매칭
   - 0.7~0.9: 높은 가능성
   - 0.5~0.7: 중간 가능성
   - 0.5 미만: 매칭 실패 (matched_stock_code를 null로 설정)

4. 매칭 실패 조건:
   - 유사한 종목이 전혀 없는 경우
   - 입력이 너무 모호한 경우
   - confidence < 0.5인 경우
</matching_rules>

<output_format>
반드시 JSON 형식으로 응답하세요:
- matched_stock_code: 종목 코드 (매칭 실패 시 null)
- matched_stock_name: 종목명 (매칭 실패 시 null)
- confidence: 0.0~1.0
- reasoning: 판단 근거
</output_format>"""),
            ("human", """사용자 입력: {user_input}

후보 종목 목록:
{candidates_text}

가장 유사한 종목을 찾아주세요.""")
        ])

        # LLM 초기화 (Claude Haiku 4.5 사용)
        llm = get_claude_llm(temperature=0, max_tokens=500)

        structured_llm = llm.with_structured_output(StockMatchResult)
        chain = prompt | structured_llm

        try:
            logger.info(f"🤖 [LLM Matching] 종목명 매칭 시작: '{user_input}' (후보 {len(candidates_df)}개)")

            result: StockMatchResult = await chain.ainvoke({
                "user_input": user_input,
                "candidates_text": candidates_text,
            })

            logger.info(f"📊 [LLM Matching] 결과:")
            logger.info(f"  - 매칭 종목: {result.matched_stock_name} ({result.matched_stock_code})")
            logger.info(f"  - 신뢰도: {result.confidence:.2f}")
            logger.info(f"  - 근거: {result.reasoning}")

            # 신뢰도 체크
            if result.confidence >= 0.5 and result.matched_stock_code:
                logger.info(f"✅ [LLM Matching] 매칭 성공: {user_input} -> {result.matched_stock_code}")
                return result.matched_stock_code
            else:
                logger.warning(f"⚠️ [LLM Matching] 신뢰도 낮음 또는 매칭 실패: {result.confidence:.2f}")
                return None

        except Exception as e:
            logger.error(f"❌ [LLM Matching] 오류 발생: {e}")
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

        # 5차 시도: LLM 기반 의미적 매칭 (fallback)
        logger.info(f"🤖 [StockData] 기존 매칭 실패 → LLM 매칭 시도: {name}")
        llm_matched_code = await self._match_stock_with_llm(name, df, market)
        if llm_matched_code:
            print(f"✅ 종목 코드 찾기 성공 (LLM 매칭): {name} -> {llm_matched_code}")
            return llm_matched_code

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
        시장 지수 데이터 조회 (KIS API 사용, FinanceDataReader fallback)

        Args:
            index_name: 지수 이름 ("KOSPI", "KOSDAQ", "KOSPI200")
            days: 조회 기간 (일)
            max_retries: 최대 재시도 횟수 (미사용, 호환성 유지)

        Returns:
            DataFrame: 지수 데이터 (Open, High, Low, Close, Volume)

        Raises:
            Exception: 모든 재시도 실패 시
        """
        # KIS API 지수 코드 매핑
        from src.constants.kis_constants import INDEX_CODES

        index_code = INDEX_CODES.get(index_name.upper())
        if not index_code:
            raise ValueError(f"지원하지 않는 지수: {index_name}. 사용 가능: {list(INDEX_CODES.keys())}")

        # 1순위: KIS API
        try:
            logger.info(f"📊 [Index] KIS API로 지수 조회: {index_name} ({index_code})")
            df = await kis_service.get_index_daily_price(
                index_code=index_code,
                period="D",
                days=days
            )

            if df is not None and not df.empty:
                logger.info(f"✅ [Index] 지수 데이터 조회 성공 (KIS API): {index_name} ({len(df)}일)")
                return df

        except Exception as e:
            logger.warning(f"⚠️ [Index] KIS API 조회 실패, FinanceDataReader fallback 시도: {e}")

        # 2순위: FinanceDataReader fallback
        try:
            logger.info(f"📊 [Index] FinanceDataReader로 지수 조회: {index_name}")

            # FinanceDataReader 티커 코드 매핑
            fdr_ticker_map = {
                "KOSPI": "KS11",      # 코스피 지수
                "KOSDAQ": "KQ11",     # 코스닥 지수
                "KOSPI200": "KS200",  # 코스피200
                "KRX100": "KRX100",   # KRX100
            }

            fdr_ticker = fdr_ticker_map.get(index_name.upper())
            if not fdr_ticker:
                raise ValueError(f"FinanceDataReader에서 지원하지 않는 지수: {index_name}")

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            df = await asyncio.to_thread(
                fdr.DataReader,
                fdr_ticker,
                start_str,
                end_str
            )

            if df is not None and len(df) > 0:
                # FinanceDataReader는 이미 표준 컬럼명 사용 (Open, High, Low, Close, Volume)
                # Change 컬럼 제거 (있다면)
                if "Change" in df.columns:
                    df = df[["Open", "High", "Low", "Close", "Volume"]]

                logger.info(f"✅ [Index] 지수 데이터 조회 성공 (FinanceDataReader): {index_name} ({len(df)}일)")
                return df
            else:
                logger.warning(f"⚠️ [Index] 지수 데이터 없음: {index_name}")
                return None

        except Exception as e:
            logger.error(f"❌ [Index] 지수 데이터 조회 실패 (모든 소스): {index_name}, {e}")
            return None


    async def get_fundamental_data(
        self, stock_code: str, date: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        펀더멘털 데이터 조회 (KIS API 사용)

        Args:
            stock_code: 종목 코드
            date: 조회 날짜 (YYYYMMDD), 미사용 (호환성 유지)

        Returns:
            dict: {
                "PER": 주가수익비율,
                "PBR": 주가순자산비율,
                "EPS": None (KIS API 미제공),
                "DIV": None (KIS API 미제공),
                "DPS": None (KIS API 미제공),
                "BPS": None (KIS API 미제공)
            }
        """
        try:
            # KIS API로 현재가 조회 (PER/PBR 포함)
            price_data = await kis_service.get_stock_price(stock_code)

            if price_data:
                fundamental = {
                    "PER": price_data.get("per"),  # KIS API 제공
                    "PBR": price_data.get("pbr"),  # KIS API 제공
                    "EPS": None,  # KIS API 미제공
                    "DIV": None,  # KIS API 미제공 (배당수익률)
                    "DPS": None,  # KIS API 미제공 (주당배당금)
                    "BPS": None,  # KIS API 미제공 (주당순자산가치)
                }

                logger.info(f"✅ 펀더멘털 데이터 조회 성공 (KIS API): {stock_code}")
                return fundamental
            else:
                logger.warning(f"⚠️ 펀더멘털 데이터 없음: {stock_code}")
                return None

        except Exception as e:
            logger.error(f"❌ 펀더멘털 데이터 조회 실패 (KIS API): {stock_code} - {e}")
            return None

    async def get_market_cap_data(
        self, stock_code: str, date: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        시가총액 및 거래 데이터 조회 (KIS API 사용)

        Args:
            stock_code: 종목 코드
            date: 조회 날짜 (YYYYMMDD), 미사용 (호환성 유지)

        Returns:
            dict: {
                "market_cap": 시가총액 (원),
                "trading_volume": 거래량,
                "trading_value": None (KIS API 미제공),
                "shares_outstanding": None (KIS API 미제공)
            }
        """
        try:
            # KIS API로 현재가 조회 (시가총액, 거래량 포함)
            price_data = await kis_service.get_stock_price(stock_code)

            if price_data:
                market_cap_data = {
                    "market_cap": price_data.get("market_cap"),  # KIS API 제공
                    "trading_volume": price_data.get("volume"),  # KIS API 제공
                    "trading_value": None,  # KIS API 미제공 (거래대금)
                    "shares_outstanding": None,  # KIS API 미제공 (상장주식수)
                }

                logger.info(f"✅ 시가총액 데이터 조회 성공 (KIS API): {stock_code}")
                return market_cap_data
            else:
                logger.warning(f"⚠️ 시가총액 데이터 없음: {stock_code}")
                return None

        except Exception as e:
            logger.error(f"❌ 시가총액 데이터 조회 실패 (KIS API): {stock_code} - {e}")
            return None

    # get_investor_trading() 메서드 제거됨 (2025-01-08)
    # KIS API에서 투자자별 매매 동향 데이터를 제공하지 않아 제거
    # Phase 2에서 크롤링 또는 외부 API로 재구현 예정


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

        if idx % 20 == 0 or idx == len(codes):
            print(
                f"📦 가격 시드 진행 ({market}): {idx}/{len(codes)} "
                f"(성공 {summary['success']}, 실패 {len(summary['failed'])})"
            )

    return summary
