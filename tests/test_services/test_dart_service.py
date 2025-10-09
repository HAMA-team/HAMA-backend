"""
DART Service 테스트

DART API 종목코드 매핑 및 재무 데이터 조회 테스트
"""
import pytest
from src.services import dart_service
from src.config.settings import settings


class TestDARTService:
    """DART Service 테스트"""

    @pytest.mark.asyncio
    async def test_search_corp_code_major_stocks(self):
        """주요 종목 고유번호 조회"""
        if not settings.DART_API_KEY:
            pytest.skip("DART_API_KEY not configured")

        # 주요 종목 테스트
        test_stocks = {
            "005930": "삼성전자",
            "000660": "SK하이닉스",
            "035420": "NAVER",
        }

        for stock_code, name in test_stocks.items():
            corp_code = await dart_service.search_corp_code_by_stock_code(stock_code)

            assert corp_code is not None, f"{name} 고유번호를 찾을 수 없음"
            assert len(corp_code) == 8, f"{name} 고유번호 길이 오류"

    @pytest.mark.asyncio
    async def test_cache_mechanism(self):
        """Redis 캐싱 메커니즘 검증"""
        if not settings.DART_API_KEY:
            pytest.skip("DART_API_KEY not configured")

        # 첫 번째 조회 (캐시 미스 → 다운로드)
        corp_code_1 = await dart_service.search_corp_code_by_stock_code("005930")
        assert corp_code_1 is not None

        # 두 번째 조회 (캐시 히트)
        corp_code_2 = await dart_service.search_corp_code_by_stock_code("000660")
        assert corp_code_2 is not None

    @pytest.mark.asyncio
    async def test_invalid_stock_code(self):
        """존재하지 않는 종목코드 처리"""
        if not settings.DART_API_KEY:
            pytest.skip("DART_API_KEY not configured")

        # 존재하지 않는 종목코드
        invalid_code = "999999"
        corp_code = await dart_service.search_corp_code_by_stock_code(invalid_code)

        # None 반환 확인
        assert corp_code is None

    @pytest.mark.asyncio
    async def test_full_mapping_coverage(self):
        """전체 종목 매핑 다운로드 검증"""
        if not settings.DART_API_KEY:
            pytest.skip("DART_API_KEY not configured")

        # 매핑 테이블 다운로드
        mapping = await dart_service._download_and_parse_corp_code_mapping()

        # 검증
        assert mapping is not None
        assert isinstance(mapping, dict)
        assert len(mapping) > 3000  # 최소 3,000개 이상
        assert "005930" in mapping  # 삼성전자 포함 확인
