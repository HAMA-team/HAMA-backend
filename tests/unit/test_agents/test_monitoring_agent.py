"""
Monitoring Agent 단위 테스트
"""
import pytest
from datetime import datetime
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, Mock, patch

from src.agents.monitoring.nodes import (
    fetch_portfolio_node,
    collect_news_node,
    analyze_news_node,
    generate_alerts_node,
    synthesis_node,
    _parse_analysis_response,
)
from src.agents.monitoring.state import MonitoringState
from src.models.stock import News


class TestMonitoringAgentNodes:
    """Monitoring Agent Nodes 단위 테스트"""

    @pytest.mark.asyncio
    async def test_fetch_portfolio_node_success(self):
        """포트폴리오 조회 성공 테스트"""
        state = MonitoringState(
            user_id="3bd04ffb-350a-5fa4-bee5-6ce019fdad9c",
            messages=[],
        )

        mock_snapshot = Mock()
        mock_snapshot.portfolio_data = {
            "holdings": [
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 10,
                    "avg_price": 70000.0,
                },
                {
                    "stock_code": "000660",
                    "stock_name": "SK하이닉스",
                    "quantity": 5,
                    "avg_price": 150000.0,
                },
                {
                    "stock_code": "CASH",
                    "stock_name": "현금",
                    "quantity": 1,
                    "avg_price": 1000000.0,
                },
            ]
        }

        with patch("src.agents.monitoring.nodes.portfolio_service") as mock_service:
            mock_service.get_portfolio_snapshot = AsyncMock(return_value=mock_snapshot)

            result = await fetch_portfolio_node(state)

            assert "portfolio_stocks" in result
            assert len(result["portfolio_stocks"]) == 2  # CASH 제외
            assert result["portfolio_stocks"][0]["stock_code"] == "005930"
            assert result["portfolio_stocks"][1]["stock_code"] == "000660"

    @pytest.mark.asyncio
    async def test_fetch_portfolio_node_no_user_id(self):
        """user_id 없이 호출 시 에러"""
        state = MonitoringState(messages=[])

        result = await fetch_portfolio_node(state)

        assert "error" in result
        assert "user_id is required" in result["error"]

    @pytest.mark.asyncio
    async def test_fetch_portfolio_node_empty_portfolio(self):
        """빈 포트폴리오 처리"""
        state = MonitoringState(
            user_id="3bd04ffb-350a-5fa4-bee5-6ce019fdad9c",
            messages=[],
        )

        with patch("src.agents.monitoring.nodes.portfolio_service") as mock_service:
            mock_service.get_portfolio_snapshot = AsyncMock(return_value=None)

            result = await fetch_portfolio_node(state)

            assert "portfolio_stocks" in result
            assert len(result["portfolio_stocks"]) == 0
            assert len(result["messages"]) == 1

    @pytest.mark.asyncio
    async def test_collect_news_node_success(self):
        """뉴스 수집 성공 테스트"""
        state = MonitoringState(
            portfolio_stocks=[
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 10,
                    "avg_price": 70000.0,
                }
            ],
            max_news_per_stock=5,
            messages=[],
        )

        mock_news_list = [
            News(
                news_id=uuid4(),
                title="삼성전자 3분기 실적 발표",
                summary="영업이익 7조원 돌파",
                url="https://example.com/news1",
                source="네이버 뉴스",
                related_stocks=["005930"],
                published_at=datetime.now(),
            )
        ]

        with patch("src.agents.monitoring.nodes.get_news_service") as mock_service:
            mock_instance = AsyncMock()
            mock_instance.fetch_stock_news.return_value = mock_news_list
            mock_instance.save_news.return_value = 1
            mock_service.return_value = mock_instance

            result = await collect_news_node(state)

            assert "news_items" in result
            assert len(result["news_items"]) == 1
            assert result["news_items"][0]["stock_code"] == "005930"

    @pytest.mark.asyncio
    async def test_collect_news_node_empty_portfolio(self):
        """빈 포트폴리오에서 뉴스 수집"""
        state = MonitoringState(portfolio_stocks=[], messages=[])

        result = await collect_news_node(state)

        assert "news_items" in result
        assert len(result["news_items"]) == 0

    @pytest.mark.asyncio
    async def test_analyze_news_node_success(self):
        """뉴스 분석 성공 테스트"""
        state = MonitoringState(
            news_items=[
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "title": "삼성전자 3분기 실적 발표",
                    "summary": "영업이익 7조원 돌파",
                    "url": "https://example.com/news1",
                    "source": "네이버 뉴스",
                    "published_at": datetime.now().isoformat(),
                }
            ],
            messages=[],
        )

        mock_llm_response = """
[1]
중요도: high
감정: positive
요약: 3분기 실적이 시장 예상치를 크게 상회하여 긍정적입니다.
"""

        with patch("src.agents.monitoring.nodes.get_llm") as mock_llm_factory:
            mock_llm = AsyncMock()
            mock_llm.ainvoke.return_value = Mock(content=mock_llm_response)
            mock_llm_factory.return_value = mock_llm

            result = await analyze_news_node(state)

            assert "analyzed_news" in result
            assert len(result["analyzed_news"]) == 1
            assert result["analyzed_news"][0]["importance"] == "high"
            assert result["analyzed_news"][0]["sentiment"] == "positive"

    @pytest.mark.asyncio
    async def test_analyze_news_node_empty_news(self):
        """빈 뉴스 리스트 분석"""
        state = MonitoringState(news_items=[], messages=[])

        result = await analyze_news_node(state)

        assert "analyzed_news" in result
        assert len(result["analyzed_news"]) == 0

    def test_parse_analysis_response(self):
        """LLM 응답 파싱 테스트"""
        text = """
[1]
중요도: high
감정: positive
요약: 실적이 좋습니다.

[2]
중요도: medium
감정: neutral
요약: 일반적인 뉴스입니다.
"""

        result = _parse_analysis_response(text, 2)

        assert len(result) == 2
        assert result[1]["importance"] == "high"
        assert result[1]["sentiment"] == "positive"
        assert result[1]["summary"] == "실적이 좋습니다."
        assert result[2]["importance"] == "medium"

    @pytest.mark.asyncio
    async def test_generate_alerts_node_success(self):
        """알림 생성 성공 테스트"""
        state = MonitoringState(
            analyzed_news=[
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "title": "삼성전자 3분기 실적 발표",
                    "summary": "영업이익 7조원 돌파",
                    "url": "https://example.com/news1",
                    "source": "네이버 뉴스",
                    "published_at": datetime.now().isoformat(),
                    "importance": "high",
                    "sentiment": "positive",
                    "ai_summary": "3분기 실적이 매우 좋습니다.",
                },
                {
                    "stock_code": "000660",
                    "stock_name": "SK하이닉스",
                    "title": "SK하이닉스 일반 뉴스",
                    "summary": "일반적인 내용",
                    "url": "https://example.com/news2",
                    "source": "네이버 뉴스",
                    "published_at": datetime.now().isoformat(),
                    "importance": "low",
                    "sentiment": "neutral",
                    "ai_summary": "일반적인 뉴스입니다.",
                },
            ],
            importance_threshold="medium",
            messages=[],
        )

        result = await generate_alerts_node(state)

        assert "alerts" in result
        # high 중요도만 알림 생성 (medium 임계값)
        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["stock_code"] == "005930"
        assert result["alerts"][0]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_generate_alerts_node_no_important_news(self):
        """중요한 뉴스가 없을 때"""
        state = MonitoringState(
            analyzed_news=[
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "title": "일반 뉴스",
                    "summary": "일반적인 내용",
                    "url": "https://example.com/news1",
                    "source": "네이버 뉴스",
                    "published_at": datetime.now().isoformat(),
                    "importance": "low",
                    "sentiment": "neutral",
                    "ai_summary": "일반 뉴스입니다.",
                }
            ],
            importance_threshold="high",
            messages=[],
        )

        result = await generate_alerts_node(state)

        assert "alerts" in result
        assert len(result["alerts"]) == 0

    @pytest.mark.asyncio
    async def test_synthesis_node_with_alerts(self):
        """알림이 있을 때 최종 메시지 생성"""
        state = MonitoringState(
            alerts=[
                {
                    "type": "news",
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "title": "삼성전자 3분기 실적 발표",
                    "message": "📈 3분기 실적이 매우 좋습니다.",
                    "importance": "high",
                    "sentiment": "positive",
                    "url": "https://example.com/news1",
                    "published_at": datetime.now().isoformat(),
                    "priority": "high",
                }
            ],
            portfolio_stocks=[{"stock_code": "005930", "stock_name": "삼성전자"}],
            messages=[],
        )

        result = await synthesis_node(state)

        assert "messages" in result
        assert len(result["messages"]) == 1
        message_content = result["messages"][0].content
        assert "삼성전자" in message_content
        assert "📰" in message_content

    @pytest.mark.asyncio
    async def test_synthesis_node_no_alerts(self):
        """알림이 없을 때"""
        state = MonitoringState(
            alerts=[],
            portfolio_stocks=[{"stock_code": "005930", "stock_name": "삼성전자"}],
            messages=[],
        )

        result = await synthesis_node(state)

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert "중요한 뉴스가 없습니다" in result["messages"][0].content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
