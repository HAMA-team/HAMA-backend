"""
Stock 테이블에 대한 Repository
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable, List, Optional

from sqlalchemy import select

from src.models.database import SessionLocal
from src.models.stock import Stock

from .base import BaseRepository


class StockRepository(BaseRepository):
    """주식 기본 정보 저장/조회 기능 제공"""

    def __init__(self):
        super().__init__(SessionLocal)

    def get_by_code(self, stock_code: str) -> Optional[Stock]:
        with self.session_scope() as session:
            return session.get(Stock, stock_code)

    def list_by_market(self, market: Optional[str] = None) -> List[Stock]:
        stmt = select(Stock)
        if market:
            stmt = stmt.where(Stock.market == market)

        with self.session_scope() as session:
            return list(session.execute(stmt).scalars().all())

    def upsert_many(self, records: Iterable[dict]) -> int:
        """Stock 엔트리를 일괄 upsert"""
        count = 0
        with self.session_scope() as session:
            for payload in records:
                if not payload.get("stock_code"):
                    continue
                stock_code = payload["stock_code"]
                instance = session.get(Stock, stock_code)
                if instance is None:
                    instance = Stock(stock_code=stock_code, market=payload.get("market", ""))
                    session.add(instance)

                for key, value in payload.items():
                    if key == "listing_date" and isinstance(value, str):
                        try:
                            value = date.fromisoformat(value)
                        except ValueError:
                            continue
                    setattr(instance, key, value)
                count += 1
        return count

    def update_fields(self, stock_code: str, **fields: Any) -> None:
        if not fields:
            return

        with self.session_scope() as session:
            instance = session.get(Stock, stock_code)
            if instance is None:
                return

            for key, value in fields.items():
                setattr(instance, key, value)


stock_repository = StockRepository()
