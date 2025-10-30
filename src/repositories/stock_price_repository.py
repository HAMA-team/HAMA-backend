"""
StockPrice 테이블에 대한 Repository
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, List, Optional

from sqlalchemy import select

from src.models.database import SessionLocal
from src.models.stock import StockPrice

from .base import BaseRepository


class StockPriceRepository(BaseRepository):
    """주가 히스토리 저장/조회"""

    def __init__(self):
        super().__init__(SessionLocal)

    def get_prices_since(self, stock_code: str, start: date) -> List[StockPrice]:
        stmt = (
            select(StockPrice)
            .where(
                StockPrice.stock_code == stock_code,
                StockPrice.date >= start,
            )
            .order_by(StockPrice.date.asc())
        )
        with self.session_scope() as session:
            return list(session.execute(stmt).scalars().all())

    def latest_price_date(self, stock_code: str) -> Optional[date]:
        stmt = (
            select(StockPrice.date)
            .where(StockPrice.stock_code == stock_code)
            .order_by(StockPrice.date.desc())
            .limit(1)
        )
        with self.session_scope() as session:
            result = session.execute(stmt).scalar()
            return result

    def upsert_many(self, stock_code: str, rows: Iterable[dict]) -> int:
        """지정한 종목의 주가 데이터 upsert"""
        rows = list(rows)
        if not rows:
            return 0

        requested_dates: List[date] = []
        normalized_rows: List[tuple[date, dict]] = []
        for row in rows:
            raw_date = row.get("date")
            if raw_date is None:
                continue
            if isinstance(raw_date, str):
                try:
                    parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                except ValueError:
                    continue
            else:
                parsed_date = raw_date
            requested_dates.append(parsed_date)
            normalized = dict(row)
            normalized["date"] = parsed_date
            normalized_rows.append((parsed_date, normalized))

        if not normalized_rows:
            return 0

        stmt = (
            select(StockPrice)
            .where(
                StockPrice.stock_code == stock_code,
                StockPrice.date.in_(requested_dates),
            )
        )

        with self.session_scope() as session:
            existing = {
                price.date: price
                for price in session.execute(stmt).scalars().all()
            }

            for target_date, payload in normalized_rows:
                instance = existing.get(target_date)
                if instance is None:
                    instance = StockPrice(stock_code=stock_code, date=target_date)
                    session.add(instance)

                for key, value in payload.items():
                    if key in {"stock_code", "price_id"}:
                        continue
                    setattr(instance, key, value)

        return len(normalized_rows)


stock_price_repository = StockPriceRepository()
