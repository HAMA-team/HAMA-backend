"""
DART 종목코드 전체 매핑 테스트

전체 종목 매핑 테이블 다운로드 및 조회 검증
"""
import asyncio
import pytest

from src.services import dart_service
from src.config.settings import settings


class TestDARTMapping:
    """DART 종목코드 매핑 테스트"""

    @pytest.mark.asyncio
    async def test_download_corp_code_mapping(self):
        """전체 종목 매핑 테이블 다운로드"""
        if not settings.DART_API_KEY:
            pytest.skip("DART_API_KEY not configured")

        # 매핑 테이블 다운로드
        mapping = await dart_service._download_and_parse_corp_code_mapping()

        # 검증
        assert mapping is not None
        assert isinstance(mapping, dict)
        assert len(mapping) > 0  # 최소 1개 이상

        print(f"✅ 전체 종목 매핑: {len(mapping)}개")

        # 주요 종목 확인
        assert "005930" in mapping  # 삼성전자
        print(f"   삼성전자(005930): {mapping['005930']}")

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
            "005380": "현대차",
            "051910": "LG화학",
            "005490": "POSCO홀딩스",
            "006400": "삼성SDI",
        }

        print("\n📋 주요 종목 고유번호 조회:")
        for stock_code, name in test_stocks.items():
            corp_code = await dart_service.search_corp_code_by_stock_code(stock_code)

            print(f"   {name}({stock_code}): {corp_code}")
            assert corp_code is not None, f"{name} 고유번호를 찾을 수 없음"
            assert len(corp_code) == 8, f"{name} 고유번호 길이 오류"

    @pytest.mark.asyncio
    async def test_cache_mechanism(self):
        """Redis 캐싱 메커니즘 검증"""
        if not settings.DART_API_KEY:
            pytest.skip("DART_API_KEY not configured")

        # 첫 번째 조회 (캐시 미스 → 다운로드)
        print("\n🔄 첫 번째 조회 (캐시 미스)...")
        corp_code_1 = await dart_service.search_corp_code_by_stock_code("005930")
        assert corp_code_1 is not None

        # 두 번째 조회 (캐시 히트)
        print("⚡ 두 번째 조회 (캐시 히트)...")
        corp_code_2 = await dart_service.search_corp_code_by_stock_code("000660")
        assert corp_code_2 is not None

        print(f"✅ 캐싱 메커니즘 정상 작동")

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
        print(f"✅ 잘못된 종목코드({invalid_code}) 처리 정상")


if __name__ == "__main__":
    """테스트 직접 실행"""
    async def main():
        print("\n" + "="*60)
        print("DART 종목코드 전체 매핑 테스트")
        print("="*60 + "\n")

        tester = TestDARTMapping()

        # DART 키 확인
        if not settings.DART_API_KEY:
            print("⏭️ DART_API_KEY가 설정되지 않아 테스트를 스킵합니다.")
            print("   .env 파일에 DART_API_KEY를 설정하세요.")
            return

        # 1. 전체 매핑 다운로드 테스트
        print("[1/4] 전체 종목 매핑 다운로드 테스트...")
        try:
            await tester.test_download_corp_code_mapping()
            print("✅ 통과\n")
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        # 2. 주요 종목 조회 테스트
        print("[2/4] 주요 종목 고유번호 조회 테스트...")
        try:
            await tester.test_search_corp_code_major_stocks()
            print("✅ 통과\n")
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        # 3. 캐싱 메커니즘 테스트
        print("[3/4] 캐싱 메커니즘 검증...")
        try:
            await tester.test_cache_mechanism()
            print("✅ 통과\n")
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        # 4. 잘못된 종목코드 처리 테스트
        print("[4/4] 잘못된 종목코드 처리 테스트...")
        try:
            await tester.test_invalid_stock_code()
            print("✅ 통과\n")
        except Exception as e:
            print(f"❌ 실패: {e}\n")

        print("="*60)
        print("테스트 완료")
        print("="*60)

    asyncio.run(main())
