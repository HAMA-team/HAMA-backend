"""
Strategy Agent - Investment Strategy and Comparative Analysis

Responsibilities:
- Compare multiple stocks
- Generate investment recommendations
- Bull/Bear analysis
- Final decision making
"""
from src.agents.base import BaseAgent
from src.schemas.agent import AgentInput, AgentOutput
from src.agents.research import research_agent
from langchain_anthropic import ChatAnthropic
from src.config.settings import settings
import json


class StrategyAgent(BaseAgent):
    """
    Strategy Agent - Compares stocks and makes investment decisions

    Phase 2 실제 구현 완료:
    - [x] Research Agent 호출하여 여러 종목 분석
    - [x] LLM 기반 비교 분석 (Claude Sonnet 4.5)
    - [x] 최종 투자 의견 도출
    """

    def __init__(self):
        super().__init__("strategy_agent")
        self.research_agent = research_agent
        self.llm = ChatAnthropic(
            model=settings.CLAUDE_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=4000,
            temperature=0.1
        )

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """Main strategy process"""
        stock_codes = input_data.context.get("stock_codes") if input_data.context else None

        if not stock_codes or len(stock_codes) < 2:
            return AgentOutput(
                status="failure",
                error="At least 2 stock_codes are required for comparison"
            )

        try:
            print(f"\n🎯 [Strategy Agent] Comparing {len(stock_codes)} stocks...")

            # 1. 각 종목에 대해 Research Agent 호출
            research_results = {}
            for stock_code in stock_codes:
                print(f"  📊 Analyzing {stock_code}...")
                research_input = AgentInput(
                    request_id=input_data.request_id,
                    context={"stock_code": stock_code}
                )
                result = await self.research_agent.process(research_input)

                if result.status == "success":
                    research_results[stock_code] = result.data
                else:
                    print(f"  ⚠️  Failed to analyze {stock_code}: {result.error}")

            if len(research_results) < 2:
                return AgentOutput(
                    status="failure",
                    error="Failed to analyze enough stocks for comparison"
                )

            # 2. LLM을 사용한 비교 분석
            print(f"🤖 [Strategy Agent] Comparing with LLM...")
            comparison = await self._compare_with_llm(research_results)

            return AgentOutput(
                status="success",
                data={
                    "comparison": comparison,
                    "research_results": research_results,
                    "stock_count": len(research_results)
                },
                metadata={
                    "llm_model": settings.CLAUDE_MODEL,
                    "stocks_analyzed": list(research_results.keys())
                }
            )

        except Exception as e:
            print(f"❌ [Strategy Agent] Error: {e}")
            return AgentOutput(
                status="failure",
                error=str(e)
            )

    async def _compare_with_llm(self, research_results: dict) -> dict:
        """LLM을 사용한 비교 분석"""

        # 분석 결과 요약
        summaries = []
        for stock_code, data in research_results.items():
            analysis = data.get("analysis", {})
            summaries.append(f"""
### {data.get('stock_name', stock_code)} ({stock_code})
- 투자 의견: {analysis.get('recommendation', 'N/A')}
- 신뢰도: {analysis.get('confidence', 'N/A')}/5
- 현재가: {analysis.get('current_price', 'N/A'):,}원
- 목표가: {analysis.get('target_price', 'N/A'):,}원
- 핵심 포인트: {', '.join(analysis.get('key_points', [])[:3])}
- 리스크: {', '.join(analysis.get('risks', [])[:2])}
- 요약: {analysis.get('summary', 'N/A')}
""")

        prompt = f"""당신은 전문 투자 자문가입니다. 다음 종목들의 분석 결과를 비교하여 최종 투자 의견을 제시하세요.

{''.join(summaries)}

다음 항목에 대해 비교 분석해주세요:

1. **추천 종목** (가장 투자 가치가 높은 종목 1개)
2. **추천 이유** (3-5가지)
3. **비추천 종목과의 차이점** (2-3가지)
4. **투자 전략** (단기/중기/장기)
5. **위험도 평가** (1-5, 5가 가장 위험)
6. **최종 의견 한 줄**

JSON 형식으로 답변해주세요:
{{
  "recommended_stock": "종목코드",
  "recommended_name": "종목명",
  "reasons": ["이유1", "이유2", ...],
  "differences": ["차이점1", "차이점2", ...],
  "strategy": "LONG_TERM" or "MID_TERM" or "SHORT_TERM",
  "risk_level": 1-5,
  "final_opinion": "한 줄 의견"
}}
"""

        # LLM 호출
        try:
            response = await self.llm.ainvoke(prompt)
            content = response.content

            # JSON 추출
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                json_str = content.strip()

            comparison = json.loads(json_str)

            print(f"✅ [Strategy Agent] Comparison complete: {comparison.get('recommended_stock')}")

            return comparison

        except Exception as e:
            print(f"⚠️ [Strategy Agent] LLM parsing error: {e}")
            # Fallback
            first_stock = list(research_results.keys())[0]
            first_data = research_results[first_stock]

            return {
                "recommended_stock": first_stock,
                "recommended_name": first_data.get('stock_name', first_stock),
                "reasons": ["분석 결과 기준 선정", "추가 검토 필요"],
                "differences": ["비교 분석 진행 중"],
                "strategy": "MID_TERM",
                "risk_level": 3,
                "final_opinion": f"{first_data.get('stock_name', first_stock)} 우선 검토 권장"
            }

    def _get_mock_response(self, input_data: AgentInput) -> AgentOutput:
        """Mock response (not used in Phase 2)"""
        return AgentOutput(
            status="success",
            data={"message": "Mock response - real implementation active"}
        )


# Global instance
strategy_agent = StrategyAgent()
