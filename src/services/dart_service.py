"""DART 공시 서비스"""

import asyncio
import logging
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from typing import Optional, List, Dict, Any

import requests

from src.config.settings import settings

logger = logging.getLogger(__name__)


class DARTService:
    """
    DART 공시 서비스

    - DART Open API 기반 공시 데이터 조회
    """

    def __init__(self):
        self.api_key = settings.DART_API_KEY
        self.base_url = "https://opendart.fss.or.kr/api"

    async def get_company_info(self, corp_code: str) -> Optional[Dict[str, Any]]:
        """
        기업 개황 조회

        Args:
            corp_code: 고유번호 (8자리, 예: "00126380" - 삼성전자)

        Returns:
            dict: 기업 개황 정보
        """
        # API 호출
        url = f"{self.base_url}/company.json"
        params = {"crtfc_key": self.api_key, "corp_code": corp_code}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data.get("status") == "000":
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
                print(f"✅ 주요주주 조회 성공: {len(shareholders)}명")
                return shareholders
            else:
                print(f"⚠️ 주요주주 조회 실패: {data.get('status')}")
                return []

        except Exception as e:
            print(f"❌ 주요주주 조회 에러: {corp_code}, {e}")
            return []

    async def _download_and_parse_corp_code_mapping(self) -> Dict[str, str]:
        """
        DART corp_code.zip 다운로드 및 파싱

        Returns:
            dict: {stock_code: corp_code} 매핑 딕셔너리
        """
        logger.info("📥 DART corp_code.zip 다운로드 시작...")

        if not self.api_key:
            logger.warning("⚠️ DART_API_KEY가 설정되지 않았습니다. 빈 매핑을 반환합니다.")
            return {}

        url = f"{self.base_url}/corpCode.xml"
        params = {"crtfc_key": self.api_key}

        try:
            # ZIP 파일 다운로드 (동기 → 비동기 변환)
            response = await asyncio.to_thread(
                requests.get, url, params=params, timeout=30
            )
            response.raise_for_status()

            # ZIP 파일 압축 해제
            zip_data = BytesIO(response.content)

            with zipfile.ZipFile(zip_data) as zip_file:
                # CORPCODE.xml 파일 읽기
                xml_data = zip_file.read("CORPCODE.xml")

            # XML 파싱
            root = ET.fromstring(xml_data)
            mapping = {}

            for company in root.findall("list"):
                corp_code_elem = company.find("corp_code")
                stock_code_elem = company.find("stock_code")

                if corp_code_elem is not None and stock_code_elem is not None:
                    corp_code = corp_code_elem.text
                    stock_code = stock_code_elem.text

                    # stock_code가 유효한 경우에만 매핑 추가
                    if stock_code and stock_code.strip() and len(stock_code.strip()) == 6:
                        mapping[stock_code.strip()] = corp_code.strip()

            logger.info(f"✅ DART 종목 매핑 완료: {len(mapping)}개 종목")
            return mapping

        except Exception as e:
            logger.error(f"❌ DART corp_code 다운로드 실패: {e}")
            return {}

    async def search_corp_code_by_stock_code(self, stock_code: str) -> Optional[str]:
        """
        종목 코드로 고유번호 찾기

        Args:
            stock_code: 종목 코드 (6자리, 예: "005930")

        Returns:
            str: 고유번호 (8자리, 예: "00126380")
        """
        mapping = await self._download_and_parse_corp_code_mapping()
        if not mapping:
            logger.warning("⚠️ DART 매핑 테이블을 불러오지 못했습니다.")
            return None

        corp_code = mapping.get(stock_code)

        if corp_code:
            logger.info(f"✅ 고유번호 찾기 성공: {stock_code} -> {corp_code}")
        else:
            logger.warning(f"⚠️ 고유번호를 찾을 수 없음: {stock_code}")

        return corp_code


# 싱글톤 인스턴스
dart_service = DARTService()
