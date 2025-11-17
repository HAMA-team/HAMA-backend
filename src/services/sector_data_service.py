"""
섹터 데이터 서비스

실제 구현 시 DART API 또는 사내 DB에서 섹터-종목 매핑을 가져와야 하지만
테스트 및 오프라인 실행을 위해 결정론적인 샘플 데이터를 제공한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class SectorSnapshot:
    """샘플 섹터 성과 데이터"""

    sector: str
    return_pct: float
    momentum: float
    volatility: float
    trend: str


# CI/테스트 환경에서도 재현 가능한 고정 데이터
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


class SectorDataService:
    """
    섹터 데이터 서비스

    실제 서비스 연결 전까지는 DEFAULT_SECTOR_SNAPSHOTS 값을 기반으로
    간단한 모멘텀 지표를 만든다. 외부 의존성이 없기 때문에 LangGraph 노드들이
    즉시 동작하며, 향후 실데이터 연동 시 인터페이스만 유지하면 된다.
    """

    def __init__(self, snapshots: List[SectorSnapshot] | None = None):
        self._snapshots = snapshots or DEFAULT_SECTOR_SNAPSHOTS

    def _normalize_days(self, days: int) -> int:
        return max(1, days)

    def get_sector_performance(
        self,
        days: int = 30
    ) -> Dict[str, Dict]:
        """
        섹터별 성과 데이터 (고정 샘플 기반)

        Args:
            days: 비교 기간. 베이스는 30일 데이터이며 단순 비율로 스케일한다.
        """
        period = self._normalize_days(days)
        scale = period / 30.0

        performance: Dict[str, Dict] = {}
        for snapshot in self._snapshots:
            scaled_return = round(snapshot.return_pct * scale, 2)
            performance[snapshot.sector] = {
                "return": scaled_return,
                "momentum": snapshot.momentum,
                "volatility": snapshot.volatility,
                "trend": snapshot.trend,
                "days": period,
            }

        return performance

    def get_sector_ranking(self, days: int = 30) -> List[Dict]:
        """
        섹터 성과 순위 (수익률 내림차순)
        """
        performance = self.get_sector_performance(days=days)

        ranking = [
            {
                "sector": sector,
                "return": data["return"],
                "volatility": data["volatility"],
                "trend": data["trend"],
                "momentum": data["momentum"],
            }
            for sector, data in performance.items()
        ]
        ranking.sort(key=lambda item: item["return"], reverse=True)
        return ranking

    def get_overweight_sectors(
        self,
        days: int = 30,
        threshold: float = 5.0
    ) -> List[str]:
        """
        비중 확대 추천 섹터
        """
        performance = self.get_sector_performance(days=days)
        return [
            sector
            for sector, data in performance.items()
            if data["return"] >= threshold
        ]

    def get_underweight_sectors(
        self,
        days: int = 30,
        threshold: float = -3.0
    ) -> List[str]:
        """
        비중 축소 추천 섹터
        """
        performance = self.get_sector_performance(days=days)
        return [
            sector
            for sector, data in performance.items()
            if data["return"] <= threshold
        ]


# Global instance
sector_data_service = SectorDataService()
