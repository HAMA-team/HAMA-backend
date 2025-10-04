"""
Sector Rotator - 섹터 로테이션 전략 서브모듈

책임:
- 시장 사이클별 유망 섹터 선정
- 섹터별 비중 결정
- Overweight/Underweight 분류
"""

from typing import Dict, Any, List
from decimal import Decimal
from src.schemas.strategy import SectorStrategy, SectorWeight


class SectorRotator:
    """
    섹터 로테이션 전략가

    Week 13 Mock 구현:
    - 규칙 기반 섹터 배분

    Week 14 실제 구현:
    - LLM 기반 섹터 평가
    - 섹터별 모멘텀 분석
    - 상관관계 기반 다각화
    """

    # 시장 사이클별 유망 섹터 (Mock)
    CYCLE_SECTOR_MAP = {
        "early_bull_market": ["IT", "금융", "소비재"],
        "mid_bull_market": ["IT", "반도체", "헬스케어"],
        "late_bull_market": ["에너지", "원자재", "금융"],
        "bear_market": ["필수소비재", "헬스케어", "유틸리티"],
        "consolidation": ["금융", "IT", "소비재"],
    }

    def __init__(self):
        pass

    async def create_strategy(
        self,
        market_cycle: str,
        user_preferences: Dict[str, Any] = None
    ) -> SectorStrategy:
        """
        섹터 전략 생성

        Args:
            market_cycle: 시장 사이클
            user_preferences: 사용자 선호 설정

        Returns:
            SectorStrategy: 섹터 전략
        """
        user_preferences = user_preferences or {}

        # 1. 기본 섹터 비중 결정
        sectors = self._allocate_sectors(market_cycle)

        # 2. 사용자 선호도 반영
        if user_preferences.get("sectors"):
            sectors = self._apply_user_preferences(sectors, user_preferences)

        # 3. Overweight/Underweight 분류
        overweight, underweight = self._classify_sectors(sectors)

        # 4. 전략 근거 생성
        rationale = self._generate_rationale(market_cycle, overweight)

        return SectorStrategy(
            sectors=sectors,
            overweight=overweight,
            underweight=underweight,
            rationale=rationale
        )

    def _allocate_sectors(self, market_cycle: str) -> List[SectorWeight]:
        """
        시장 사이클에 따른 섹터 배분

        Week 14 구현:
        - 섹터별 과거 성과 분석
        - 모멘텀 점수 계산
        - 동적 비중 조정
        """
        # Mock: IT/반도체 중심
        if market_cycle in ["mid_bull_market", "early_bull_market"]:
            return [
                SectorWeight(sector="IT", weight=Decimal("0.40"), stance="overweight"),
                SectorWeight(sector="반도체", weight=Decimal("0.20"), stance="overweight"),
                SectorWeight(sector="헬스케어", weight=Decimal("0.15"), stance="neutral"),
                SectorWeight(sector="금융", weight=Decimal("0.15"), stance="neutral"),
                SectorWeight(sector="에너지", weight=Decimal("0.10"), stance="underweight"),
            ]
        else:
            # 다른 사이클의 기본 배분
            return [
                SectorWeight(sector="금융", weight=Decimal("0.30"), stance="overweight"),
                SectorWeight(sector="IT", weight=Decimal("0.25"), stance="neutral"),
                SectorWeight(sector="헬스케어", weight=Decimal("0.20"), stance="neutral"),
                SectorWeight(sector="소비재", weight=Decimal("0.15"), stance="neutral"),
                SectorWeight(sector="에너지", weight=Decimal("0.10"), stance="underweight"),
            ]

    def _apply_user_preferences(
        self,
        sectors: List[SectorWeight],
        user_preferences: Dict[str, Any]
    ) -> List[SectorWeight]:
        """
        사용자 선호도 반영

        Week 14 구현:
        - 선호 섹터 비중 증가
        - 비선호 섹터 비중 감소
        - 제약조건 유지
        """
        # Mock: 그대로 반환
        preferred_sectors = user_preferences.get("sectors", [])
        if preferred_sectors:
            print(f"   [Sector Rotator] 사용자 선호 섹터 반영: {preferred_sectors}")

        return sectors

    def _classify_sectors(
        self,
        sectors: List[SectorWeight]
    ) -> tuple[List[str], List[str]]:
        """섹터를 Overweight/Underweight로 분류"""
        overweight = [s.sector for s in sectors if s.stance == "overweight"]
        underweight = [s.sector for s in sectors if s.stance == "underweight"]
        return overweight, underweight

    def _generate_rationale(self, market_cycle: str, overweight: List[str]) -> str:
        """전략 근거 생성"""
        cycle_desc = {
            "early_bull_market": "초기 강세장",
            "mid_bull_market": "중기 강세장",
            "late_bull_market": "후기 강세장",
            "bear_market": "약세장",
            "consolidation": "횡보장",
        }

        cycle_name = cycle_desc.get(market_cycle, market_cycle)
        sectors_str = ", ".join(overweight)

        return f"{cycle_name}에서 {sectors_str} 섹터 주도 상승 예상. 금리 안정화로 기술주 선호 지속"


# Global instance
sector_rotator = SectorRotator()
