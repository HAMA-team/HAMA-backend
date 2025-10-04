"""
한국은행(BOK) 경제통계시스템 API 테스트

주요 지표:
- 기준금리
- CPI (소비자물가지수)
- GDP (국내총생산)
- 환율 (원/달러)
"""

import requests
from datetime import datetime, timedelta
import json

# API 인증키
BOK_API_KEY = "2O7RAZB6EF8Z41P5HINK"
BASE_URL = "http://ecos.bok.or.kr/api"


def get_base_rate(start_date: str = None, end_date: str = None):
    """
    기준금리 조회

    통계표코드: 722Y001
    주기: M (월간)
    통계항목코드: 0101000
    """
    if not start_date:
        # 최근 1년
        end_date = datetime.now().strftime("%Y%m")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m")

    url = f"{BASE_URL}/StatisticSearch/{BOK_API_KEY}/json/kr/1/100/722Y001/M/{start_date}/{end_date}/0101000"

    response = requests.get(url)
    data = response.json()

    print("\n📊 기준금리 데이터:")
    print(f"   URL: {url}")
    print(f"   Status: {response.status_code}")

    if "StatisticSearch" in data:
        rows = data["StatisticSearch"]["row"]
        print(f"   조회 건수: {len(rows)}개")
        print(f"\n   최근 3개월:")
        for row in rows[-3:]:
            print(f"   - {row['TIME']}: {row['DATA_VALUE']}%")
        return rows
    else:
        print(f"   Error: {data}")
        return None


def get_cpi(start_date: str = None, end_date: str = None):
    """
    소비자물가지수(CPI) 조회

    통계표코드: 901Y009
    주기: M (월간)
    통계항목코드: 0 (전체)
    """
    if not start_date:
        # 최근 2년
        end_date = datetime.now().strftime("%Y%m")
        start_date = (datetime.now() - timedelta(days=730)).strftime("%Y%m")

    url = f"{BASE_URL}/StatisticSearch/{BOK_API_KEY}/json/kr/1/100/901Y009/M/{start_date}/{end_date}/0"

    response = requests.get(url)
    data = response.json()

    print("\n📊 소비자물가지수(CPI) 데이터:")
    print(f"   URL: {url}")
    print(f"   Status: {response.status_code}")

    if "StatisticSearch" in data:
        rows = data["StatisticSearch"]["row"]
        print(f"   조회 건수: {len(rows)}개")
        print(f"\n   최근 3개월:")
        for row in rows[-3:]:
            print(f"   - {row['TIME']}: {row['DATA_VALUE']} (기준년도: {row.get('ITEM_NAME1', 'N/A')})")
        return rows
    else:
        print(f"   Error: {data}")
        return None


def get_gdp(start_date: str = None, end_date: str = None):
    """
    GDP (국내총생산) 조회

    통계표코드: 200Y001
    주기: Q (분기)
    통계항목코드: 10111 (실질GDP)
    """
    if not start_date:
        # 최근 2년 (8분기)
        end = datetime.now()
        start = end - timedelta(days=730)
        end_date = f"{end.year}Q{(end.month-1)//3 + 1}"
        start_date = f"{start.year}Q{(start.month-1)//3 + 1}"

    url = f"{BASE_URL}/StatisticSearch/{BOK_API_KEY}/json/kr/1/100/200Y001/Q/{start_date}/{end_date}/10111"

    response = requests.get(url)
    data = response.json()

    print("\n📊 GDP (실질국내총생산) 데이터:")
    print(f"   URL: {url}")
    print(f"   Status: {response.status_code}")

    if "StatisticSearch" in data:
        rows = data["StatisticSearch"]["row"]
        print(f"   조회 건수: {len(rows)}개")
        print(f"\n   최근 4분기:")
        for row in rows[-4:]:
            print(f"   - {row['TIME']}: {row['DATA_VALUE']} (조원)")
        return rows
    else:
        print(f"   Error: {data}")
        return None


def get_exchange_rate(start_date: str = None, end_date: str = None):
    """
    환율 (원/달러) 조회

    통계표코드: 731Y001
    주기: D (일간)
    통계항목코드: 0000001 (매매기준율)
    """
    if not start_date:
        # 최근 30일
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    url = f"{BASE_URL}/StatisticSearch/{BOK_API_KEY}/json/kr/1/100/731Y001/D/{start_date}/{end_date}/0000001"

    response = requests.get(url)
    data = response.json()

    print("\n📊 환율 (원/달러) 데이터:")
    print(f"   URL: {url}")
    print(f"   Status: {response.status_code}")

    if "StatisticSearch" in data:
        rows = data["StatisticSearch"]["row"]
        print(f"   조회 건수: {len(rows)}개")
        print(f"\n   최근 5일:")
        for row in rows[-5:]:
            print(f"   - {row['TIME']}: {row['DATA_VALUE']} 원")
        return rows
    else:
        print(f"   Error: {data}")
        return None


def main():
    """모든 경제지표 조회 테스트"""
    print("\n" + "="*80)
    print("🏦 한국은행 경제통계 API 테스트")
    print("="*80)

    # 1. 기준금리
    base_rate = get_base_rate()

    # 2. CPI
    cpi = get_cpi()

    # 3. GDP
    gdp = get_gdp()

    # 4. 환율
    exchange_rate = get_exchange_rate()

    print("\n" + "="*80)
    print("✅ 테스트 완료!")
    print("="*80)

    # 결과 요약
    print("\n📋 수집된 데이터 요약:")
    print(f"   - 기준금리: {len(base_rate) if base_rate else 0}개")
    print(f"   - CPI: {len(cpi) if cpi else 0}개")
    print(f"   - GDP: {len(gdp) if gdp else 0}개")
    print(f"   - 환율: {len(exchange_rate) if exchange_rate else 0}개")

    return {
        "base_rate": base_rate,
        "cpi": cpi,
        "gdp": gdp,
        "exchange_rate": exchange_rate
    }


if __name__ == "__main__":
    result = main()
