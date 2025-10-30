"""
StockIndicator 테이블 Repository
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import select

from src.models.database import SessionLocal
from src.models.stock import StockIndicator

from .base import BaseRepository


class StockIndicatorRepository(BaseRepository):
    """기술적 지표 스냅샷 저장/조회"""

    def __init__(self):
        super().__init__(SessionLocal)

    def upsert(self, stock_code: str, date_: date, payload: Dict[str, Any]) -> None:
        with self.session_scope() as session:
            instance = (
                session.query(StockIndicator)
                .filter(
                    StockIndicator.stock_code == stock_code,
                    StockIndicator.date == date_,
                )
                .first()
            )
            if instance is None:
                instance = StockIndicator(stock_code=stock_code, date=date_)
                session.add(instance)

            for key, value in payload.items():
                if key in {"indicator_id", "stock_code", "date"}:
                    continue
                setattr(instance, key, value)

    def bulk_upsert(self, stock_code: str, rows: Iterable[Dict[str, Any]]) -> int:
        count = 0
        with self.session_scope() as session:
            for row in rows:
                date_ = row.get("date")
                if date_ is None:
                    continue
                instance = (
                    session.query(StockIndicator)
                    .filter(
                        StockIndicator.stock_code == stock_code,
                        StockIndicator.date == date_,
                    )
                    .first()
                )
                if instance is None:
                    instance = StockIndicator(stock_code=stock_code, date=date_)
                    session.add(instance)

                for key, value in row.items():
                    if key in {"indicator_id", "stock_code", "date"}:
                        continue
                    setattr(instance, key, value)
                count += 1
        return count

    def latest(self, stock_code: str) -> Optional[StockIndicator]:
        stmt = (
            select(StockIndicator)
            .where(StockIndicator.stock_code == stock_code)
            .order_by(StockIndicator.date.desc())
            .limit(1)
        )
        with self.session_scope() as session:
            return session.execute(stmt).scalar_one_or_none()


stock_indicator_repository = StockIndicatorRepository()
