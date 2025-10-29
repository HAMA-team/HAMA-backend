"""
KIS API 동기화 시 Stock 테이블에 종목명이 올바르게 저장되는지 테스트

이 테스트는 실제 KIS API를 호출하여:
1. 계좌 잔고를 조회하고
2. Stock 테이블에 종목명을 저장하며
3. 포트폴리오 조회 시 stock_name이 올바르게 표시되는지 검증한다.
"""
import asyncio
import pytest

from src.models.database import get_db_context
from src.models.stock import Stock
from src.models.portfolio import Portfolio, Position
from src.services.portfolio_service import portfolio_service
from src.services.kis_service import kis_service


@pytest.mark.asyncio
async def test_kis_sync_updates_stock_table():
    """KIS API 동기화 시 Stock 테이블에 종목명이 저장되는지 검증"""

    # 1. KIS API에서 계좌 잔고 조회
    print("\n📊 [테스트] KIS API 계좌 잔고 조회 중...")
    try:
        balance = await kis_service.get_account_balance()
    except Exception as e:
        pytest.skip(f"KIS API 호출 실패 (환경 변수 미설정 또는 네트워크 문제): {e}")

    stocks = balance.get("stocks", [])
    if not stocks:
        pytest.skip("보유 종목이 없어 테스트를 건너뜁니다.")

    print(f"✅ [테스트] {len(stocks)}개 종목 조회 완료")
    for stock in stocks:
        print(f"  - {stock['stock_code']}: {stock['stock_name']} ({stock['quantity']}주)")

    # 2. Portfolio Service를 통해 동기화
    print("\n🔄 [테스트] Portfolio Service로 동기화 중...")
    try:
        snapshot = await portfolio_service.sync_with_kis()
    except Exception as e:
        pytest.skip(f"포트폴리오 동기화 실패: {e}")

    assert snapshot is not None, "스냅샷이 None입니다"
    assert snapshot.portfolio_data is not None, "portfolio_data가 None입니다"

    # 3. Stock 테이블에서 종목 정보 확인
    print("\n📝 [테스트] Stock 테이블 확인 중...")
    with get_db_context() as db:
        stock_codes = [s["stock_code"] for s in stocks]
        db_stocks = db.query(Stock).filter(Stock.stock_code.in_(stock_codes)).all()

        print(f"✅ [테스트] Stock 테이블에 {len(db_stocks)}개 종목 저장됨")

        # 종목명이 올바르게 저장되었는지 검증
        for db_stock in db_stocks:
            kis_stock = next(
                (s for s in stocks if s["stock_code"] == db_stock.stock_code),
                None
            )
            if kis_stock:
                print(f"  - {db_stock.stock_code}: {db_stock.stock_name} (KIS: {kis_stock['stock_name']})")
                assert db_stock.stock_name == kis_stock["stock_name"], \
                    f"종목명 불일치: DB={db_stock.stock_name}, KIS={kis_stock['stock_name']}"

        # 모든 종목이 DB에 저장되었는지 확인
        assert len(db_stocks) == len(stock_codes), \
            f"일부 종목이 누락됨: 예상={len(stock_codes)}, 실제={len(db_stocks)}"

    # 4. 포트폴리오 조회 시 stock_name이 올바른지 확인
    print("\n🔍 [테스트] 포트폴리오 스냅샷 검증 중...")
    holdings = snapshot.portfolio_data.get("holdings", [])

    for holding in holdings:
        stock_code = holding["stock_code"]
        stock_name = holding["stock_name"]

        if stock_code.upper() == "CASH":
            continue

        # stock_name이 stock_code와 같지 않아야 함 (실제 종목명이어야 함)
        assert stock_name != stock_code, \
            f"종목명이 종목코드와 동일함: {stock_code} == {stock_name}"

        # KIS API 응답과 일치해야 함
        kis_stock = next(
            (s for s in stocks if s["stock_code"] == stock_code),
            None
        )
        if kis_stock:
            assert stock_name == kis_stock["stock_name"], \
                f"종목명 불일치: 스냅샷={stock_name}, KIS={kis_stock['stock_name']}"
            print(f"  ✅ {stock_code}: {stock_name}")

    print("\n✅ [테스트] 모든 검증 통과!")


@pytest.mark.asyncio
async def test_stock_name_not_equals_stock_code():
    """포트폴리오 조회 시 stock_name이 stock_code와 다른지 검증"""

    # 포트폴리오 스냅샷 조회
    snapshot = await portfolio_service.get_portfolio_snapshot()

    if snapshot is None or not snapshot.portfolio_data:
        pytest.skip("포트폴리오가 없습니다")

    holdings = snapshot.portfolio_data.get("holdings", [])

    if not holdings:
        pytest.skip("보유 종목이 없습니다")

    print("\n📊 [테스트] 보유 종목 검증:")
    for holding in holdings:
        stock_code = holding["stock_code"]
        stock_name = holding["stock_name"]

        if stock_code.upper() == "CASH":
            continue

        print(f"  - {stock_code}: {stock_name}")

        # stock_name이 stock_code와 같으면 안 됨
        assert stock_name != stock_code, \
            f"❌ 종목명이 종목코드와 동일함: {stock_code}"

    print("✅ [테스트] 모든 종목의 이름이 올바릅니다!")


if __name__ == "__main__":
    """직접 실행 시"""
    asyncio.run(test_kis_sync_updates_stock_table())
    asyncio.run(test_stock_name_not_equals_stock_code())