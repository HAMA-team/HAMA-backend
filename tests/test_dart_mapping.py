"""
DART 고유번호 매핑 검증 테스트

목적: 테스트 풀의 모든 종목이 DART에 올바르게 매핑되는지 확인
"""
import asyncio
import pytest
from src.services.dart_service import dart_service


# 테스트할 주요 종목 풀
TEST_STOCKS = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
    ("035420", "NAVER"),
    ("005380", "현대차"),
    ("051910", "LG화학"),
    ("006400", "삼성SDI"),
    ("035720", "카카오"),
    ("000270", "기아"),
    ("068270", "셀트리온"),
    ("207940", "삼성바이오로직스"),
    ("005490", "POSCO홀딩스"),
    ("012330", "현대모비스"),
    ("028260", "삼성물산"),
    ("105560", "KB금융"),
    ("055550", "신한지주"),
]


@pytest.mark.asyncio
async def test_all_stock_dart_mapping():
    """모든 테스트 종목의 DART 매핑 확인"""
    print("\n" + "=" * 80)
    print("📊 DART 고유번호 매핑 검증")
    print("=" * 80 + "\n")

    success_count = 0
    fail_count = 0
    mapping_results = []

    for stock_code, stock_name in TEST_STOCKS:
        try:
            corp_code = await dart_service.search_corp_code_by_stock_code(stock_code)

            if corp_code:
                # 기업 정보 조회로 매핑 검증
                company_info = await dart_service.get_company_info(corp_code)

                if company_info and company_info.get("status") == "000":
                    result = {
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "corp_code": corp_code,
                        "dart_name": company_info.get("corp_name", "N/A"),
                        "status": "✅ 성공"
                    }
                    success_count += 1
                else:
                    result = {
                        "stock_code": stock_code,
                        "stock_name": stock_name,
                        "corp_code": corp_code,
                        "dart_name": "조회 실패",
                        "status": "⚠️ 기업정보 조회 실패"
                    }
                    fail_count += 1
            else:
                result = {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "corp_code": None,
                    "dart_name": "매핑 없음",
                    "status": "❌ 매핑 실패"
                }
                fail_count += 1

            mapping_results.append(result)

        except Exception as e:
            result = {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "corp_code": None,
                "dart_name": f"에러: {e}",
                "status": "❌ 에러"
            }
            mapping_results.append(result)
            fail_count += 1

    # 결과 출력
    print(f"{'종목코드':<10} {'종목명':<15} {'고유번호':<12} {'DART명':<20} {'상태'}")
    print("-" * 80)

    for result in mapping_results:
        print(
            f"{result['stock_code']:<10} "
            f"{result['stock_name']:<15} "
            f"{result['corp_code'] or 'N/A':<12} "
            f"{result['dart_name']:<20} "
            f"{result['status']}"
        )

    print("\n" + "=" * 80)
    print(f"결과: ✅ 성공 {success_count}개, ❌ 실패 {fail_count}개 / 총 {len(TEST_STOCKS)}개")
    print("=" * 80)

    # 적어도 80% 이상 매핑되어야 테스트 통과
    assert success_count >= len(TEST_STOCKS) * 0.8, \
        f"DART 매핑 성공률이 80% 미만입니다: {success_count}/{len(TEST_STOCKS)}"


@pytest.mark.asyncio
async def test_dart_mapping_cache():
    """DART 매핑 캐시 효과 테스트"""
    import time

    stock_code = "005930"

    # 첫 번째 호출 (캐시 미스 - 매핑 테이블 다운로드)
    start = time.time()
    corp_code_1 = await dart_service.search_corp_code_by_stock_code(stock_code)
    time_1 = time.time() - start

    # 두 번째 호출 (캐시 히트)
    start = time.time()
    corp_code_2 = await dart_service.search_corp_code_by_stock_code(stock_code)
    time_2 = time.time() - start

    assert corp_code_1 == corp_code_2 == "00126380"

    print(f"\n✅ DART 매핑 캐시 테스트")
    print(f"   첫 번째 호출: {time_1:.3f}초")
    print(f"   두 번째 호출: {time_2:.3f}초")

    if time_2 > 0.001:  # 두 번째 호출이 충분히 측정 가능한 경우만
        speedup = time_1 / time_2
        print(f"   속도 향상: {speedup:.1f}배\n")
        assert speedup > 2, "캐시 효과가 충분하지 않습니다"
    else:
        print(f"   ⚡ 두 호출 모두 매우 빠름 (캐시 이미 존재)\n")


@pytest.mark.asyncio
async def test_invalid_stock_code_dart_mapping():
    """존재하지 않는 종목코드 처리"""
    invalid_code = "999999"

    corp_code = await dart_service.search_corp_code_by_stock_code(invalid_code)

    assert corp_code is None, "존재하지 않는 종목은 None을 반환해야 합니다"

    print(f"\n✅ 잘못된 종목코드 처리: {invalid_code} -> None")


if __name__ == "__main__":
    """직접 실행"""
    async def main():
        print("\n🔍 DART 매핑 검증 테스트 시작\n")

        # 1. 전체 매핑 테스트
        await test_all_stock_dart_mapping()

        # 2. 캐시 효과 테스트
        await test_dart_mapping_cache()

        # 3. 잘못된 코드 처리
        await test_invalid_stock_code_dart_mapping()

        print("\n✅ 모든 DART 매핑 테스트 완료!\n")

    asyncio.run(main())
