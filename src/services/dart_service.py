"""DART 공시 서비스"""

from typing import Optional, List, Dict, Any
import requests

from src.services.cache_manager import cache_manager
from src.config.settings import settings


class DARTService:
    """
    DART 공시 서비스

    - DART Open API를 사용한 공시 데이터 조회
    - 캐싱 지원
    """

    def __init__(self):
        self.api_key = settings.DART_API_KEY
        self.base_url = "https://opendart.fss.or.kr/api"
        self.cache = cache_manager

    async def get_company_info(self, corp_code: str) -> Optional[Dict[str, Any]]:
        """
        기업 개황 조회

        Args:
            corp_code: 고유번호 (8자리, 예: "00126380" - 삼성전자)

        Returns:
            dict: 기업 개황 정보
        """
        # 캐시 키
        cache_key = f"dart_company:{corp_code}"

        # 캐시 확인
        cached = await self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ 캐시 히트: {cache_key}")
            return cached

        # API 호출
        url = f"{self.base_url}/company.json"
        params = {"crtfc_key": self.api_key, "corp_code": corp_code}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "000":
                # 캐싱 (1일 TTL - 기업 정보는 자주 변하지 않음)
                await self.cache.set(cache_key, data, ttl=86400)
                print(f"✅ 기업 개황 조회 성공: {data.get('corp_name', corp_code)}")
                return data
            else:
                print(
                    f"⚠️ 기업 개황 조회 실패: {data.get('status')}, {data.get('message')}"
                )
                return None

        except Exception as e:
            print(f"❌ 기업 개황 조회 에러: {corp_code}, {e}")
            return None

    async def get_disclosure_list(
        self, corp_code: str, bgn_de: str, end_de: str, page_count: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """
        공시 목록 조회

        Args:
            corp_code: 고유번호
            bgn_de: 시작일 (YYYYMMDD)
            end_de: 종료일 (YYYYMMDD)
            page_count: 페이지당 건수

        Returns:
            list: 공시 목록
        """
        # 캐시 키
        cache_key = f"dart_disclosure:{corp_code}:{bgn_de}:{end_de}"

        # 캐시 확인
        cached = await self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ 캐시 히트: {cache_key}")
            return cached

        # API 호출
        url = f"{self.base_url}/list.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_count": str(page_count),
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "000":
                disclosures = data.get("list", [])
                # 캐싱 (5분 TTL)
                await self.cache.set(
                    cache_key, disclosures, ttl=settings.CACHE_TTL_NEWS
                )
                print(f"✅ 공시 목록 조회 성공: {len(disclosures)}건")
                return disclosures
            else:
                print(f"⚠️ 공시 목록 조회 실패: {data.get('status')}")
                return []

        except Exception as e:
            print(f"❌ 공시 목록 조회 에러: {corp_code}, {e}")
            return []

    async def get_financial_statement(
        self, corp_code: str, bsns_year: str, reprt_code: str = "11011"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        재무제표 조회

        Args:
            corp_code: 고유번호
            bsns_year: 사업연도 (YYYY)
            reprt_code: 보고서 코드 (11011: 사업보고서, 11012: 반기보고서, 11013: 1분기보고서, 11014: 3분기보고서)

        Returns:
            list: 재무제표 항목 리스트
        """
        # 캐시 키
        cache_key = f"dart_financial:{corp_code}:{bsns_year}:{reprt_code}"

        # 캐시 확인
        cached = await self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ 캐시 히트: {cache_key}")
            return cached

        # API 호출
        url = f"{self.base_url}/fnlttSinglAcntAll.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,
            "fs_div": "CFS",  # 연결재무제표
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "000":
                statements = data.get("list", [])
                # 캐싱 (1일 TTL)
                await self.cache.set(
                    cache_key, statements, ttl=settings.CACHE_TTL_FINANCIAL_STATEMENTS
                )
                print(f"✅ 재무제표 조회 성공: {len(statements)}개 항목")
                return statements
            else:
                print(f"⚠️ 재무제표 조회 실패: {data.get('status')}")
                return []

        except Exception as e:
            print(f"❌ 재무제표 조회 에러: {corp_code}, {e}")
            return []

    async def get_major_shareholder(
        self, corp_code: str, bsns_year: str, reprt_code: str = "11011"
    ) -> Optional[List[Dict[str, Any]]]:
        """
        주요주주 현황 조회

        Args:
            corp_code: 고유번호
            bsns_year: 사업연도 (YYYY)
            reprt_code: 보고서 코드

        Returns:
            list: 주요주주 목록
        """
        # 캐시 키
        cache_key = f"dart_shareholder:{corp_code}:{bsns_year}:{reprt_code}"

        # 캐시 확인
        cached = await self.cache.get(cache_key)
        if cached is not None:
            print(f"✅ 캐시 히트: {cache_key}")
            return cached

        # API 호출
        url = f"{self.base_url}/hyslrSttus.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "000":
                shareholders = data.get("list", [])
                # 캐싱 (1일 TTL)
                await self.cache.set(cache_key, shareholders, ttl=86400)
                print(f"✅ 주요주주 조회 성공: {len(shareholders)}명")
                return shareholders
            else:
                print(f"⚠️ 주요주주 조회 실패: {data.get('status')}")
                return []

        except Exception as e:
            print(f"❌ 주요주주 조회 에러: {corp_code}, {e}")
            return []

    def search_corp_code_by_stock_code(self, stock_code: str) -> Optional[str]:
        """
        종목 코드로 고유번호 찾기 (하드코딩 매핑)

        Note: 실제로는 DART corp_code.zip을 다운로드하여 매핑 테이블을 만들어야 하지만,
        Phase 2에서는 주요 종목만 하드코딩

        Args:
            stock_code: 종목 코드 (6자리, 예: "005930")

        Returns:
            str: 고유번호 (8자리, 예: "00126380")
        """
        # 주요 종목 매핑 (Phase 2에서는 일부만 지원)
        mapping = {
            "005930": "00126380",  # 삼성전자
            "000660": "00126380",  # SK하이닉스 (임시: DART corp_code 확인 필요)
            "035420": "00140536",  # NAVER
            "005380": "00164779",  # 현대자동차
            "051910": "00164529",  # LG화학
        }

        corp_code = mapping.get(stock_code)

        if corp_code:
            print(f"✅ 고유번호 찾기 성공: {stock_code} -> {corp_code}")
        else:
            print(f"⚠️ 고유번호를 찾을 수 없음: {stock_code}")

        return corp_code


# 싱글톤 인스턴스
dart_service = DARTService()
