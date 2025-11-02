"""
네이버 뉴스 검색 API 서비스

네이버 검색 API를 사용하여 종목별 뉴스를 수집하여 DB에 저장합니다.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from urllib.parse import quote
from uuid import uuid4

import httpx

from src.config.settings import settings
from src.models.stock import News
from src.repositories.news_repository import news_repository

logger = logging.getLogger(__name__)


class NaverNewsAPIService:
    """네이버 뉴스 검색 API 서비스"""

    API_URL = "https://openapi.naver.com/v1/search/news.json"

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        """
        네이버 뉴스 API 서비스 초기화

        Args:
            client_id: 네이버 API 클라이언트 ID (없으면 settings에서 가져옴)
            client_secret: 네이버 API 클라이언트 시크릿
        """
        self.client_id = client_id or getattr(settings, "NAVER_CLIENT_ID", None)
        self.client_secret = client_secret or getattr(
            settings, "NAVER_CLIENT_SECRET", None
        )

        if not self.client_id or not self.client_secret:
            logger.warning(
                "⚠️ [NaverNewsAPI] API 키가 설정되지 않았습니다. "
                ".env 파일에 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET를 추가하세요."
            )

        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    async def close(self):
        """HTTP 클라이언트 종료"""
        await self.client.aclose()

    async def search_news(
        self,
        query: str,
        display: int = 20,
        start: int = 1,
        sort: str = "date",
    ) -> List[dict]:
        """
        뉴스 검색 API 호출

        Args:
            query: 검색 키워드 (종목명 또는 종목 코드)
            display: 한 번에 가져올 결과 수 (최대 100)
            start: 검색 시작 위치 (최대 1000)
            sort: 정렬 방식 ("sim" 정확도순, "date" 날짜순)

        Returns:
            뉴스 항목 리스트 (dict)
        """
        if not self.client_id or not self.client_secret:
            logger.error("❌ [NaverNewsAPI] API 키가 없습니다.")
            return []

        # 쿼리 URL 인코딩
        encoded_query = quote(query)

        url = f"{self.API_URL}?query={encoded_query}&display={display}&start={start}&sort={sort}"

        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }

        try:
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("items", [])
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ [NaverNewsAPI] HTTP 에러 ({e.response.status_code}): {e}")
            return []
        except httpx.HTTPError as e:
            logger.error(f"❌ [NaverNewsAPI] 요청 실패: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ [NaverNewsAPI] 예상치 못한 에러: {e}")
            return []

    async def fetch_stock_news(
        self,
        stock_code: str,
        stock_name: str,
        max_articles: int = 20,
    ) -> List[News]:
        """
        종목별 뉴스 수집

        Args:
            stock_code: 종목 코드 (예: "005930")
            stock_name: 종목명 (예: "삼성전자")
            max_articles: 최대 수집 기사 수

        Returns:
            News 객체 리스트
        """
        logger.info(
            f"📰 [NaverNewsAPI] 뉴스 검색 시작: {stock_name} (최대 {max_articles}개)"
        )

        # 종목명으로 검색 (종목 코드보다 관련성 높은 결과)
        items = await self.search_news(
            query=stock_name, display=min(max_articles, 100), sort="date"
        )

        if not items:
            logger.warning(f"⚠️ [NaverNewsAPI] 검색 결과 없음: {stock_name}")
            return []

        news_list = []
        for item in items:
            news = self._parse_news_item(item, stock_code)
            if news:
                news_list.append(news)

        logger.info(f"✅ [NaverNewsAPI] {len(news_list)}개 뉴스 수집 완료")
        return news_list

    def _parse_news_item(self, item: dict, stock_code: str) -> Optional[News]:
        """
        API 응답 항목을 News 모델로 변환

        Args:
            item: 네이버 API 응답 항목
            stock_code: 관련 종목 코드

        Returns:
            News 객체
        """
        try:
            # HTML 태그 제거
            title = self._remove_html_tags(item.get("title", ""))
            description = self._remove_html_tags(item.get("description", ""))

            # 발행일 파싱 (예: "Mon, 28 Oct 2024 13:51:00 +0900")
            pub_date_str = item.get("pubDate", "")
            published_at = self._parse_pub_date(pub_date_str)

            news = News(
                news_id=uuid4(),
                title=title,
                content=None,  # API는 전문 제공하지 않음
                summary=description,
                url=item.get("originallink") or item.get("link", ""),
                source="네이버 뉴스",
                related_stocks=[stock_code],
                published_at=published_at,
                embedding_id=None,  # URL 해시로 중복 체크 가능
            )

            return news
        except Exception as e:
            logger.warning(f"⚠️ [NaverNewsAPI] 뉴스 파싱 실패: {e}")
            return None

    @staticmethod
    def _remove_html_tags(text: str) -> str:
        """HTML 태그 제거"""
        import re

        # <b>, </b> 등 태그 제거
        clean_text = re.sub(r"<[^>]+>", "", text)
        return clean_text.strip()

    @staticmethod
    def _parse_pub_date(pub_date_str: str) -> datetime:
        """
        발행일 문자열을 datetime으로 변환

        Args:
            pub_date_str: "Mon, 28 Oct 2024 13:51:00 +0900" 형식

        Returns:
            datetime 객체
        """
        try:
            # RFC 2822 형식 파싱
            from email.utils import parsedate_to_datetime

            return parsedate_to_datetime(pub_date_str)
        except Exception:
            # 파싱 실패 시 현재 시간
            return datetime.now()

    async def save_news(self, news_list: List[News]) -> int:
        """
        뉴스 리스트를 DB에 저장 (중복 제거)

        Returns:
            저장된 뉴스 개수
        """
        if not news_list:
            return 0

        logger.info(f"💾 [NaverNewsAPI] DB 저장 시작: {len(news_list)}개")

        # 중복 제거: URL 기준
        unique_news = {}
        for news in news_list:
            if news.url and news.url not in unique_news:
                unique_news[news.url] = news

        try:
            news_repository.bulk_insert(unique_news.values())
            logger.info(f"✅ [NaverNewsAPI] {len(unique_news)}개 뉴스 저장 완료")
            return len(unique_news)
        except Exception as e:
            logger.error(f"❌ [NaverNewsAPI] DB 저장 실패: {e}")
            return 0


# 싱글톤 인스턴스
_news_service = None


def get_news_service() -> NaverNewsAPIService:
    """뉴스 API 서비스 싱글톤 인스턴스 반환"""
    global _news_service
    if _news_service is None:
        _news_service = NaverNewsAPIService()
    return _news_service


async def fetch_and_save_news(
    stock_code: str, stock_name: str, max_articles: int = 20
) -> int:
    """
    종목 뉴스를 검색하고 DB에 저장하는 헬퍼 함수

    Args:
        stock_code: 종목 코드 (예: "005930")
        stock_name: 종목명 (예: "삼성전자")
        max_articles: 최대 수집 기사 수

    Returns:
        저장된 뉴스 개수
    """
    service = get_news_service()
    news_list = await service.fetch_stock_news(
        stock_code, stock_name, max_articles=max_articles
    )
    return await service.save_news(news_list)

