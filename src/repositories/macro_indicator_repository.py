"""
MacroIndicator 테이블 Repository
"""
from __future__ import annotations

from datetime import date
from typing import Iterable, List, Optional, Dict, Any

from sqlalchemy import select

from src.models.database import SessionLocal
from src.models.macro import MacroIndicator

from .base import BaseRepository


class MacroIndicatorRepository(BaseRepository):
    """거시 지표 저장/조회 Repository"""

    def __init__(self):
        super().__init__(SessionLocal)

    def upsert_many(self, indicator_code: str, rows: Iterable[Dict[str, Any]]) -> int:
        count = 0
        with self.session_scope() as session:
            for row in rows:
                reference_date: date = row["reference_date"]
                instance = (
                    session.query(MacroIndicator)
                    .filter(
                        MacroIndicator.indicator_code == indicator_code,
                        MacroIndicator.reference_date == reference_date,
                    )
                    .first()
                )
                if instance is None:
                    instance = MacroIndicator(
                        indicator_code=indicator_code,
                        reference_date=reference_date,
                        indicator_name=row.get("indicator_name", indicator_code),
                        frequency=row.get("frequency", "M"),
                        country=row.get("country", "KR"),
                        unit=row.get("unit"),
                        source=row.get("source", "BOK"),
                        value=row.get("value"),
                        raw_data=row.get("raw_data"),
                    )
                    session.add(instance)
                else:
                    for key in [
                        "indicator_name",
                        "frequency",
                        "unit",
                        "source",
                        "country",
                        "value",
                        "raw_data",
                    ]:
                        if key in row:
                            setattr(instance, key, row[key])
                count += 1
        return count

    def latest(self, indicator_code: str) -> Optional[MacroIndicator]:
        stmt = (
            select(MacroIndicator)
            .where(MacroIndicator.indicator_code == indicator_code)
            .order_by(MacroIndicator.reference_date.desc())
            .limit(1)
        )
        with self.session_scope() as session:
            return session.execute(stmt).scalar_one_or_none()

    def get_series(
        self,
        indicator_code: str,
        limit: int = 120,
        ascending: bool = False,
    ) -> List[MacroIndicator]:
        stmt = (
            select(MacroIndicator)
            .where(MacroIndicator.indicator_code == indicator_code)
            .order_by(
                MacroIndicator.reference_date.asc() if ascending else MacroIndicator.reference_date.desc()
            )
            .limit(limit)
        )
        with self.session_scope() as session:
            rows = session.execute(stmt).scalars().all()
            if ascending:
                return rows
            return list(reversed(rows))


macro_indicator_repository = MacroIndicatorRepository()
