"""
Disclosure 테이블 Repository
"""
from __future__ import annotations

from typing import Iterable, List

from sqlalchemy import select

from src.models.database import SessionLocal
from src.models.stock import Disclosure

from .base import BaseRepository


class DisclosureRepository(BaseRepository):
    """공시 데이터 저장/조회"""

    def __init__(self):
        super().__init__(SessionLocal)

    def bulk_upsert(self, items: Iterable[Disclosure]) -> None:
        with self.session_scope() as session:
            for item in items:
                session.merge(item)

    def list_recent(self, stock_code: str, limit: int = 20) -> List[Disclosure]:
        stmt = (
            select(Disclosure)
            .where(Disclosure.stock_code == stock_code)
            .order_by(Disclosure.submit_date.desc())
            .limit(limit)
        )
        with self.session_scope() as session:
            return list(session.execute(stmt).scalars().all())


disclosure_repository = DisclosureRepository()
