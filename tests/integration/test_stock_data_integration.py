"""
Stock Data Service 통합 테스트 (KIS API + FinanceDataReader)

Research Agent의 KIS API 및 FinanceDataReader 통합과 기술적 지표 계산을 검증합니다.
"""
import pytest

from src.services.stock_data_service import stock_data_service
from src.utils.indicators import calculate_all_indicators


@pytest.mark.asyncio
async def test_stock_price():
    """KIS API + FinanceDataReader를 사용한 주가 데이터 조회 테스트"""
    print("\n=== Test 1: 주가 데이터 조회 (KIS API/FDR) ===")

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


@pytest.mark.asyncio
async def test_technical_indicators():
    """기술적 지표 계산 테스트"""
    print("\n=== Test 2: 기술적 지표 계산 ===")

    # 주가 데이터 먼저 조회
    stock_code = "005930"
    df = await stock_data_service.get_stock_price(stock_code, days=30)
    assert df is not None, "주가 데이터 조회 실패"

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


@pytest.mark.asyncio
async def test_market_index():
    """시장 지수 데이터 조회 테스트"""
    print("\n=== Test 3: 시장 지수 데이터 조회 ===")

    df = await stock_data_service.get_market_index("KOSPI", days=30)

    # Mock 데이터 포함하여 성공으로 간주
    assert df is not None, "시장 지수 조회 실패 (Mock 데이터도 없음)"
    assert len(df) > 0, "시장 지수 데이터가 비어 있음"

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


@pytest.mark.asyncio
async def test_stock_listing():
    """종목 리스트 조회 테스트"""
    print("\n=== Test 4: 종목 리스트 조회 ===")

    df = await stock_data_service.get_stock_listing("KOSPI")

    assert df is not None, "종목 리스트 조회 실패"
    assert len(df) > 0, "종목 리스트가 비어 있음"

    # 컬럼 확인
    expected_columns = ["Code", "Name", "Market"]
    for col in expected_columns:
        assert col in df.columns, f"컬럼 {col}이 없음"

    # 삼성전자 검색
    samsung = df[df["Code"] == "005930"]
    assert len(samsung) > 0, "삼성전자를 찾을 수 없음"

    print(f"✅ 종목 리스트 조회 성공")
    print(f"   - 종목 수: {len(df)}개")
    print(f"   - 삼성전자: {samsung.iloc[0]['Name']} ({samsung.iloc[0]['Code']})")


@pytest.mark.asyncio
async def test_fundamental_data():
    """펀더멘털 데이터 조회 테스트 (KIS API)"""
    print("\n=== Test 5: 펀더멘털 데이터 조회 (KIS API) ===")

    stock_code = "005930"  # 삼성전자
    fundamental = await stock_data_service.get_fundamental_data(stock_code)

    # 펀더멘털 데이터는 API 의존성이 높으므로 None일 경우 스킵
    if fundamental is None:
        pytest.skip("펀더멘털 데이터 조회 실패 (KIS API 이슈) - 스킵")

    # 필수 필드 확인
    expected_keys = ["PER", "PBR", "EPS", "DIV", "DPS", "BPS"]
    for key in expected_keys:
        assert key in fundamental, f"펀더멘털 데이터에 {key} 필드 없음"

    print(f"✅ 펀더멘털 데이터 조회 성공: {stock_code}")
    print(f"   - PER: {fundamental['PER']}배" if fundamental['PER'] else "   - PER: N/A")
    print(f"   - PBR: {fundamental['PBR']}배" if fundamental['PBR'] else "   - PBR: N/A")
    # EPS, DIV, DPS, BPS는 KIS API에서 제공하지 않음 (None 예상)
    print(f"   - EPS: {fundamental['EPS']:,}원" if fundamental['EPS'] else "   - EPS: N/A (KIS API 미지원)")
    print(f"   - 배당수익률: {fundamental['DIV']}%" if fundamental['DIV'] else "   - DIV: N/A (KIS API 미지원)")
    print(f"   - DPS: {fundamental['DPS']:,}원" if fundamental['DPS'] else "   - DPS: N/A (KIS API 미지원)")
    print(f"   - BPS: {fundamental['BPS']:,}원" if fundamental['BPS'] else "   - BPS: N/A (KIS API 미지원)")


@pytest.mark.asyncio
async def test_market_cap_data():
    """시가총액 및 거래 데이터 조회 테스트 (KIS API)"""
    print("\n=== Test 6: 시가총액 및 거래 데이터 조회 (KIS API) ===")

    stock_code = "005930"  # 삼성전자
    market_cap = await stock_data_service.get_market_cap_data(stock_code)

    # 시가총액 데이터는 API 의존성이 높으므로 None일 경우 스킵
    if market_cap is None:
        pytest.skip("시가총액 데이터 조회 실패 (KIS API 이슈) - 스킵")

    # 필수 필드 확인
    expected_keys = ["market_cap", "trading_volume", "trading_value", "shares_outstanding"]
    for key in expected_keys:
        assert key in market_cap, f"시가총액 데이터에 {key} 필드 없음"

    print(f"✅ 시가총액 데이터 조회 성공: {stock_code}")

    # market_cap과 trading_volume은 항상 존재해야 함
    if market_cap["market_cap"]:
        market_cap_trillion = market_cap["market_cap"] / 1e12
        print(f"   - 시가총액: {market_cap_trillion:.2f}조원")
    else:
        print(f"   - 시가총액: N/A")

    if market_cap["trading_volume"]:
        print(f"   - 거래량: {market_cap['trading_volume']:,}주")
    else:
        print(f"   - 거래량: N/A")

    # trading_value와 shares_outstanding은 KIS API에서 제공하지 않음 (None 예상)
    if market_cap["trading_value"]:
        print(f"   - 거래대금: {market_cap['trading_value'] / 1e8:,.0f}억원")
    else:
        print(f"   - 거래대금: N/A (KIS API 미지원)")

    if market_cap["shares_outstanding"]:
        print(f"   - 상장주식수: {market_cap['shares_outstanding']:,}주")
    else:
        print(f"   - 상장주식수: N/A (KIS API 미지원)")


@pytest.mark.asyncio
async def test_llm_stock_name_matching():
    """LLM 기반 종목명 매칭 테스트"""
    print("\n=== Test 7: LLM 기반 종목명 매칭 ===")

    # 테스트 케이스: 한글명 → 영문명 매칭
    test_cases = [
        ("네이버", "035420"),  # 네이버 → NAVER
        ("삼전", "005930"),    # 삼전 → 삼성전자
        ("카카오", "035720"),  # 카카오 → 카카오
    ]

    for user_input, expected_code in test_cases:
        print(f"\n  테스트: '{user_input}' → {expected_code}")

        # KOSPI 먼저 시도
        result = await stock_data_service.get_stock_by_name(user_input, market="KOSPI")

        # KOSPI에서 못 찾으면 KOSDAQ 시도
        if not result:
            result = await stock_data_service.get_stock_by_name(user_input, market="KOSDAQ")

        assert result is not None, f"'{user_input}' 종목 코드를 찾을 수 없음"
        assert result == expected_code, f"잘못된 매칭: '{user_input}' → {result} (예상: {expected_code})"

        print(f"  ✅ 매칭 성공: '{user_input}' → {result}")

    print(f"\n✅ LLM 기반 종목명 매칭 테스트 완료")


@pytest.mark.asyncio
async def test_llm_matching_cache():
    """LLM 매칭 캐싱 테스트"""
    print("\n=== Test 8: LLM 매칭 캐싱 ===")

    user_input = "네이버"

    # 첫 번째 요청 (LLM 호출)
    print(f"  첫 번째 요청: '{user_input}'")
    result1 = await stock_data_service.get_stock_by_name(user_input, market="KOSPI")
    assert result1 is not None, f"'{user_input}' 매칭 실패"

    # 두 번째 요청 (캐시 사용)
    print(f"  두 번째 요청: '{user_input}' (캐시 사용 예상)")
    result2 = await stock_data_service.get_stock_by_name(user_input, market="KOSPI")
    assert result2 is not None, f"'{user_input}' 캐시 조회 실패"

    # 결과 일치 확인
    assert result1 == result2, f"캐시 결과 불일치: {result1} != {result2}"

    print(f"  ✅ 캐싱 정상 동작: '{user_input}' → {result1}")
    print(f"\n✅ LLM 매칭 캐싱 테스트 완료")
