"""뉴스 수집 및 분석 통합 테스트"""
import pytest

from src.subgraphs.research_subgraph.nodes import (
    data_worker_node,
    information_worker_node,
)
from src.subgraphs.research_subgraph.state import ResearchState


@pytest.mark.asyncio
async def test_news_collection_in_data_worker():
    """data_worker_node가 뉴스 데이터를 수집하는지 테스트"""
    # Given: 삼성전자 종목 코드
    initial_state: ResearchState = {
        "stock_code": "005930",
        "query": "삼성전자 분석해줘",
        "request_id": "test-news-collection",
        "messages": [],
    }

    # When: data_worker_node 실행
    result = await data_worker_node(initial_state)

    # Then: 뉴스 데이터가 State에 포함되어야 함
    assert "news_data" in result, "news_data 필드가 State에 있어야 합니다"
    news_data = result["news_data"]

    # 뉴스가 수집되었거나 빈 리스트여야 함 (API 키가 없을 수 있음)
    assert isinstance(news_data, list), "news_data는 리스트여야 합니다"

    # 뉴스가 수집된 경우
    if len(news_data) > 0:
        first_news = news_data[0]
        assert "title" in first_news, "뉴스는 title 필드를 가져야 합니다"
        assert "summary" in first_news, "뉴스는 summary 필드를 가져야 합니다"
        assert "url" in first_news, "뉴스는 url 필드를 가져야 합니다"
        assert "source" in first_news, "뉴스는 source 필드를 가져야 합니다"
        assert "published_at" in first_news, "뉴스는 published_at 필드를 가져야 합니다"
        print(f"✅ 뉴스 {len(news_data)}건 수집 완료")
        print(f"   첫 번째 뉴스: {first_news['title']}")
    else:
        print("⚠️  뉴스가 수집되지 않았습니다 (API 키 없음 또는 데이터 없음)")

    # 다른 데이터도 정상적으로 수집되어야 함
    assert "stock_code" in result
    assert "price_data" in result
    assert "company_data" in result


@pytest.mark.asyncio
async def test_news_usage_in_information_worker():
    """information_worker_node가 뉴스 데이터를 활용하는지 테스트"""
    # Given: data_worker의 결과를 포함한 State (뉴스 포함)
    state_with_news: ResearchState = {
        "stock_code": "005930",
        "query": "삼성전자 정보 분석",
        "messages": [],
        "price_data": {
            "latest_close": 70000,
            "latest_volume": 10000000,
            "change_rate": 1.5,
        },
        "fundamental_data": {
            "PER": 15.5,
            "PBR": 1.2,
            "EPS": 4500,
        },
        "technical_indicators": {
            "RSI": 55.0,
            "MACD": {"macd": 100, "signal": 90},
        },
        "company_data": {
            "info": {
                "corp_name": "삼성전자",
                "ceo_nm": "이재용",
            }
        },
        "macro_analysis": {
            "analysis": {
                "summary": "경기 회복세",
                "interest_rate": 3.5,
            }
        },
        "news_data": [
            {
                "title": "삼성전자, 신규 AI 칩 개발",
                "summary": "삼성전자가 차세대 AI 칩을 개발했다고 발표",
                "url": "https://example.com/news1",
                "source": "네이버 뉴스",
                "published_at": "2024-01-15T10:00:00",
            },
            {
                "title": "삼성전자 실적 호조",
                "summary": "삼성전자 4분기 실적이 예상을 상회",
                "url": "https://example.com/news2",
                "source": "네이버 뉴스",
                "published_at": "2024-01-14T09:00:00",
            },
        ],
    }

    # When: information_worker_node 실행
    result = await information_worker_node(state_with_news)

    # Then: 정보 분석 결과가 생성되어야 함
    assert "information_analysis" in result, "information_analysis가 State에 있어야 합니다"
    analysis = result["information_analysis"]

    assert isinstance(analysis, dict), "분석 결과는 딕셔너리여야 합니다"
    assert "market_sentiment" in analysis, "market_sentiment 필드가 있어야 합니다"
    assert "risk_level" in analysis, "risk_level 필드가 있어야 합니다"

    print(f"✅ 정보 분석 완료:")
    print(f"   시장 센티먼트: {analysis.get('market_sentiment')}")
    print(f"   리스크 레벨: {analysis.get('risk_level')}")
    print(f"   요약: {analysis.get('summary', 'N/A')}")


@pytest.mark.asyncio
async def test_information_worker_without_news():
    """뉴스가 없어도 information_worker_node가 정상 동작하는지 테스트"""
    # Given: 뉴스가 없는 State
    state_without_news: ResearchState = {
        "stock_code": "005930",
        "query": "삼성전자 정보 분석",
        "messages": [],
        "price_data": {
            "latest_close": 70000,
            "latest_volume": 10000000,
        },
        "fundamental_data": {
            "PER": 15.5,
            "PBR": 1.2,
        },
        "technical_indicators": {
            "RSI": 55.0,
        },
        "company_data": {
            "info": {
                "corp_name": "삼성전자",
            }
        },
        "macro_analysis": {},
        # news_data가 없음 (또는 빈 리스트)
    }

    # When: information_worker_node 실행
    result = await information_worker_node(state_without_news)

    # Then: 뉴스 없이도 정상 동작해야 함 (호환성)
    assert "information_analysis" in result
    analysis = result["information_analysis"]

    assert isinstance(analysis, dict)
    assert "market_sentiment" in analysis
    assert "risk_level" in analysis

    print(f"✅ 뉴스 없이도 정보 분석 완료:")
    print(f"   시장 센티먼트: {analysis.get('market_sentiment')}")
    print(f"   리스크 레벨: {analysis.get('risk_level')}")


if __name__ == "__main__":
    import asyncio

    print("=" * 60)
    print("뉴스 수집 및 분석 통합 테스트 시작")
    print("=" * 60)

    # Test 1: 뉴스 수집
    print("\n[Test 1] data_worker_node 뉴스 수집 테스트")
    asyncio.run(test_news_collection_in_data_worker())

    # Test 2: 뉴스 활용
    print("\n[Test 2] information_worker_node 뉴스 활용 테스트")
    asyncio.run(test_news_usage_in_information_worker())

    # Test 3: 뉴스 없을 때
    print("\n[Test 3] information_worker_node 뉴스 없을 때 테스트")
    asyncio.run(test_information_worker_without_news())

    print("\n" + "=" * 60)
    print("모든 테스트 완료!")
    print("=" * 60)
