"""FinanceDataReader 설치 및 기능 테스트"""

import pytest
import FinanceDataReader as fdr
from datetime import datetime, timedelta


def test_fdr_import():
    """FinanceDataReader 임포트 테스트"""
    assert fdr is not None


def test_get_stock_price():
    """주가 데이터 조회 테스트 (삼성전자 최근 30일)"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    df = fdr.DataReader("005930", start=start_date, end=end_date)

    assert df is not None
    assert len(df) > 0
    assert "Open" in df.columns
    assert "High" in df.columns
    assert "Low" in df.columns
    assert "Close" in df.columns
    assert "Volume" in df.columns

    print(f"✅ 조회된 데이터: {len(df)}일")
    print(f"✅ 최근 종가: {df.iloc[-1]['Close']:,.0f}원")
    print(f"✅ 최근 거래량: {df.iloc[-1]['Volume']:,.0f}주")


def test_get_multiple_stocks():
    """여러 종목 데이터 조회 테스트"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    # 삼성전자, SK하이닉스, NAVER
    stocks = ["005930", "000660", "035420"]

    for stock_code in stocks:
        df = fdr.DataReader(stock_code, start=start_date, end=end_date)
        assert df is not None
        assert len(df) > 0

    print(f"✅ {len(stocks)}개 종목 데이터 조회 성공")


def test_get_stock_with_change():
    """주가 변동률 계산 테스트"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    df = fdr.DataReader("005930", start=start_date, end=end_date)

    assert df is not None
    assert len(df) > 0

    # 변동률 계산
    df["Change"] = df["Close"].pct_change() * 100

    print(f"✅ 전일 대비 변동률: {df.iloc[-1]['Change']:.2f}%")


if __name__ == "__main__":
    print("\n🔍 FinanceDataReader 테스트 시작\n")

    test_fdr_import()
    print("1️⃣ 임포트 테스트 통과\n")

    test_get_stock_price()
    print("2️⃣ 주가 데이터 조회 테스트 통과\n")

    test_get_multiple_stocks()
    print("3️⃣ 여러 종목 조회 테스트 통과\n")

    test_get_stock_with_change()
    print("4️⃣ 변동률 계산 테스트 통과\n")

    print("✅ 모든 테스트 통과!")
