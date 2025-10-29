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
from src.utils.json_parser import safe_json_parse


class SectorRotator:
    """
    섹터 로테이션 전략가

    LLM 기반 구현:
    - LLM 기반 섹터 평가
    - 섹터별 모멘텀 분석
    - 상관관계 기반 다각화
    """

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
            sector_performance = sector_data_service.get_sector_performance(days=30)

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

            # 안전한 JSON 파싱
            result = safe_json_parse(content, "Sector Rotator")

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
            print(f"❌ [Sector Rotator] LLM 실패: {e}")
            raise



# Global instance
sector_rotator = SectorRotator()
