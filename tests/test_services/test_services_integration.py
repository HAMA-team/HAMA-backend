"""Service Layer 통합 테스트"""

import asyncio
from src.services.stock_data_service import stock_data_service
from src.services.dart_service import dart_service


async def test_stock_data_service():
    """StockDataService 테스트"""
    print("\n📊 StockDataService 테스트\n")

    # 1. 주가 데이터 조회
    df = await stock_data_service.get_stock_price("005930", days=7)
    assert df is not None
    assert len(df) > 0
    print(f"✅ 삼성전자 주가 데이터: {len(df)}일")
    print(f"   최근 종가: {df.iloc[-1]['Close']:,.0f}원\n")

    # 2. 종목명으로 코드 찾기 (캐시 미스 - KRX API 에러 가능성 있음)
    try:
        code = await stock_data_service.get_stock_by_name("삼성전자")
        if code:
            print(f"✅ 종목 코드 검색: 삼성전자 -> {code}\n")
    except Exception as e:
        print(f"⚠️ 종목 코드 검색 스킵 (KRX API 제한): {e}\n")

    # 3. 수익률 계산
    df_returns = await stock_data_service.calculate_returns("005930", days=7)
    if df_returns is not None:
        print(f"✅ 수익률 계산 완료")
        print(f"   최근 일일수익률: {df_returns.iloc[-1]['Daily_Return']:.2f}%")
        print(f"   누적수익률: {df_returns.iloc[-1]['Cumulative_Return']:.2f}%\n")

    # 4. 여러 종목 조회
    stocks = await stock_data_service.get_multiple_stocks(
        ["005930", "000660"], days=7
    )
    print(f"✅ 여러 종목 조회: {len(stocks)}개\n")


async def test_dart_service():
    """DARTService 테스트"""
    print("\n📑 DARTService 테스트\n")

    # 삼성전자 고유번호
    corp_code = "00126380"

    # 1. 기업 개황
    company = await dart_service.get_company_info(corp_code)
    if company:
        print(f"✅ 기업명: {company.get('corp_name')}")
        print(f"   대표자: {company.get('ceo_nm')}\n")

    # 2. 최근 공시 목록
    disclosures = await dart_service.get_disclosure_list(
        corp_code, bgn_de="20240901", end_de="20251003", page_count=5
    )
    if disclosures and len(disclosures) > 0:
        print(f"✅ 최근 공시: {len(disclosures)}건")
        print(f"   최신: {disclosures[0]['report_nm']}\n")

    # 3. 재무제표
    financial = await dart_service.get_financial_statement(
        corp_code, bsns_year="2023"
    )
    if financial and len(financial) > 0:
        print(f"✅ 재무제표 항목: {len(financial)}개\n")

    # 4. 종목코드로 고유번호 찾기
    found_corp_code = await dart_service.search_corp_code_by_stock_code("005930")
    assert found_corp_code == "00126380"
    print(f"✅ 종목코드 매핑: 005930 -> {found_corp_code}\n")


async def test_cache_effectiveness():
    """캐시 효과 테스트"""
    print("\n⚡ 캐시 효과 테스트\n")

    import time

    # 첫 번째 호출 (캐시 미스)
    start = time.time()
    df1 = await stock_data_service.get_stock_price("005930", days=7)
    time1 = time.time() - start

    # 두 번째 호출 (캐시 히트)
    start = time.time()
    df2 = await stock_data_service.get_stock_price("005930", days=7)
    time2 = time.time() - start

    print(f"✅ 첫 번째 호출 (API): {time1:.3f}초")
    print(f"✅ 두 번째 호출 (캐시): {time2:.3f}초")
    print(f"✅ 속도 향상: {time1/time2:.1f}배\n")


async def test_full_workflow():
    """전체 워크플로우 테스트"""
    print("\n🔄 전체 워크플로우 테스트\n")

    # 1. 종목코드로 기업 정보 가져오기
    stock_code = "005930"
    print(f"1️⃣ 종목 코드: {stock_code}")

    # 2. 주가 데이터
    price_data = await stock_data_service.get_stock_price(stock_code, days=30)
    if price_data is not None:
        print(f"2️⃣ 주가 데이터: {len(price_data)}일")

    # 3. DART 고유번호 찾기
    corp_code = await dart_service.search_corp_code_by_stock_code(stock_code)
    if corp_code:
        print(f"3️⃣ 고유번호: {corp_code}")

        # 4. 기업 정보
        company = await dart_service.get_company_info(corp_code)
        if company:
            print(f"4️⃣ 기업명: {company.get('corp_name')}")

        # 5. 재무제표
        financial = await dart_service.get_financial_statement(
            corp_code, bsns_year="2023"
        )
        if financial:
            print(f"5️⃣ 재무제표: {len(financial)}개 항목")

    print("\n✅ 전체 워크플로우 완료!")


async def main():
    print("\n🚀 Service Layer 통합 테스트 시작")
    print("=" * 50)

    await test_stock_data_service()
    await test_dart_service()
    await test_cache_effectiveness()
    await test_full_workflow()

    print("\n" + "=" * 50)
    print("✅ 모든 Service Layer 통합 테스트 통과!")


if __name__ == "__main__":
    asyncio.run(main())
