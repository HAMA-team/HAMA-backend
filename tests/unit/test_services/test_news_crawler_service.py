"""
네이버 뉴스 API 서비스 단위 테스트
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from src.services.news_crawler_service import NaverNewsAPIService, get_news_service
from src.models.stock import News


class TestNaverNewsAPIService:
    """NaverNewsAPIService 단위 테스트"""

    @pytest.fixture
    def mock_api_response(self):
        """네이버 API 응답 모킹"""
        return {
            "lastBuildDate": "Mon, 28 Oct 2024 13:51:00 +0900",
            "total": 100,
            "start": 1,
            "display": 3,
            "items": [
                {
                    "title": "<b>삼성전자</b> 3분기 영업익 7조원 돌파",
                    "originallink": "https://example.com/news1",
                    "link": "https://n.news.naver.com/news1",
                    "description": "<b>삼성전자</b>가 3분기 실적을 발표했다.",
                    "pubDate": "Mon, 28 Oct 2024 13:51:00 +0900",
                },
                {
                    "title": "<b>삼성전자</b> AI 반도체 투자 확대",
                    "originallink": "https://example.com/news2",
                    "link": "https://n.news.naver.com/news2",
                    "description": "AI 시장 공략을 위해 투자 확대",
                    "pubDate": "Mon, 28 Oct 2024 12:30:00 +0900",
                },
            ],
        }

    @pytest.fixture
    async def service(self):
        """NaverNewsAPIService 인스턴스 생성"""
        service = NaverNewsAPIService(
            client_id="test_client_id", client_secret="test_client_secret"
        )
        yield service
        await service.close()

    @pytest.mark.asyncio
    async def test_search_news_success(self, service, mock_api_response):
        """뉴스 검색 API 호출 성공 테스트"""
        with patch.object(
            service.client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_api_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await service.search_news(query="삼성전자", display=3)

            assert len(result) == 2
            assert result[0]["title"] == "<b>삼성전자</b> 3분기 영업익 7조원 돌파"
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_news_without_credentials(self):
        """API 키 없이 호출 시 빈 리스트 반환"""
        service = NaverNewsAPIService(client_id=None, client_secret=None)
        result = await service.search_news(query="삼성전자")
        await service.close()

        assert result == []

    @pytest.mark.asyncio
    async def test_search_news_http_error(self, service):
        """HTTP 에러 발생 시 처리"""
        with patch.object(
            service.client, "get", new_callable=AsyncMock
        ) as mock_get:
            import httpx

            mock_get.side_effect = httpx.HTTPStatusError(
                "404 Not Found", request=Mock(), response=Mock(status_code=404)
            )

            result = await service.search_news(query="삼성전자")

            assert result == []

    def test_remove_html_tags(self):
        """HTML 태그 제거 테스트"""
        text_with_tags = "<b>삼성전자</b>가 <em>실적</em>을 발표했다."
        clean_text = NaverNewsAPIService._remove_html_tags(text_with_tags)

        assert clean_text == "삼성전자가 실적을 발표했다."
        assert "<b>" not in clean_text
        assert "</b>" not in clean_text

    def test_parse_pub_date_valid(self):
        """RFC 2822 형식 날짜 파싱 테스트"""
        pub_date_str = "Mon, 28 Oct 2024 13:51:00 +0900"
        parsed_date = NaverNewsAPIService._parse_pub_date(pub_date_str)

        assert isinstance(parsed_date, datetime)
        assert parsed_date.year == 2024
        assert parsed_date.month == 10
        assert parsed_date.day == 28

    def test_parse_pub_date_invalid(self):
        """잘못된 날짜 형식 처리 (현재 시간 반환)"""
        invalid_date = "Invalid Date Format"
        parsed_date = NaverNewsAPIService._parse_pub_date(invalid_date)

        assert isinstance(parsed_date, datetime)
        # 현재 시간으로 fallback
        assert abs((datetime.now() - parsed_date).seconds) < 5

    def test_parse_news_item(self, service):
        """API 응답 항목을 News 모델로 변환"""
        item = {
            "title": "<b>삼성전자</b> 3분기 영업익 7조원 돌파",
            "originallink": "https://example.com/news1",
            "link": "https://n.news.naver.com/news1",
            "description": "<b>삼성전자</b>가 3분기 실적을 발표했다.",
            "pubDate": "Mon, 28 Oct 2024 13:51:00 +0900",
        }

        news = service._parse_news_item(item, stock_code="005930")

        assert news is not None
        assert isinstance(news, News)
        assert news.title == "삼성전자 3분기 영업익 7조원 돌파"  # HTML 태그 제거됨
        assert news.summary == "삼성전자가 3분기 실적을 발표했다."
        assert news.url == "https://example.com/news1"
        assert news.source == "네이버 뉴스"
        assert "005930" in news.related_stocks
        assert news.published_at.year == 2024

    @pytest.mark.asyncio
    async def test_fetch_stock_news(self, service, mock_api_response):
        """종목별 뉴스 수집 통합 테스트"""
        with patch.object(
            service.client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_api_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            news_list = await service.fetch_stock_news(
                stock_code="005930", stock_name="삼성전자", max_articles=20
            )

            assert len(news_list) == 2
            assert all(isinstance(news, News) for news in news_list)
            assert all("005930" in news.related_stocks for news in news_list)

    @pytest.mark.asyncio
    async def test_fetch_stock_news_empty_result(self, service):
        """검색 결과 없을 때 처리"""
        with patch.object(
            service.client, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"items": []}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            news_list = await service.fetch_stock_news(
                stock_code="000000", stock_name="없는회사", max_articles=20
            )

            assert news_list == []

    @pytest.mark.asyncio
    async def test_save_news_success(self, service):
        """뉴스 DB 저장 성공 테스트"""
        news_list = [
            News(
                news_id=uuid4(),
                title="뉴스 1",
                url="https://example.com/news1",
                source="네이버 뉴스",
                related_stocks=["005930"],
                published_at=datetime.now(),
            ),
            News(
                news_id=uuid4(),
                title="뉴스 2",
                url="https://example.com/news2",
                source="네이버 뉴스",
                related_stocks=["005930"],
                published_at=datetime.now(),
            ),
        ]

        with patch("src.services.news_crawler_service.news_repository") as mock_repo:
            mock_repo.bulk_insert.return_value = None

            saved_count = await service.save_news(news_list)

            assert saved_count == 2
            mock_repo.bulk_insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_news_deduplication(self, service):
        """중복 URL 제거 테스트"""
        duplicate_url = "https://example.com/news1"
        news_list = [
            News(
                news_id=uuid4(),
                title="뉴스 1",
                url=duplicate_url,
                source="네이버 뉴스",
                related_stocks=["005930"],
                published_at=datetime.now(),
            ),
            News(
                news_id=uuid4(),
                title="뉴스 1 중복",
                url=duplicate_url,  # 동일 URL
                source="네이버 뉴스",
                related_stocks=["005930"],
                published_at=datetime.now(),
            ),
        ]

        with patch("src.services.news_crawler_service.news_repository") as mock_repo:
            mock_repo.bulk_insert.return_value = None

            saved_count = await service.save_news(news_list)

            # 중복 제거되어 1개만 저장
            assert saved_count == 1
            mock_repo.bulk_insert.assert_called_once()
            saved_news = list(mock_repo.bulk_insert.call_args[0][0])
            assert len(saved_news) == 1

    @pytest.mark.asyncio
    async def test_save_news_empty_list(self, service):
        """빈 리스트 저장 시 0 반환"""
        saved_count = await service.save_news([])
        assert saved_count == 0

    def test_get_news_service_singleton(self):
        """싱글톤 인스턴스 테스트"""
        service1 = get_news_service()
        service2 = get_news_service()

        assert service1 is service2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
