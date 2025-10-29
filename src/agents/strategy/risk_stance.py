"""
Risk Stance - 리스크 스탠스 결정 서브모듈

책임:
- 시장 상황별 리스크 수준 판단
- 주식/현금 비율 결정
- 방어 수위 조정
"""

import logging
from decimal import Decimal
from src.schemas.strategy import AssetAllocation
from src.services.stock_data_service import stock_data_service

logger = logging.getLogger(__name__)


class RiskStanceAnalyzer:
    """
    리스크 스탠스 분석기

    실제 구현:
    - 변동성 지표 분석 (KOSPI 표준편차)
    - 시장 심리 지표 통합
    - 동적 리스크 조정
    """

    def __init__(self):
        pass

    async def determine_allocation(
        self,
        market_cycle: str,
        risk_tolerance: str,
        volatility_index: float = None
    ) -> AssetAllocation:
        """
        자산 배분 결정 (LLM 기반)

        Args:
            market_cycle: 시장 사이클
            risk_tolerance: 리스크 허용도 (conservative/moderate/aggressive)
            volatility_index: 변동성 지수 (제공되지 않으면 자동 계산)

        Returns:
            AssetAllocation: 자산 배분 전략
        """
        from src.utils.llm_factory import get_llm
        from src.utils.json_parser import safe_json_parse

        # 변동성 계산
        if volatility_index is None:
            volatility_index = await self._calculate_market_volatility()

        llm = get_llm(max_tokens=1000, temperature=0.1)

        prompt = f"""당신은 자산 배분 전문가입니다. 다음 정보를 바탕으로 주식/현금 비율을 결정하세요.

## 상황
- 시장 사이클: {market_cycle}
- 리스크 허용도: {risk_tolerance}
- KOSPI 변동성: {volatility_index:.2f}% (연환산)

## 요구사항
1. 주식 비중 20% ~ 95% 범위
2. 변동성 높을수록 현금 비중 증가
3. 리스크 허용도 반영
   - conservative: 보수적 배분
   - moderate: 균형 배분
   - aggressive: 공격적 배분

다음 JSON 형식으로 답변:
{{
  "stocks": 0.75,
  "cash": 0.25,
  "rationale": "배분 근거 (50자 이내)"
}}

**중요**: stocks + cash = 1.0"""

        try:
            response = await llm.ainvoke(prompt)
            result = safe_json_parse(response.content, "Risk Stance")

            equity_weight = Decimal(str(result["stocks"]))
            cash_weight = Decimal(str(result["cash"]))

            # 범위 검증
            equity_weight = max(Decimal("0.20"), min(Decimal("0.95"), equity_weight))
            cash_weight = Decimal("1.00") - equity_weight

            return AssetAllocation(
                stocks=equity_weight,
                cash=cash_weight,
                rationale=result["rationale"]
            )
        except Exception as e:
            logger.error(f"❌ [Risk Stance] LLM 실패: {e}")
            raise

    async def _calculate_market_volatility(self) -> float | None:
        """
        시장 변동성 계산 (KOSPI 지수 기준)

        Returns:
            변동성 지수 (%) 또는 None

        Raises:
            Exception: Rate Limit 등으로 데이터 조회 실패 시
        """
        # KOSPI 지수 최근 60일 데이터 조회 (Rate Limit 방지 최적화)
        df = await stock_data_service.get_market_index("KS11", days=60)

        if df is None or len(df) < 20:
            logger.warning("⚠️ [Risk Stance] KOSPI 데이터 부족, 변동성 계산 불가")
            return None

        # 일일 수익률 계산
        returns = df["Close"].pct_change().dropna()

        # 변동성 = 일일 수익률 표준편차 * √252 (연환산)
        daily_volatility = returns.std()
        annual_volatility = daily_volatility * (252 ** 0.5)

        # 백분율로 변환
        volatility_pct = annual_volatility * 100

        logger.info(f"📊 [Risk Stance] KOSPI 변동성: {volatility_pct:.2f}%")
        return float(volatility_pct)



# Global instance
risk_stance_analyzer = RiskStanceAnalyzer()
