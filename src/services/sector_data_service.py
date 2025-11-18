"""섹터 데이터 서비스

KIS 업종 지수(혹은 샘플 데이터)를 기반으로 섹터 성과/모멘텀을 제공합니다.
모의 환경이나 KIS 코드가 지원되지 않을 경우 기존 샘플 스냅샷이 사용됩니다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from src.config.settings import settings
from src.services.kis_service import kis_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SectorSnapshot:
    """샘플 섹터 성과 데이터"""

    sector: str
    return_pct: float
    momentum: float
    volatility: float
    trend: str


DEFAULT_SECTOR_SNAPSHOTS: List[SectorSnapshot] = [
    SectorSnapshot("IT/전기전자", 6.4, 0.78, 17.5, "up"),
    SectorSnapshot("2차전지", 5.1, 0.72, 22.3, "up"),
    SectorSnapshot("반도체/장비", 4.6, 0.70, 19.1, "up"),
    SectorSnapshot("인터넷/콘텐츠", 3.8, 0.61, 21.4, "up"),
    SectorSnapshot("자동차/부품", 2.9, 0.55, 15.7, "flat"),
    SectorSnapshot("바이오/제약", 1.2, 0.48, 24.6, "flat"),
    SectorSnapshot("경기소비재", -0.7, 0.42, 13.8, "down"),
    SectorSnapshot("산업재", -1.9, 0.38, 12.5, "down"),
    SectorSnapshot("금융", -2.8, 0.34, 11.2, "down"),
    SectorSnapshot("에너지/화학", -4.1, 0.30, 16.0, "down"),
]

DEFAULT_SECTOR_INDEX_CODES: Dict[str, str] = {
    "KOSPI": "0001",  # 코스피 지수
    "KOSDAQ": "1001",  # 코스닥 지수
    "KOSPI200": "2001",  # 코스피200
}


class SectorDataService:
    """섹터/업종별 성과를 제공하는 서비스"""

    def __init__(
        self,
        snapshots: Optional[List[SectorSnapshot]] = None,
        index_codes: Optional[Dict[str, str]] = None,
    ):
        self._snapshots = snapshots or DEFAULT_SECTOR_SNAPSHOTS
        merged_codes = {
            **DEFAULT_SECTOR_INDEX_CODES,
            **(index_codes or {}),
            **(settings.KIS_SECTOR_INDEX_CODES or {}),
        }
        self._sector_index_codes = {
            str(key).strip(): str(value).strip()
            for key, value in merged_codes.items()
            if key and value
        }

    def _normalize_days(self, days: int) -> int:
        return max(1, days)

    def _scale_snapshot(self, snapshot: SectorSnapshot, scale: float, days: int) -> Dict[str, float]:
        return {
            "return": round(snapshot.return_pct * scale, 2),
            "momentum": snapshot.momentum,
            "volatility": snapshot.volatility,
            "trend": snapshot.trend,
            "days": days,
            "source": "sample",
        }

    async def _fetch_kis_snapshot(
        self, sector: str, days: int
    ) -> Optional[SectorSnapshot]:
        index_code = self._sector_index_codes.get(sector)
        if not index_code:
            return None

        try:
            df = await kis_service.get_index_daily_price(
                index_code=index_code,
                period="D",
                days=days,
            )
        except Exception as exc:
            logger.warning("⚠️ [SectorData] KIS 지수 조회 실패: %s (%s)", sector, exc)
            return None

        if df is None or df.empty:
            return None

        close = df["Close"].dropna()
        if len(close) < 2:
            return None

        start = close.iloc[0]
        end = close.iloc[-1]
        if start == 0:
            return None

        return_pct = round((end - start) / start * 100, 2)
        returns = close.pct_change().dropna()
        momentum = float(returns.tail(min(5, len(returns))).mean() * 100) if not returns.empty else 0.0
        volatility = (
            float(returns.std() * (252 ** 0.5) * 100)
            if len(returns) > 1
            else 0.0
        )
        trend = "up" if return_pct > 0.5 else "down" if return_pct < -0.5 else "flat"

        return SectorSnapshot(sector, return_pct, momentum, volatility, trend)

    async def get_sector_performance(self, days: int = 30) -> Dict[str, Dict]:
        period = self._normalize_days(days)
        scale = period / 30.0

        performance: Dict[str, Dict] = {}
        for snapshot in self._snapshots:
            kis_snapshot = await self._fetch_kis_snapshot(snapshot.sector, period)
            if kis_snapshot:
                performance[snapshot.sector] = {
                    "return": kis_snapshot.return_pct,
                    "momentum": kis_snapshot.momentum,
                    "volatility": kis_snapshot.volatility,
                    "trend": kis_snapshot.trend,
                    "days": period,
                    "source": "KIS",
                }
            else:
                performance[snapshot.sector] = self._scale_snapshot(snapshot, scale, period)

        return performance

    async def get_sector_ranking(self, days: int = 30) -> List[Dict]:
        performance = await self.get_sector_performance(days=days)

        ranking = [
            {
                "sector": sector,
                "return": data["return"],
                "volatility": data["volatility"],
                "trend": data["trend"],
                "momentum": data["momentum"],
                "source": data.get("source", "sample"),
            }
            for sector, data in performance.items()
        ]
        ranking.sort(key=lambda item: item["return"], reverse=True)
        return ranking

    async def get_overweight_sectors(self, days: int = 30, threshold: float = 5.0) -> List[str]:
        performance = await self.get_sector_performance(days=days)
        return [
            sector
            for sector, data in performance.items()
            if data["return"] >= threshold
        ]

    async def get_underweight_sectors(self, days: int = 30, threshold: float = -3.0) -> List[str]:
        performance = await self.get_sector_performance(days=days)
        return [
            sector
            for sector, data in performance.items()
            if data["return"] <= threshold
        ]


sector_data_service = SectorDataService()
