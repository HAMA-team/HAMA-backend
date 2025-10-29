"""
간단한 웹 검색 서비스 (DuckDuckGo HTML 엔드포인트 기반)
"""
import logging
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from src.config.settings import settings

logger = logging.getLogger(__name__)


class WebSearchService:
    """DuckDuckGo HTML 기반의 경량 웹 검색 서비스."""

    SEARCH_ENDPOINT = "https://duckduckgo.com/html/"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    )

    def __init__(self, *, timeout: Optional[float] = None):
        self.timeout = timeout or settings.WEB_SEARCH_TIMEOUT

    async def search(
        self,
        query: str,
        *,
        max_results: Optional[int] = None,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        """DuckDuckGo HTML 페이지를 파싱하여 검색 결과를 반환."""
        if not settings.ENABLE_WEB_SEARCH and not force:
            logger.info("🌐 [WebSearch] 검색 비활성화 설정 - 빈 결과 반환")
            return []

        if not query.strip():
            return []

        limit = max_results or settings.WEB_SEARCH_MAX_RESULTS
        limit = max(1, min(limit, 10))

        params = {
            "q": query,
            "kl": settings.WEB_SEARCH_REGION or "kr-kr",
            "ia": "web",
        }

        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept-Language": "ko,en;q=0.8",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                response = await client.get(self.SEARCH_ENDPOINT, params=params)
                response.raise_for_status()
        except Exception as exc:
            logger.warning("⚠️ [WebSearch] 검색 요청 실패: %s", exc)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        results: List[Dict[str, Any]] = []

        for rank, result in enumerate(soup.select("div.result"), start=1):
            link_tag = result.select_one("a.result__a")
            if not link_tag:
                continue

            title = link_tag.get_text(" ", strip=True)
            url = link_tag.get("href", "").strip()

            snippet_tag = result.select_one("a.result__snippet") or result.select_one("div.result__snippet")
            snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

            if not url:
                continue

            results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "rank": rank,
                }
            )

            if len(results) >= limit:
                break

        if not results:
            logger.info("ℹ️ [WebSearch] 검색 결과 없음: %s", query)

        return results


web_search_service = WebSearchService()

__all__ = ["WebSearchService", "web_search_service"]
