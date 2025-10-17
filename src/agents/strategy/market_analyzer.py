"""
Market Analyzer - 시장 사이클 분석 서브모듈

책임:
- 거시경제 지표 분석
- 시장 사이클 판단 (early_bull, mid_bull, late_bull, bear, consolidation)
- 신뢰도 계산
"""

from typing import Dict, Any
from src.schemas.strategy import MarketCycle
from src.services.bok_service import bok_service
from src.services.sector_data_service import sector_data_service
from src.utils.llm_factory import get_llm
from src.utils.json_parser import safe_json_parse
import json


class MarketAnalyzer:
    """
    시장 사이클 분석기

    Week 14 실제 구현:
    - 거시경제 데이터 수집 (한국은행 API)
    - 섹터 성과 데이터 수집
    - LLM 기반 사이클 분석
    """

    def __init__(self):
        self.llm = get_llm(
            max_tokens=2000,
            temperature=0.1
        )

    async def analyze(self, macro_data: Dict[str, Any] = None) -> MarketCycle:
        """
        시장 사이클 분석

        Args:
            macro_data: 거시경제 데이터 (옵션)

        Returns:
            MarketCycle: 시장 사이클 정보
        """
        # 1. 거시경제 데이터 수집
        if not macro_data:
            macro_data = await bok_service.get_macro_indicators()

        # 2. 섹터 성과 데이터 수집
        sector_ranking = await sector_data_service.get_sector_ranking(days=30)

        # 3. LLM을 사용한 시장 사이클 분석
        cycle_analysis = await self._analyze_with_llm(macro_data, sector_ranking)

        return MarketCycle(
            cycle=cycle_analysis["cycle"],
            confidence=cycle_analysis["confidence"],
            summary=cycle_analysis["summary"]
        )

    async def _analyze_with_llm(
        self,
        macro_data: Dict,
        sector_ranking: list
    ) -> Dict:
        """
        LLM을 사용한 시장 사이클 분석

        시장 사이클 분류:
        - early_bull_market: 초기 강세장
        - mid_bull_market: 중기 강세장
        - late_bull_market: 후기 강세장
        - bear_market: 약세장
        - consolidation: 횡보장
        """

        # 섹터 성과 요약
        sector_summary = []
        for i, sector in enumerate(sector_ranking[:5], 1):
            sector_summary.append(
                f"{i}. {sector['sector']}: {sector['return']:+.1f}%"
            )

        prompt = f"""당신은 한국 주식시장 전문 애널리스트입니다. 다음 거시경제 지표와 섹터 성과를 분석하여 현재 시장 사이클을 판단하세요.

## 거시경제 지표
- 기준금리: {macro_data.get('base_rate', 'N/A')}% (추세: {macro_data.get('base_rate_trend', 'N/A')})
- CPI (소비자물가): {macro_data.get('cpi', 'N/A')} (전년대비: {macro_data.get('cpi_yoy', 'N/A'):.1f}%)
- 환율 (원/달러): {macro_data.get('exchange_rate', 'N/A'):,.0f}원

## 섹터 성과 (최근 30일)
{chr(10).join(sector_summary)}

## 시장 사이클 분류 기준

1. **early_bull_market (초기 강세장)**
   - 금리 인하 시작 또는 안정화
   - 주요 섹터 상승 전환
   - 시장 심리 회복 초기

2. **mid_bull_market (중기 강세장)**
   - 금리 안정 또는 완만한 인하
   - 대다수 섹터 강세
   - 성장주 주도 상승

3. **late_bull_market (후기 강세장)**
   - 금리 상승 우려
   - 업종별 차별화
   - 가치주 선호

4. **bear_market (약세장)**
   - 금리 급등
   - 대다수 섹터 하락
   - 방어주 선호

5. **consolidation (횡보장)**
   - 방향성 불명확
   - 섹터별 엇갈린 성과
   - 변동성 확대

다음 JSON 형식으로 답변하세요:
{{
  "cycle": "시장 사이클 (위 5가지 중 1개)",
  "confidence": 0.0-1.0 (신뢰도),
  "summary": "한 줄 요약 (40자 이내)",
  "key_factors": ["주요 근거1", "주요 근거2", "주요 근거3"]
}}"""

        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content

            # 안전한 JSON 파싱
            analysis = safe_json_parse(content, "Market Analyzer")

            print(f"✅ [Market Analyzer] 시장 사이클: {analysis['cycle']} (신뢰도: {analysis['confidence']:.0%})")

            return analysis

        except Exception as e:
            print(f"⚠️ [Market Analyzer] LLM 분석 실패, Fallback 사용: {e}")
            # Fallback: 섹터 성과 기반 간단 판단
            top_sectors_positive = sum(1 for s in sector_ranking[:5] if s['return'] > 0)

            if top_sectors_positive >= 4:
                cycle = "mid_bull_market"
            elif top_sectors_positive >= 3:
                cycle = "early_bull_market"
            elif top_sectors_positive <= 1:
                cycle = "bear_market"
            else:
                cycle = "consolidation"

            return {
                "cycle": cycle,
                "confidence": 0.6,
                "summary": f"상위 5개 섹터 중 {top_sectors_positive}개 상승",
                "key_factors": ["섹터 성과 기반 판단"]
            }


# Global instance
market_analyzer = MarketAnalyzer()
