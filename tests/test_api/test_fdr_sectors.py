"""
FinanceDataReader 섹터 지수 데이터 확인

주요 섹터:
1. IT/전기전자
2. 반도체
3. 헬스케어/바이오
4. 금융
5. 자동차
6. 화학
7. 철강
8. 에너지
9. 건설
10. 소비재
"""

import FinanceDataReader as fdr
from datetime import datetime, timedelta
import pandas as pd

# KOSPI 섹터 지수 코드 매핑
SECTOR_INDICES = {
    # KRX 섹터 지수
    "에너지화학": "KS11",  # KOSPI
    "IT": "KRX.001",  # IT 지수 (예시)
    "금융": "KRX.002",  # 금융 지수
    # 기타 섹터는 확인 필요
}

# 일부 대표 종목으로 섹터 대표
SECTOR_STOCKS = {
    "IT/전기전자": ["005930", "000660"],  # 삼성전자, SK하이닉스
    "반도체": ["000660"],  # SK하이닉스
    "헬스케어": ["207940"],  # 삼성바이오로직스
    "금융": ["055550"],  # 신한지주
    "자동차": ["005380", "000270"],  # 현대차, 기아
    "화학": ["051910"],  # LG화학
    "철강": ["005490"],  # POSCO홀딩스
    "에너지": ["096770"],  # SK이노베이션
    "건설": ["000720"],  # 현대건설
    "소비재": ["271560"],  # 오리온
}


def check_kospi_indices():
    """KOSPI 및 관련 지수 확인"""
    print("\n" + "="*80)
    print("📊 KOSPI 및 주요 지수 데이터 확인")
    print("="*80)

    indices = {
        "KOSPI": "KS11",
        "KOSDAQ": "KQ11",
        "KRX100": "KRX100",
    }

    end = datetime.now()
    start = end - timedelta(days=30)

    for name, code in indices.items():
        try:
            df = fdr.DataReader(code, start, end)
            if not df.empty:
                latest = df.iloc[-1]
                print(f"\n✅ {name} ({code})")
                print(f"   최근 종가: {latest['Close']:,.2f}")
                print(f"   거래량: {latest['Volume']:,.0f}")
                print(f"   날짜: {df.index[-1].strftime('%Y-%m-%d')}")
        except Exception as e:
            print(f"\n❌ {name} ({code}): {e}")


def check_sector_via_stocks():
    """대표 종목으로 섹터 데이터 확인"""
    print("\n" + "="*80)
    print("📊 섹터별 대표 종목 데이터 확인")
    print("="*80)

    end = datetime.now()
    start = end - timedelta(days=30)

    sector_performance = {}

    for sector, stocks in SECTOR_STOCKS.items():
        print(f"\n📌 {sector} 섹터:")
        sector_returns = []

        for stock_code in stocks[:2]:  # 최대 2개 종목만
            try:
                df = fdr.DataReader(stock_code, start, end)
                if not df.empty and len(df) > 1:
                    # 30일 수익률 계산
                    first_price = df.iloc[0]['Close']
                    last_price = df.iloc[-1]['Close']
                    returns = ((last_price - first_price) / first_price) * 100

                    sector_returns.append(returns)

                    # 종목명 조회 시도
                    stock_name = stock_code
                    try:
                        stock_list = fdr.StockListing('KRX')
                        stock_info = stock_list[stock_list['Code'] == stock_code]
                        if not stock_info.empty:
                            stock_name = stock_info.iloc[0]['Name']
                    except:
                        pass

                    print(f"   - {stock_name} ({stock_code}): {returns:+.2f}% (30일)")
            except Exception as e:
                print(f"   - {stock_code}: Error - {str(e)[:50]}")

        # 섹터 평균 수익률
        if sector_returns:
            avg_return = sum(sector_returns) / len(sector_returns)
            sector_performance[sector] = avg_return
            print(f"   ➡️ 섹터 평균: {avg_return:+.2f}%")

    return sector_performance


def check_krx_sector_indices():
    """KRX 섹터 지수 확인 (가능한 경우)"""
    print("\n" + "="*80)
    print("📊 KRX 섹터 지수 확인")
    print("="*80)

    # KRX 섹터 지수 코드 (예상)
    possible_codes = [
        "KS001",  # KOSPI 대형주
        "KS002",  # KOSPI 중형주
        "KS003",  # KOSPI 소형주
        "1001",   # 에너지/화학
        "1002",   # 비철금속
        "1003",   # 철강
        "1004",   # 건설
        "1005",   # 기계
        "1006",   # 조선
        "1007",   # 상사/자본재
        "1008",   # 운송
        "1009",   # 유통
        "1010",   # 음식료
        "1011",   # 종이/목재
        "1012",   # 의약
        "1013",   # 유리/요업
        "1014",   # 섬유/의복
        "1015",   # 전기가스
        "1016",   # 통신
        "1017",   # 금융
        "1018",   # 증권
        "1019",   # 보험
    ]

    end = datetime.now()
    start = end - timedelta(days=30)

    found = []
    for code in possible_codes[:5]:  # 일부만 테스트
        try:
            df = fdr.DataReader(code, start, end)
            if not df.empty:
                print(f"   ✅ {code}: {len(df)}일 데이터")
                found.append(code)
        except:
            pass

    if not found:
        print("   ℹ️ KRX 섹터 지수 직접 지원 안 됨 (대표 종목 사용 권장)")


def main():
    """모든 섹터 데이터 확인"""
    print("\n" + "="*80)
    print("🔍 FinanceDataReader 섹터 데이터 분석")
    print("="*80)

    # 1. 주요 지수 확인
    check_kospi_indices()

    # 2. KRX 섹터 지수 확인
    check_krx_sector_indices()

    # 3. 대표 종목으로 섹터 확인
    sector_perf = check_sector_via_stocks()

    # 결과 요약
    print("\n" + "="*80)
    print("📊 섹터 성과 순위 (30일 기준)")
    print("="*80)

    if sector_perf:
        sorted_sectors = sorted(sector_perf.items(), key=lambda x: x[1], reverse=True)
        for i, (sector, perf) in enumerate(sorted_sectors, 1):
            emoji = "🔥" if perf > 5 else "📈" if perf > 0 else "📉"
            print(f"   {i}. {emoji} {sector}: {perf:+.2f}%")

    print("\n" + "="*80)
    print("✅ 테스트 완료!")
    print("\n💡 결론:")
    print("   - FinanceDataReader는 KRX 섹터 지수를 직접 지원하지 않음")
    print("   - 섹터별 대표 종목 수익률로 섹터 성과 측정 가능")
    print("   - 또는 한국은행 API의 산업별 지수 활용 권장")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
