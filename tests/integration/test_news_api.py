"""
뉴스 API 엔드포인트 통합 테스트
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from uuid import uuid4

from src.main import app
from src.models.database import SessionLocal
from src.models.stock import News
from src.repositories.news_repository import news_repository


class TestNewsAPIEndpoints:
    """뉴스 API 엔드포인트 통합 테스트"""

    @pytest.fixture
    def client(self):
        """FastAPI 테스트 클라이언트"""
        return TestClient(app)

    @pytest.fixture
    def sample_news_data(self):
        """테스트용 샘플 뉴스 데이터"""
        return [
            News(
                news_id=uuid4(),
                title="삼성전자 3분기 실적 발표",
                summary="삼성전자가 3분기 영업이익 7조원을 기록했다.",
                url="https://example.com/news1",
                source="네이버 뉴스",
                related_stocks=["005930"],
                published_at=datetime(2024, 10, 28, 13, 51, 0),
            ),
            News(
                news_id=uuid4(),
                title="SK하이닉스 AI 반도체 수주 확대",
                summary="SK하이닉스가 AI 반도체 수주를 확대하고 있다.",
                url="https://example.com/news2",
                source="네이버 뉴스",
                related_stocks=["000660"],
                published_at=datetime(2024, 10, 28, 12, 30, 0),
            ),
            News(
                news_id=uuid4(),
                title="삼성전자 AI 투자 확대",
                summary="삼성전자가 AI 분야 투자를 대폭 확대한다.",
                url="https://example.com/news3",
                source="네이버 뉴스",
                related_stocks=["005930"],
                published_at=datetime(2024, 10, 28, 11, 0, 0),
            ),
        ]

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, sample_news_data):
        """각 테스트 전후 DB 초기화"""
        # Setup: 테스트 데이터 삽입
        try:
            news_repository.bulk_insert(sample_news_data)
        except Exception:
            pass  # 중복 삽입 시 무시

        yield

        # Teardown은 생략 (실제 DB 사용, 테스트 데이터 유지)

    def test_get_stock_news_success(self, client):
        """종목별 뉴스 조회 성공"""
        response = client.get("/api/v1/news/005930?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # 삼성전자 관련 뉴스만 반환되어야 함
        for item in data:
            assert "005930" in item["related_stocks"]
            assert "news_id" in item
            assert "title" in item
            assert "url" in item
            assert "source" in item
            assert "published_at" in item

    def test_get_stock_news_with_limit(self, client):
        """limit 파라미터 적용 확인"""
        response = client.get("/api/v1/news/005930?limit=1")

        assert response.status_code == 200
        data = response.json()
        # limit이 1이어도 필터링 후 결과가 1개 이하일 수 있음
        assert len(data) <= 1

    def test_get_stock_news_no_results(self, client):
        """존재하지 않는 종목 코드 조회"""
        response = client.get("/api/v1/news/999999?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_recent_news_success(self, client):
        """최근 뉴스 조회 성공"""
        response = client.get("/api/v1/news/recent?limit=50")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        for item in data:
            assert "news_id" in item
            assert "title" in item
            assert "url" in item
            assert "source" in item
            assert "related_stocks" in item
            assert "published_at" in item

    def test_get_recent_news_default_limit(self, client):
        """기본 limit 적용 확인"""
        response = client.get("/api/v1/news/recent")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # 기본값은 50개
        assert len(data) <= 50

    @pytest.mark.asyncio
    async def test_fetch_news_endpoint(self, client):
        """
        뉴스 수집 엔드포인트 테스트

        주의: 이 테스트는 실제 네이버 API를 호출합니다.
        .env 파일에 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET이 설정되어 있어야 합니다.
        """
        from src.config.settings import settings

        if not settings.NAVER_CLIENT_ID or not settings.NAVER_CLIENT_SECRET:
            pytest.skip("네이버 API 키가 설정되지 않았습니다.")

        request_data = {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "max_articles": 5,
        }

        response = client.post("/api/v1/news/fetch", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert "message" in data
        assert "collected_count" in data
        assert "saved_count" in data
        assert data["collected_count"] >= 0
        assert data["saved_count"] >= 0

    def test_fetch_news_invalid_request(self, client):
        """잘못된 요청 데이터"""
        invalid_data = {
            "stock_code": "005930",
            # stock_name 누락
            "max_articles": 5,
        }

        response = client.post("/api/v1/news/fetch", json=invalid_data)

        assert response.status_code == 422  # Validation error

    def test_fetch_news_max_articles_validation(self, client):
        """max_articles 범위 검증"""
        # 최소값 위반
        response = client.post(
            "/api/v1/news/fetch",
            json={"stock_code": "005930", "stock_name": "삼성전자", "max_articles": 0},
        )
        assert response.status_code == 422

        # 최대값 위반
        response = client.post(
            "/api/v1/news/fetch",
            json={"stock_code": "005930", "stock_name": "삼성전자", "max_articles": 101},
        )
        assert response.status_code == 422

    def test_news_response_model_structure(self, client):
        """응답 모델 구조 검증"""
        response = client.get("/api/v1/news/recent?limit=1")

        assert response.status_code == 200
        data = response.json()

        if len(data) > 0:
            item = data[0]
            # 필수 필드 존재 확인
            required_fields = [
                "news_id",
                "title",
                "url",
                "source",
                "related_stocks",
                "published_at",
            ]
            for field in required_fields:
                assert field in item, f"Missing field: {field}"

            # 타입 검증
            assert isinstance(item["news_id"], str)
            assert isinstance(item["title"], str)
            assert isinstance(item["url"], str)
            assert isinstance(item["source"], str)
            assert isinstance(item["related_stocks"], list)
            assert isinstance(item["published_at"], str)

            # summary는 optional
            if "summary" in item:
                assert isinstance(item["summary"], (str, type(None)))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
