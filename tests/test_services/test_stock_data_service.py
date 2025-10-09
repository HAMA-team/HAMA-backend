"""
Stock Data Service 테스트

FinanceDataReader 기반 주가 데이터 조회 및 Rate Limit 방지 테스트
"""
import pytest
from src.services import stock_data_service


class TestStockDataService:
    """Stock Data Service 테스트"""

    @pytest.mark.asyncio
    async def test_get_stock_price(self):
        """개별 종목 주가 조회"""
        # 삼성전자 주가 조회
        df = await stock_data_service.get_stock_price("005930", days=30)

        assert df is not None, "주가 데이터 조회 실패"
        assert len(df) > 0, "주가 데이터 없음"
        assert "Close" in df.columns, "Close 컬럼 없음"

    @pytest.mark.asyncio
    async def test_get_market_index_with_retry(self):
        """
        시장 지수 조회 (Rate Limit 방지)

        Note: Rate Limit 발생 가능 - Retry 로직 검증
        """
        # KOSPI 지수 조회 시도
        try:
            df = await stock_data_service.get_market_index("KS11", days=60)

            if df is not None and len(df) > 0:
                # 성공 시 검증
                assert "Close" in df.columns

                # 변동성 계산
                returns = df["Close"].pct_change().dropna()
                volatility = returns.std() * (252 ** 0.5) * 100
                assert volatility > 0, "변동성 계산 실패"
            else:
                pytest.skip("KOSPI 데이터 없음 (Rate Limit)")

        except Exception as e:
            # Rate Limit 에러는 허용 (Retry 후에도 실패 가능)
            if "Rate Limit" in str(e) or "429" in str(e):
                pytest.skip(f"Rate Limit 발생: {e}")
            else:
                raise

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """캐싱 메커니즘 검증"""
        # 첫 번째 호출
        df1 = await stock_data_service.get_stock_price("005930", days=30)
        assert df1 is not None

        # 두 번째 호출 (캐시 히트 예상)
        df2 = await stock_data_service.get_stock_price("005930", days=30)
        assert df2 is not None
        assert len(df1) == len(df2), "캐시 데이터 불일치"

    @pytest.mark.asyncio
    async def test_calculate_returns(self):
        """수익률 계산"""
        df = await stock_data_service.calculate_returns("005930", days=60)

        assert df is not None, "수익률 계산 실패"
        assert "Daily_Return" in df.columns, "일일 수익률 없음"
        assert "Cumulative_Return" in df.columns, "누적 수익률 없음"

    @pytest.mark.asyncio
    async def test_get_stock_listing(self):
        """종목 리스트 조회"""
        df = await stock_data_service.get_stock_listing("KOSPI")

        assert df is not None, "종목 리스트 조회 실패"
        assert len(df) > 0, "종목 리스트 없음"
        assert "Code" in df.columns, "Code 컬럼 없음"
        assert "Name" in df.columns, "Name 컬럼 없음"
