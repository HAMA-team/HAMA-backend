"""
KIS API 지수 조회 테스트
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.kis_service import kis_service
from src.services.stock_data_service import stock_data_service


async def test_kis_index_price():
    """KIS API 현재 지수 조회 테스트"""
    print("\n=== 1. KIS API 현재 지수 조회 테스트 ===")

    # KOSPI 지수 조회
    result = await kis_service.get_index_price("0001")

    if result:
        print(f"✅ KOSPI 현재 지수 조회 성공:")
        print(f"   - 지수명: {result['index_name']}")
        print(f"   - 현재가: {result['current_price']}")
        print(f"   - 전일대비: {result['change']} ({result['change_rate']}%)")
        print(f"   - 거래량: {result['volume']:,}")
    else:
        print("❌ KOSPI 현재 지수 조회 실패")


async def test_kis_index_daily():
    """KIS API 일자별 지수 조회 테스트"""
    print("\n=== 2. KIS API 일자별 지수 조회 테스트 ===")

    # KOSPI 60일 데이터 조회
    df = await kis_service.get_index_daily_price(
        index_code="0001",
        period="D",
        days=60
    )

    if df is not None and not df.empty:
        print(f"✅ KOSPI 일자별 지수 조회 성공:")
        print(f"   - 데이터 개수: {len(df)}일")
        print(f"   - 기간: {df.index[0]} ~ {df.index[-1]}")
        print(f"\n최근 5일 데이터:")
        print(df.tail())
    else:
        print("❌ KOSPI 일자별 지수 조회 실패")


async def test_stock_data_service_index():
    """StockDataService의 get_market_index 테스트 (KIS API 우선)"""
    print("\n=== 3. StockDataService.get_market_index 테스트 (KIS API 우선) ===")

    # KOSPI 지수 조회
    df = await stock_data_service.get_market_index("KOSPI", days=30)

    if df is not None and not df.empty:
        print(f"✅ KOSPI 지수 조회 성공 (StockDataService):")
        print(f"   - 데이터 개수: {len(df)}일")
        print(f"   - 기간: {df.index[0]} ~ {df.index[-1]}")
        print(f"\n최근 5일 데이터:")
        print(df.tail())

        # 데이터 구조 확인
        print(f"\n컬럼: {list(df.columns)}")
        print(f"최근 종가: {df['Close'].iloc[-1]:.2f}")
    else:
        print("❌ KOSPI 지수 조회 실패")


async def test_multiple_indices():
    """여러 지수 동시 조회 테스트"""
    print("\n=== 4. 여러 지수 동시 조회 테스트 ===")

    indices = ["KOSPI", "KOSDAQ", "KOSPI200"]

    for index_name in indices:
        print(f"\n{index_name} 조회 중...")
        df = await stock_data_service.get_market_index(index_name, days=7)

        if df is not None and not df.empty:
            latest_close = df['Close'].iloc[-1]
            print(f"✅ {index_name}: {latest_close:.2f} ({len(df)}일)")
        else:
            print(f"❌ {index_name}: 조회 실패")

        # Rate limit 방지를 위해 약간 대기
        await asyncio.sleep(0.5)


async def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("KIS API 지수 조회 테스트 시작")
    print("=" * 60)

    try:
        # 1. KIS API 현재 지수 조회
        await test_kis_index_price()
        await asyncio.sleep(1)

        # 2. KIS API 일자별 지수 조회
        await test_kis_index_daily()
        await asyncio.sleep(1)

        # 3. StockDataService를 통한 지수 조회
        await test_stock_data_service_index()
        await asyncio.sleep(1)

        # 4. 여러 지수 동시 조회
        await test_multiple_indices()

    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
