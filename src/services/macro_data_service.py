"""매크로 경제 데이터 서비스"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from src.repositories import macro_indicator_repository
from src.services.bok_service import bok_service


def _parse_reference_date(time_str: str, frequency: str) -> date:
    if frequency == "D":
        return datetime.strptime(time_str, "%Y%m%d").date()
    if frequency == "Q":
        year = int(time_str[:4])
        quarter = time_str[-1]
        month_map = {"1": 1, "2": 4, "3": 7, "4": 10}
        month = month_map.get(quarter, 1)
        return date(year, month, 1)
    # 기본 월 단위
    dt = datetime.strptime(time_str, "%Y%m")
    return date(dt.year, dt.month, 1)


class MacroDataService:
    """BOK API와 로컬 DB를 통합 관리하는 서비스"""

    def __init__(self):
        self._bok = bok_service
        self._repository = macro_indicator_repository

    @staticmethod
    def _build_rows(
        indicator_code: str,
        indicator_name: str,
        frequency: str,
        unit: Optional[str],
        source: str,
        rows: List[Dict],
    ) -> List[Dict]:
        parsed: List[Dict] = []
        for row in rows:
            time_key = row.get("TIME") or row.get("TIME")
            if not time_key:
                continue
            try:
                reference_date = _parse_reference_date(time_key, frequency)
            except ValueError:
                continue

            raw_value = row.get("DATA_VALUE")
            if raw_value in (None, "", "."):
                continue

            try:
                value = Decimal(str(raw_value))
            except Exception:
                continue

            parsed.append(
                {
                    "indicator_name": indicator_name,
                    "frequency": frequency,
                    "unit": unit,
                    "source": source,
                    "country": "KR",
                    "reference_date": reference_date,
                    "value": value,
                    "raw_data": row,
                }
            )

        return parsed

    async def refresh_base_rate(self, start: Optional[str] = None, end: Optional[str] = None) -> int:
        rows = await asyncio.to_thread(self._bok.get_base_rate, start, end)
        payload = self._build_rows(
            indicator_code="base_rate",
            indicator_name="기준금리",
            frequency="M",
            unit="%",
            source="BOK",
            rows=rows,
        )
        return self._repository.upsert_many("base_rate", payload)

    async def refresh_cpi(self, start: Optional[str] = None, end: Optional[str] = None) -> int:
        rows = await asyncio.to_thread(self._bok.get_cpi, start, end)
        payload = self._build_rows(
            indicator_code="cpi",
            indicator_name="소비자물가지수",
            frequency="M",
            unit="지수",
            source="BOK",
            rows=rows,
        )
        return self._repository.upsert_many("cpi", payload)

    async def refresh_exchange_rate(self, start: Optional[str] = None, end: Optional[str] = None) -> int:
        rows = await asyncio.to_thread(self._bok.get_exchange_rate, start, end)
        payload = self._build_rows(
            indicator_code="usdkrw",
            indicator_name="원/달러 환율",
            frequency="D",
            unit="KRW",
            source="BOK",
            rows=rows,
        )
        return self._repository.upsert_many("usdkrw", payload)

    async def refresh_all(self) -> Dict[str, int]:
        base = await self.refresh_base_rate()
        cpi = await self.refresh_cpi()
        fx = await self.refresh_exchange_rate()
        return {
            "base_rate": base,
            "cpi": cpi,
            "usdkrw": fx,
        }

    def latest_snapshot(self) -> Dict[str, Optional[Decimal]]:
        base = self._repository.latest("base_rate")
        cpi = self._repository.latest("cpi")
        fx = self._repository.latest("usdkrw")

        return {
            "base_rate": base.value if base else None,
            "base_rate_date": base.reference_date.isoformat() if base else None,
            "cpi": cpi.value if cpi else None,
            "cpi_date": cpi.reference_date.isoformat() if cpi else None,
            "usdkrw": fx.value if fx else None,
            "usdkrw_date": fx.reference_date.isoformat() if fx else None,
        }

    def macro_summary(self) -> Dict[str, Optional[Decimal]]:
        base_series = self._repository.get_series("base_rate", limit=2, ascending=True)
        cpi_series = self._repository.get_series("cpi", limit=13, ascending=True)
        fx_latest = self._repository.latest("usdkrw")

        result = {
            "base_rate": None,
            "base_rate_trend": "유지",
            "cpi": None,
            "cpi_yoy": None,
            "exchange_rate": fx_latest.value if fx_latest else None,
        }

        if base_series:
            latest_base = base_series[-1]
            result["base_rate"] = latest_base.value
            if len(base_series) > 1:
                prev = base_series[-2].value
                if prev is not None and latest_base.value is not None:
                    if latest_base.value > prev:
                        result["base_rate_trend"] = "상승"
                    elif latest_base.value < prev:
                        result["base_rate_trend"] = "하락"

        if cpi_series:
            latest_cpi = cpi_series[-1]
            result["cpi"] = latest_cpi.value
            if len(cpi_series) >= 13:
                year_ago = cpi_series[-13]
                if latest_cpi.value and year_ago.value:
                    result["cpi_yoy"] = ((latest_cpi.value - year_ago.value) / year_ago.value) * 100

        return result


macro_data_service = MacroDataService()


async def seed_macro_data() -> Dict[str, int]:
    """거시 지표 전체를 초기 적재"""
    return await macro_data_service.refresh_all()
