"""
뉴스 API 엔드포인트
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.repositories.news_repository import news_repository
from src.services.news_crawler_service import fetch_and_save_news, get_news_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/news", tags=["news"])


class NewsItemResponse(BaseModel):
    """뉴스 항목 응답"""

    news_id: str
    title: str
    summary: Optional[str] = None
    url: str
    source: str
    related_stocks: List[str]
    published_at: str


class NewsFetchRequest(BaseModel):
    """뉴스 수집 요청"""

    stock_code: str = Field(..., description="종목 코드 (예: 005930)")
    stock_name: str = Field(..., description="종목명 (예: 삼성전자)")
    max_articles: int = Field(20, ge=1, le=100, description="최대 수집 기사 수")


class NewsFetchResponse(BaseModel):
    """뉴스 수집 응답"""

    status: str
    message: str
    collected_count: int
    saved_count: int


@router.get("/{stock_code}", response_model=List[NewsItemResponse])
async def get_stock_news(
    stock_code: str,
    limit: int = Query(20, ge=1, le=100, description="조회할 뉴스 개수"),
):
    """
    종목별 뉴스 조회 (DB에서)

    Args:
        stock_code: 종목 코드
        limit: 조회할 뉴스 개수 (기본 20개)

    Returns:
        뉴스 리스트
    """
    try:
        news_list = news_repository.list_recent(limit=limit)

        # 특정 종목 필터링
        filtered_news = [
            news
            for news in news_list
            if stock_code in (news.related_stocks or [])
        ]

        return [
            NewsItemResponse(
                news_id=str(news.news_id),
                title=news.title,
                summary=news.summary,
                url=news.url,
                source=news.source,
                related_stocks=news.related_stocks or [],
                published_at=news.published_at.isoformat(),
            )
            for news in filtered_news
        ]
    except Exception as e:
        logger.error(f"❌ [NewsAPI] 뉴스 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="뉴스 조회 중 오류 발생")


@router.post("/fetch", response_model=NewsFetchResponse)
async def fetch_news(request: NewsFetchRequest):
    """
    뉴스 수집 (네이버 API 호출)

    Args:
        request: 뉴스 수집 요청 (종목 코드, 종목명, 최대 개수)

    Returns:
        수집 결과
    """
    try:
        logger.info(
            f"📰 [NewsAPI] 뉴스 수집 요청: {request.stock_name} ({request.stock_code})"
        )

        # 네이버 API로 뉴스 검색
        service = get_news_service()
        news_list = await service.fetch_stock_news(
            stock_code=request.stock_code,
            stock_name=request.stock_name,
            max_articles=request.max_articles,
        )

        # DB에 저장
        saved_count = await service.save_news(news_list)

        return NewsFetchResponse(
            status="success",
            message=f"{request.stock_name} 뉴스 수집 완료",
            collected_count=len(news_list),
            saved_count=saved_count,
        )
    except Exception as e:
        logger.error(f"❌ [NewsAPI] 뉴스 수집 실패: {e}")
        raise HTTPException(status_code=500, detail=f"뉴스 수집 중 오류 발생: {str(e)}")


@router.get("/recent", response_model=List[NewsItemResponse])
async def get_recent_news(
    limit: int = Query(50, ge=1, le=100, description="조회할 뉴스 개수"),
):
    """
    최근 뉴스 조회 (모든 종목)

    Args:
        limit: 조회할 뉴스 개수 (기본 50개)

    Returns:
        최근 뉴스 리스트
    """
    try:
        news_list = news_repository.list_recent(limit=limit)

        return [
            NewsItemResponse(
                news_id=str(news.news_id),
                title=news.title,
                summary=news.summary,
                url=news.url,
                source=news.source,
                related_stocks=news.related_stocks or [],
                published_at=news.published_at.isoformat(),
            )
            for news in news_list
        ]
    except Exception as e:
        logger.error(f"❌ [NewsAPI] 최근 뉴스 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="뉴스 조회 중 오류 발생")
