"""DART API 연동 테스트 (HTTP 직접 호출 방식)"""

import os
import pytest
import requests
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()


@pytest.fixture
def api_key():
    """DART API 키 확인"""
    api_key = os.getenv("DART_API_KEY")
    assert api_key is not None
    assert len(api_key) > 0
    print(f"✅ DART API 키: {api_key[:10]}...")
    return api_key


def test_get_company_info(api_key):
    """기업 개황 조회 테스트"""
    url = "https://opendart.fss.or.kr/api/company.json"

    # 삼성전자 corp_code: 00126380
    params = {"crtfc_key": api_key, "corp_code": "00126380"}

    response = requests.get(url, params=params)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "000"  # 정상

    print(f"✅ 기업명: {data['corp_name']}")
    print(f"✅ 대표자명: {data['ceo_nm']}")
    print(f"✅ 주소: {data['adres']}")


def test_get_disclosure_list(api_key):
    """공시 검색 테스트 (최근 공시 목록)"""
    url = "https://opendart.fss.or.kr/api/list.json"

    # 삼성전자의 최근 10개 공시
    params = {
        "crtfc_key": api_key,
        "corp_code": "00126380",
        "bgn_de": "20240901",
        "end_de": "20251003",
        "page_count": "10",
    }

    response = requests.get(url, params=params)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "000"

    if "list" in data:
        disclosures = data["list"]
        print(f"✅ 조회된 공시 수: {len(disclosures)}")
        if len(disclosures) > 0:
            print(f"✅ 최신 공시: {disclosures[0]['report_nm']}")
            print(f"✅ 접수일자: {disclosures[0]['rcept_dt']}")
    else:
        print("✅ 해당 기간 공시 없음")


def test_get_financial_statement(api_key):
    """재무제표 조회 테스트"""
    url = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"

    # 삼성전자 2023년 사업보고서 재무제표
    params = {
        "crtfc_key": api_key,
        "corp_code": "00126380",
        "bsns_year": "2023",
        "reprt_code": "11011",  # 사업보고서
        "fs_div": "CFS",  # 연결재무제표
    }

    response = requests.get(url, params=params)
    assert response.status_code == 200

    data = response.json()

    if data["status"] == "000":
        if "list" in data:
            statements = data["list"]
            print(f"✅ 조회된 재무항목 수: {len(statements)}")

            # 매출액 찾기
            revenue = [s for s in statements if "매출액" in s.get("account_nm", "")]
            if revenue:
                print(f"✅ 매출액 항목 수: {len(revenue)}")
    else:
        print(f"⚠️ 재무제표 조회: status={data['status']}, message={data.get('message', '없음')}")


def test_get_major_shareholder(api_key):
    """주요주주 현황 조회 테스트"""
    url = "https://opendart.fss.or.kr/api/hyslrSttus.json"

    params = {
        "crtfc_key": api_key,
        "corp_code": "00126380",
        "bsns_year": "2023",
        "reprt_code": "11011",  # 사업보고서
    }

    response = requests.get(url, params=params)
    assert response.status_code == 200

    data = response.json()

    if data["status"] == "000" and "list" in data:
        shareholders = data["list"]
        print(f"✅ 주요주주 수: {len(shareholders)}")
        if len(shareholders) > 0:
            print(f"✅ 최대주주: {shareholders[0]['nm']}")
            # 지분율 관련 필드 확인
            for key in shareholders[0].keys():
                if "hold" in key.lower() or "rate" in key.lower():
                    print(f"✅ 지분 정보: {key}={shareholders[0][key]}")
                    break
    else:
        print("✅ 주요주주 정보 없음")


if __name__ == "__main__":
    print("\n🔍 DART Open API 테스트 시작\n")

    test_api_key = os.getenv("DART_API_KEY")
    assert test_api_key is not None
    print(f"✅ DART API 키: {test_api_key[:10]}...")
    print("1️⃣ API 키 확인 완료\n")
    api_key = test_api_key

    test_get_company_info(api_key)
    print("2️⃣ 기업 개황 조회 완료\n")

    test_get_disclosure_list(api_key)
    print("3️⃣ 공시 목록 조회 완료\n")

    test_get_financial_statement(api_key)
    print("4️⃣ 재무제표 조회 완료\n")

    test_get_major_shareholder(api_key)
    print("5️⃣ 주요주주 현황 조회 완료\n")

    print("✅ 모든 DART API 테스트 통과!")
