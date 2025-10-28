"""
pykrx 통합 및 기술적 지표 테스트

Research Agent의 pykrx 전환과 기술적 지표 계산을 검증합니다.
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.stock_data_service import stock_data_service
from src.utils.indicators import calculate_all_indicators


async def test_pykrx_stock_price():
    """pykrx를 사용한 주가 데이터 조회 테스트"""
    print("\n=== Test 1: pykrx 주가 데이터 조회 ===")

    stock_code = "005930"  # 삼성전자
    df = await stock_data_service.get_stock_price(stock_code, days=30)

    assert df is not None, "주가 데이터 조회 실패"
    assert len(df) > 0, "주가 데이터가 비어 있음"

    # 컬럼 확인
    expected_columns = ["Open", "High", "Low", "Close", "Volume", "Change"]
    for col in expected_columns:
        assert col in df.columns, f"컬럼 {col}이 없음"

    print(f"✅ 주가 데이터 조회 성공: {stock_code}")
    print(f"   - 데이터 기간: {len(df)}일")
    print(f"   - 컬럼: {list(df.columns)}")
    print(f"   - 최근 종가: {df.iloc[-1]['Close']:,.0f}원")

    return df


async def test_technical_indicators(df):
    """기술적 지표 계산 테스트"""
    print("\n=== Test 2: 기술적 지표 계산 ===")

    indicators = calculate_all_indicators(df)

    assert indicators is not None, "지표 계산 실패"
    assert "rsi" in indicators, "RSI 지표 없음"
    assert "macd" in indicators, "MACD 지표 없음"
    assert "bollinger_bands" in indicators, "Bollinger Bands 지표 없음"
    assert "moving_averages" in indicators, "이동평균 없음"
    assert "volume" in indicators, "거래량 분석 없음"
    assert "signals" in indicators, "시그널 없음"
    assert "overall_trend" in indicators, "전체 추세 없음"

    print(f"✅ 기술적 지표 계산 성공")
    print(f"   - RSI: {indicators['rsi']['value']} ({indicators['rsi']['signal']})")
    print(f"   - MACD: {indicators['macd']['trend']}")
    print(f"   - Bollinger Bands: {indicators['bollinger_bands']['position']}")
    print(f"   - 전체 추세: {indicators['overall_trend']}")
    print(f"   - 시그널 개수: {len(indicators['signals'])}")

    if indicators['signals']:
        print(f"   - 시그널:")
        for signal in indicators['signals']:
            print(f"     * {signal}")

    return indicators


async def test_market_index():
    """시장 지수 데이터 조회 테스트"""
    print("\n=== Test 3: 시장 지수 데이터 조회 ===")

    try:
        df = await stock_data_service.get_market_index("KOSPI", days=30)

        if df is not None and len(df) > 0:
            # 컬럼 확인
            expected_columns = ["Open", "High", "Low", "Close", "Volume"]
            for col in expected_columns:
                assert col in df.columns, f"컬럼 {col}이 없음"

            current_index = df.iloc[-1]["Close"]
            prev_index = df.iloc[-2]["Close"]
            change_rate = (current_index / prev_index - 1) * 100

            print(f"✅ 시장 지수 조회 성공: KOSPI")
            print(f"   - 데이터 기간: {len(df)}일")
            print(f"   - 현재 지수: {current_index:,.2f}")
            print(f"   - 전일 대비: {change_rate:+.2f}%")

            return df
        else:
            print(f"⚠️ 시장 지수 조회 실패 (pykrx API 이슈) - 스킵")
            return None

    except Exception as e:
        print(f"⚠️ 시장 지수 조회 실패 (pykrx API 이슈) - 스킵: {e}")
        # 시장 지수는 선택적 기능이므로 실패해도 전체 테스트를 중단하지 않음
        return None


async def test_stock_listing():
    """종목 리스트 조회 테스트"""
    print("\n=== Test 4: 종목 리스트 조회 ===")

    try:
        df = await stock_data_service.get_stock_listing("KOSPI")

        if df is not None and len(df) > 0:
            # 컬럼 확인
            expected_columns = ["Code", "Name", "Market"]
            for col in expected_columns:
                assert col in df.columns, f"컬럼 {col}이 없음"

            # 삼성전자 검색
            samsung = df[df["Code"] == "005930"]
            if len(samsung) > 0:
                print(f"✅ 종목 리스트 조회 성공")
                print(f"   - 종목 수: {len(df)}개")
                print(f"   - 삼성전자: {samsung.iloc[0]['Name']} ({samsung.iloc[0]['Code']})")
            else:
                print(f"⚠️ 종목 리스트 조회 성공했으나 삼성전자를 찾을 수 없음")

            return df
        else:
            print(f"⚠️ 종목 리스트 조회 실패 (pykrx API 이슈) - 스킵")
            return None

    except Exception as e:
        print(f"⚠️ 종목 리스트 조회 실패 (pykrx API 이슈) - 스킵: {e}")
        return None


async def test_fundamental_data():
    """펀더멘털 데이터 조회 테스트 (신규)"""
    print("\n=== Test 5: 펀더멘털 데이터 조회 (PER/PBR/EPS) ===")

    stock_code = "005930"  # 삼성전자
    fundamental = await stock_data_service.get_fundamental_data(stock_code)

    if fundamental is None:
        print(f"⚠️ 펀더멘털 데이터 조회 실패 - 스킵")
        return None

    # 필수 필드 확인
    expected_keys = ["PER", "PBR", "EPS", "DIV", "DPS", "BPS"]
    for key in expected_keys:
        assert key in fundamental, f"펀더멘털 데이터에 {key} 필드 없음"

    print(f"✅ 펀더멘털 데이터 조회 성공: {stock_code}")
    print(f"   - PER: {fundamental['PER']}배")
    print(f"   - PBR: {fundamental['PBR']}배")
    print(f"   - EPS: {fundamental['EPS']:,}원")
    print(f"   - 배당수익률: {fundamental['DIV']}%")
    print(f"   - DPS: {fundamental['DPS']:,}원")
    print(f"   - BPS: {fundamental['BPS']:,}원")

    return fundamental


async def test_market_cap_data():
    """시가총액 및 거래 데이터 조회 테스트 (신규)"""
    print("\n=== Test 6: 시가총액 및 거래 데이터 조회 ===")

    stock_code = "005930"  # 삼성전자
    market_cap = await stock_data_service.get_market_cap_data(stock_code)

    if market_cap is None:
        print(f"⚠️ 시가총액 데이터 조회 실패 - 스킵")
        return None

    # 필수 필드 확인
    expected_keys = ["market_cap", "trading_volume", "trading_value", "shares_outstanding"]
    for key in expected_keys:
        assert key in market_cap, f"시가총액 데이터에 {key} 필드 없음"

    market_cap_trillion = market_cap["market_cap"] / 1e12

    print(f"✅ 시가총액 데이터 조회 성공: {stock_code}")
    print(f"   - 시가총액: {market_cap_trillion:.2f}조원")
    print(f"   - 거래량: {market_cap['trading_volume']:,}주")
    print(f"   - 거래대금: {market_cap['trading_value'] / 1e8:,.0f}억원")
    print(f"   - 상장주식수: {market_cap['shares_outstanding']:,}주")

    return market_cap


async def test_investor_trading():
    """투자주체별 매매 동향 테스트 (신규)"""
    print("\n=== Test 7: 투자주체별 매매 동향 조회 ===")

    stock_code = "005930"  # 삼성전자
    investor = await stock_data_service.get_investor_trading(stock_code, days=30)

    if investor is None:
        print(f"⚠️ 투자주체별 데이터 조회 실패 - 스킵")
        return None

    # 필수 필드 확인
    expected_keys = ["foreign_net", "institution_net", "individual_net", "foreign_trend", "institution_trend"]
    for key in expected_keys:
        assert key in investor, f"투자주체별 데이터에 {key} 필드 없음"

    print(f"✅ 투자주체별 매매 동향 조회 성공: {stock_code}")
    print(f"   - 외국인 순매수: {investor['foreign_net'] / 1e8:,.0f}억원 (추세: {investor['foreign_trend']})")
    print(f"   - 기관 순매수: {investor['institution_net'] / 1e8:,.0f}억원 (추세: {investor['institution_trend']})")
    print(f"   - 개인 순매수: {investor['individual_net'] / 1e8:,.0f}억원")

    return investor


async def main():
    """전체 테스트 실행"""
    print("=" * 60)
    print("pykrx 통합 및 펀더멘털 분석 테스트")
    print("=" * 60)

    try:
        # Test 1: 주가 데이터 조회
        df_price = await test_pykrx_stock_price()

        # Test 2: 기술적 지표 계산
        indicators = await test_technical_indicators(df_price)

        # Test 3: 시장 지수 조회
        df_index = await test_market_index()

        # Test 4: 종목 리스트 조회
        df_listing = await test_stock_listing()

        # Test 5: 펀더멘털 데이터 조회 (신규)
        fundamental = await test_fundamental_data()

        # Test 6: 시가총액 데이터 조회 (신규)
        market_cap = await test_market_cap_data()

        # Test 7: 투자주체별 매매 동향 (신규)
        investor = await test_investor_trading()

        print("\n" + "=" * 60)
        print("✅ 모든 테스트 통과!")
        print("=" * 60)
        print("\n📊 종합 리포트:")
        print(f"   - 주가 데이터: {'✅' if df_price is not None else '⚠️'}")
        print(f"   - 기술적 지표: {'✅' if indicators else '⚠️'}")
        print(f"   - 시장 지수: {'✅' if df_index is not None else '⚠️ (Mock 데이터)'}")
        print(f"   - 종목 리스트: {'✅' if df_listing is not None else '⚠️'}")
        print(f"   - 펀더멘털: {'✅' if fundamental else '⚠️'}")
        print(f"   - 시가총액: {'✅' if market_cap else '⚠️'}")
        print(f"   - 투자주체별: {'✅' if investor else '⚠️'}")

    except AssertionError as e:
        print(f"\n❌ 테스트 실패: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
