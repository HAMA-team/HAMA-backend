"""
News 테이블 Repository
"""
from __future__ import annotations

from typing import Iterable, List

from sqlalchemy import select

from src.models.database import SessionLocal
from src.models.stock import News

from .base import BaseRepository


class NewsRepository(BaseRepository):
    """뉴스 데이터 저장/조회"""

    def __init__(self):
        super().__init__(SessionLocal)

    def bulk_insert(self, items: Iterable[News]) -> None:
        with self.session_scope() as session:
            for item in items:
                session.merge(item)

    def list_recent(self, limit: int = 50) -> List[News]:
        stmt = (
            select(News)
            .order_by(News.published_at.desc())
            .limit(limit)
        )
        with self.session_scope() as session:
            return list(session.execute(stmt).scalars().all())


news_repository = NewsRepository()
