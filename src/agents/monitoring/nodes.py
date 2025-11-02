"""Monitoring Agent Nodes"""
import logging
from typing import Dict, Any, List
from datetime import datetime
from uuid import UUID

from langchain_core.messages import HumanMessage, AIMessage

from src.agents.monitoring.state import MonitoringState
from src.services import portfolio_service
from src.services.news_crawler_service import get_news_service
from src.repositories.news_repository import news_repository
from src.utils.llm_factory import get_llm

logger = logging.getLogger(__name__)


async def fetch_portfolio_node(state: MonitoringState) -> Dict[str, Any]:
    """
    사용자 포트폴리오 조회 노드

    사용자의 포트폴리오에서 보유 종목 목록을 가져옵니다.
    """
    user_id_str = state.get("user_id")

    if not user_id_str:
        logger.error("❌ [MonitoringAgent] user_id가 없습니다.")
        return {"error": "user_id is required"}

    try:
        # PortfolioService를 사용하여 포트폴리오 스냅샷 조회
        snapshot = await portfolio_service.get_portfolio_snapshot(
            user_id=user_id_str
        )

        if not snapshot:
            logger.warning(f"⚠️ [MonitoringAgent] 포트폴리오 없음: {user_id_str}")
            return {
                "portfolio_stocks": [],
                "messages": [AIMessage(content="포트폴리오가 비어있습니다.")],
            }

        # 보유 종목 리스트 추출
        stocks = []
        holdings = snapshot.portfolio_data.get("holdings", [])

        for holding in holdings:
            stock_code = holding.get("stock_code")
            if stock_code and stock_code != "CASH":  # CASH 제외
                stocks.append({
                    "stock_code": stock_code,
                    "stock_name": holding.get("stock_name", stock_code),
                    "quantity": holding.get("quantity", 0),
                    "avg_price": float(holding.get("avg_price", 0)),
                })

        logger.info(f"✅ [MonitoringAgent] 포트폴리오 종목 {len(stocks)}개 조회 완료")

        return {"portfolio_stocks": stocks}

    except Exception as e:
        logger.error(f"❌ [MonitoringAgent] 포트폴리오 조회 실패: {e}")
        return {"error": f"포트폴리오 조회 실패: {str(e)}"}


async def collect_news_node(state: MonitoringState) -> Dict[str, Any]:
    """
    종목별 뉴스 수집 노드

    포트폴리오 종목들에 대한 최신 뉴스를 수집합니다.
    """
    portfolio_stocks = state.get("portfolio_stocks", [])
    max_news_per_stock = state.get("max_news_per_stock", 10)

    if not portfolio_stocks:
        logger.warning("⚠️ [MonitoringAgent] 포트폴리오 종목이 없습니다.")
        return {"news_items": []}

    try:
        news_service = get_news_service()
        all_news = []

        for stock in portfolio_stocks:
            stock_code = stock["stock_code"]
            stock_name = stock["stock_name"]

            # 네이버 API로 뉴스 검색
            logger.info(f"📰 [MonitoringAgent] {stock_name}({stock_code}) 뉴스 수집 중...")
            news_list = await news_service.fetch_stock_news(
                stock_code=stock_code,
                stock_name=stock_name,
                max_articles=max_news_per_stock,
            )

            # DB에 저장
            await news_service.save_news(news_list)

            # 결과 변환
            for news in news_list:
                all_news.append({
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "title": news.title,
                    "summary": news.summary,
                    "url": news.url,
                    "source": news.source,
                    "published_at": news.published_at.isoformat(),
                })

        logger.info(f"✅ [MonitoringAgent] 총 {len(all_news)}개 뉴스 수집 완료")

        return {"news_items": all_news}

    except Exception as e:
        logger.error(f"❌ [MonitoringAgent] 뉴스 수집 실패: {e}")
        return {"error": f"뉴스 수집 실패: {str(e)}"}


async def analyze_news_node(state: MonitoringState) -> Dict[str, Any]:
    """
    뉴스 분석 노드

    LLM을 사용하여 뉴스의 중요도, 감정(긍정/부정/중립), 요약을 분석합니다.
    """
    news_items = state.get("news_items", [])

    if not news_items:
        logger.warning("⚠️ [MonitoringAgent] 분석할 뉴스가 없습니다.")
        return {"analyzed_news": []}

    try:
        llm = get_llm()
        analyzed_news = []

        # 배치 처리 (최대 20개씩)
        batch_size = 20
        for i in range(0, len(news_items), batch_size):
            batch = news_items[i:i + batch_size]

            # 뉴스 리스트를 텍스트로 변환
            news_text = "\n\n".join([
                f"[{idx + 1}] {item['stock_name']}({item['stock_code']})\n"
                f"제목: {item['title']}\n"
                f"요약: {item.get('summary', 'N/A')}"
                for idx, item in enumerate(batch)
            ])

            prompt = f"""다음 뉴스들을 분석하여 각각에 대해 중요도, 감정, 간단한 요약을 제공하세요.

뉴스 목록:
{news_text}

각 뉴스에 대해 다음 형식으로 응답하세요:

[번호]
중요도: high/medium/low (투자 결정에 미치는 영향도)
감정: positive/negative/neutral (주가에 미치는 영향)
요약: 한 문장으로 핵심 내용 요약

응답 예시:
[1]
중요도: high
감정: positive
요약: 3분기 실적이 시장 예상치를 크게 상회하여 긍정적입니다.
"""

            response = await llm.ainvoke(prompt)
            analysis_text = response.content if hasattr(response, 'content') else str(response)

            # 응답 파싱 (간단한 파싱)
            parsed_analyses = _parse_analysis_response(analysis_text, len(batch))

            # 원본 뉴스와 분석 결과 병합
            for idx, item in enumerate(batch):
                analysis = parsed_analyses.get(idx + 1, {
                    "importance": "medium",
                    "sentiment": "neutral",
                    "summary": item.get("summary", item["title"])[:100]
                })

                analyzed_news.append({
                    **item,
                    "importance": analysis["importance"],
                    "sentiment": analysis["sentiment"],
                    "ai_summary": analysis["summary"],
                })

        logger.info(f"✅ [MonitoringAgent] {len(analyzed_news)}개 뉴스 분석 완료")

        return {"analyzed_news": analyzed_news}

    except Exception as e:
        logger.error(f"❌ [MonitoringAgent] 뉴스 분석 실패: {e}")
        return {"error": f"뉴스 분석 실패: {str(e)}"}


def _parse_analysis_response(text: str, expected_count: int) -> Dict[int, Dict[str, str]]:
    """
    LLM 응답 파싱 헬퍼

    Args:
        text: LLM 응답 텍스트
        expected_count: 예상 뉴스 개수

    Returns:
        {1: {"importance": "high", "sentiment": "positive", "summary": "..."}, ...}
    """
    results = {}
    lines = text.strip().split("\n")

    current_idx = None
    current_data = {}

    for line in lines:
        line = line.strip()

        # [1], [2], ... 형식 감지
        if line.startswith("[") and line.endswith("]"):
            if current_idx and current_data:
                results[current_idx] = current_data

            try:
                current_idx = int(line[1:-1])
                current_data = {}
            except ValueError:
                continue

        # 중요도: ...
        elif line.startswith("중요도:"):
            importance_value = line.split(":", 1)[1].strip().lower()
            if importance_value in ["high", "medium", "low"]:
                current_data["importance"] = importance_value

        # 감정: ...
        elif line.startswith("감정:"):
            sentiment_value = line.split(":", 1)[1].strip().lower()
            if sentiment_value in ["positive", "negative", "neutral"]:
                current_data["sentiment"] = sentiment_value

        # 요약: ...
        elif line.startswith("요약:"):
            summary_value = line.split(":", 1)[1].strip()
            current_data["summary"] = summary_value

    # 마지막 항목 저장
    if current_idx and current_data:
        results[current_idx] = current_data

    return results


async def generate_alerts_node(state: MonitoringState) -> Dict[str, Any]:
    """
    알림 생성 노드

    중요한 뉴스에 대해 알림을 생성합니다.
    """
    analyzed_news = state.get("analyzed_news", [])
    importance_threshold = state.get("importance_threshold", "medium")

    if not analyzed_news:
        logger.warning("⚠️ [MonitoringAgent] 분석된 뉴스가 없습니다.")
        return {"alerts": []}

    try:
        alerts = []

        # 중요도 우선순위
        importance_priority = {"high": 3, "medium": 2, "low": 1}
        threshold_value = importance_priority.get(importance_threshold, 2)

        for news in analyzed_news:
            news_importance = importance_priority.get(news.get("importance", "low"), 1)

            # 임계값 이상인 경우 알림 생성
            if news_importance >= threshold_value:
                sentiment_emoji = {
                    "positive": "📈",
                    "negative": "📉",
                    "neutral": "➡️",
                }.get(news.get("sentiment", "neutral"), "")

                alert = {
                    "type": "news",
                    "stock_code": news["stock_code"],
                    "stock_name": news["stock_name"],
                    "title": news["title"],
                    "message": f"{sentiment_emoji} {news['ai_summary']}",
                    "importance": news["importance"],
                    "sentiment": news["sentiment"],
                    "url": news["url"],
                    "published_at": news["published_at"],
                    "priority": "high" if news_importance == 3 else "medium",
                }

                alerts.append(alert)

        logger.info(f"✅ [MonitoringAgent] {len(alerts)}개 알림 생성 완료")

        return {"alerts": alerts}

    except Exception as e:
        logger.error(f"❌ [MonitoringAgent] 알림 생성 실패: {e}")
        return {"error": f"알림 생성 실패: {str(e)}"}


async def synthesis_node(state: MonitoringState) -> Dict[str, Any]:
    """
    최종 메시지 생성 노드

    수집된 알림을 사용자에게 보여줄 메시지로 변환합니다.
    """
    alerts = state.get("alerts", [])
    portfolio_stocks = state.get("portfolio_stocks", [])

    if not alerts:
        message = f"✅ 포트폴리오 {len(portfolio_stocks)}개 종목에 대한 중요한 뉴스가 없습니다."
    else:
        # 종목별로 그룹핑
        alerts_by_stock = {}
        for alert in alerts:
            stock_code = alert["stock_code"]
            if stock_code not in alerts_by_stock:
                alerts_by_stock[stock_code] = []
            alerts_by_stock[stock_code].append(alert)

        # 메시지 생성
        message_parts = [f"📰 포트폴리오 뉴스 알림 ({len(alerts)}건)\n"]

        for stock_code, stock_alerts in alerts_by_stock.items():
            stock_name = stock_alerts[0]["stock_name"]
            message_parts.append(f"\n**{stock_name} ({stock_code})**")

            for alert in stock_alerts[:3]:  # 최대 3개만 표시
                importance_badge = "🔴" if alert["importance"] == "high" else "🟡"
                message_parts.append(
                    f"{importance_badge} {alert['title']}\n   {alert['message']}"
                )

        message = "\n".join(message_parts)

    logger.info(f"✅ [MonitoringAgent] 최종 메시지 생성 완료")

    return {"messages": [AIMessage(content=message)]}
