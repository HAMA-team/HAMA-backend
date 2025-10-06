"""
Research Agent - Data Collection and Company Analysis

Responsibilities:
- Real-time stock data collection
- Financial statement analysis (DART)
- LLM-based comprehensive analysis
- Technical indicator calculation
"""
from src.agents.legacy import LegacyAgent
from src.schemas.agent import AgentInput, AgentOutput
from src.agents.legacy.data_collection import data_collection_agent
from langchain_anthropic import ChatAnthropic
from src.config.settings import settings
import json


class ResearchAgent(LegacyAgent):
    """
    Research Agent - Analyzes companies using LLM

    Phase 2 실제 구현 완료:
    - [x] Data Collection Agent 호출
    - [x] LLM 기반 종합 분석 (Claude Sonnet 4.5)
    - [x] 주가, 재무제표, 기업정보 통합 분석
    """

    def __init__(self):
        super().__init__("research_agent")
        self.data_agent = data_collection_agent
        self.llm = ChatAnthropic(
            model=settings.CLAUDE_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            max_tokens=4000,
            temperature=0.1
        )

    async def process(self, input_data: AgentInput) -> AgentOutput:
        """Main research process"""
        stock_code = input_data.context.get("stock_code") if input_data.context else None

        if not stock_code:
            return AgentOutput(
                status="failure",
                error="stock_code is required in context"
            )

        try:
            # 1. Data Collection Agent 호출하여 데이터 수집
            print(f"\n📊 [Research Agent] Collecting data for {stock_code}...")

            # 주가 데이터
            price_input = AgentInput(
                request_id=input_data.request_id,
                context={"data_type": "stock_price", "stock_code": stock_code, "days": 30}
            )
            price_result = await self.data_agent.process(price_input)

            # 재무제표 데이터
            financial_input = AgentInput(
                request_id=input_data.request_id,
                context={"data_type": "financial_statement", "stock_code": stock_code, "year": "2023"}
            )
            financial_result = await self.data_agent.process(financial_input)

            # 기업 정보
            company_input = AgentInput(
                request_id=input_data.request_id,
                context={"data_type": "company_info", "stock_code": stock_code}
            )
            company_result = await self.data_agent.process(company_input)

            # 2. 데이터 검증
            if price_result.status != "success":
                return AgentOutput(
                    status="failure",
                    error=f"Failed to fetch price data: {price_result.error}"
                )

            # 3. LLM을 사용한 종합 분석
            print(f"🤖 [Research Agent] Analyzing with LLM...")
            analysis = await self._analyze_with_llm(
                stock_code=stock_code,
                price_data=price_result.data,
                financial_data=financial_result.data if financial_result.status == "success" else None,
                company_data=company_result.data if company_result.status == "success" else None
            )

            return AgentOutput(
                status="success",
                data={
                    "stock_code": stock_code,
                    "stock_name": company_result.data.get("corp_name") if company_result.status == "success" else stock_code,
                    "analysis": analysis,
                    "raw_data": {
                        "price": price_result.data,
                        "financial": financial_result.data if financial_result.status == "success" else None,
                        "company": company_result.data if company_result.status == "success" else None
                    }
                },
                metadata={
                    "llm_model": settings.CLAUDE_MODEL,
                    "data_sources": ["FinanceDataReader", "DART"]
                }
            )

        except Exception as e:
            print(f"❌ [Research Agent] Error: {e}")
            return AgentOutput(
                status="failure",
                error=str(e)
            )

    async def _analyze_with_llm(self, stock_code: str, price_data: dict, financial_data: dict, company_data: dict) -> dict:
        """LLM을 사용한 종합 분석"""

        # 프롬프트 생성
        prompt = f"""당신은 전문 주식 애널리스트입니다. 다음 데이터를 분석하여 종합적인 투자 의견을 제시하세요.

## 종목 정보
- 종목코드: {stock_code}
- 기업명: {company_data.get('corp_name') if company_data else stock_code}
- CEO: {company_data.get('ceo_nm') if company_data else 'N/A'}
- 설립일: {company_data.get('est_dt') if company_data else 'N/A'}

## 주가 데이터 (최근 {price_data.get('days')}일)
- 현재가: {price_data.get('latest_close'):,.0f}원
- 최근 거래량: {price_data.get('latest_volume'):,.0f}주
- 데이터 출처: {price_data.get('source')}

## 재무 데이터 ({financial_data.get('year') if financial_data else 'N/A'}년)
{json.dumps(financial_data, ensure_ascii=False, indent=2) if financial_data else '재무제표 데이터 없음'}

다음 항목에 대해 분석해주세요:

1. **투자 의견** (BUY/HOLD/SELL)
2. **신뢰도** (1-5 점수, 5가 가장 높음)
3. **목표가** (원 단위)
4. **투자 포인트** (3-5가지 핵심 포인트)
5. **리스크 요인** (주의할 점 2-3가지)
6. **한 줄 요약**

JSON 형식으로 답변해주세요:
{{
  "recommendation": "BUY" or "HOLD" or "SELL",
  "confidence": 1-5,
  "target_price": 목표가(숫자),
  "current_price": 현재가(숫자),
  "key_points": ["포인트1", "포인트2", ...],
  "risks": ["리스크1", "리스크2", ...],
  "summary": "한 줄 요약"
}}
"""

        # LLM 호출
        try:
            response = await self.llm.ainvoke(prompt)

            # 응답 파싱
            content = response.content

            # JSON 추출 (```json ... ``` 또는 직접 JSON)
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

            analysis = json.loads(json_str)

            print(f"✅ [Research Agent] LLM Analysis complete: {analysis.get('recommendation')}")

            return analysis

        except Exception as e:
            print(f"⚠️ [Research Agent] LLM parsing error, using fallback: {e}")
            # Fallback 분석
            return {
                "recommendation": "HOLD",
                "confidence": 3,
                "target_price": int(price_data.get('latest_close', 0) * 1.05),
                "current_price": int(price_data.get('latest_close', 0)),
                "key_points": [
                    f"현재가: {price_data.get('latest_close'):,.0f}원",
                    f"최근 거래량: {price_data.get('latest_volume'):,.0f}주",
                    "추가 분석 필요"
                ],
                "risks": ["시장 변동성", "추가 데이터 필요"],
                "summary": f"{company_data.get('corp_name') if company_data else stock_code} 종목 분석 진행 중"
            }

    def _get_mock_response(self, input_data: AgentInput) -> AgentOutput:
        """Mock response (not used in Phase 2)"""
        return AgentOutput(
            status="success",
            data={"message": "Mock response - real implementation active"}
        )


# Global instance
research_agent = ResearchAgent()
