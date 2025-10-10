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
from src.utils.llm_factory import get_llm


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
        sector_performance: Dict[str, Dict] = None,
        user_preferences: Dict[str, Any] = None
    ) -> SectorStrategy:
        """
        섹터 전략 생성

        Args:
            market_cycle: 시장 사이클
            sector_performance: 섹터 성과 데이터 (from SectorDataService)
            user_preferences: 사용자 선호 설정

        Returns:
            SectorStrategy: 섹터 전략
        """
        from src.services.sector_data_service import sector_data_service
        import json

        user_preferences = user_preferences or {}

        # 1. 섹터 성과 데이터 수집 (제공되지 않은 경우)
        if not sector_performance:
            sector_performance = await sector_data_service.get_sector_performance(days=30)

        # 2. LLM 기반 섹터 비중 결정
        llm = get_llm(
            max_tokens=2000,
            temperature=0.1
        )

        # 섹터 성과 요약
        perf_summary = []
        for sector, data in sector_performance.items():
            perf_summary.append(f"- {sector}: {data['return']:+.1f}%")

        # 사용자 선호 섹터
        preferred = user_preferences.get("sectors", [])
        pref_str = f"사용자 선호 섹터: {', '.join(preferred)}" if preferred else "없음"

        prompt = f"""당신은 자산 배분 전문가입니다. 다음 정보를 바탕으로 섹터별 투자 비중을 결정하세요.

## 시장 상황
- 시장 사이클: {market_cycle}
- {pref_str}

## 섹터 성과 (최근 30일)
{chr(10).join(perf_summary)}

## 요구사항
1. 10개 섹터에 총 100% 비중 배분
2. 단일 섹터 최대 40% 제한
3. 모멘텀 강한 섹터 overweight
4. 약한 섹터 underweight
5. 사용자 선호 섹터 우대 (있는 경우)

다음 JSON 형식으로 답변:
{{
  "allocations": [
    {{"sector": "IT/전기전자", "weight": 0.35, "stance": "overweight"}},
    ...
  ],
  "overweight": ["섹터1", "섹터2"],
  "underweight": ["섹터3", "섹터4"],
  "rationale": "전략 근거 (50자 이내)"
}}

**중요**: weight 합계는 정확히 1.0이어야 합니다."""

        try:
            response = await llm.ainvoke(prompt)
            content = response.content

            # JSON 추출
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                json_str = content.strip()

            result = json.loads(json_str)

            # SectorWeight 객체 생성
            sectors = []
            for alloc in result["allocations"]:
                sectors.append(
                    SectorWeight(
                        sector=alloc["sector"],
                        weight=Decimal(str(alloc["weight"])),
                        stance=alloc["stance"]
                    )
                )

            print(f"✅ [Sector Rotator] Overweight: {', '.join(result['overweight'])}")

            return SectorStrategy(
                sectors=sectors,
                overweight=result["overweight"],
                underweight=result["underweight"],
                rationale=result["rationale"]
            )

        except Exception as e:
            print(f"⚠️ [Sector Rotator] LLM 실패, Fallback 사용: {e}")
            # Fallback: 기존 Mock 로직
            sectors = self._allocate_sectors(market_cycle)
            overweight, underweight = self._classify_sectors(sectors)
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
