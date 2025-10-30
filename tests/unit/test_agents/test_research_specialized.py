"""
Research Agent 전문가 노드 단위 테스트

테스트 범위:
1. Technical Analyst 노드 (기술적 분석)
2. Trading Flow Analyst 노드 (거래 동향)
3. Information Analyst 노드 (정보 분석)
4. Research Synthesizer (전문가 분석 통합)

사용법:
    pytest tests/unit/test_agents/test_research_specialized.py -v
    python tests/unit/test_agents/test_research_specialized.py
"""
import asyncio
import pytest
from uuid import uuid4

from langchain_core.messages import HumanMessage

from src.agents.research.nodes import (
    technical_analyst_worker_node,
    trading_flow_analyst_worker_node,
    information_analyst_worker_node,
    synthesis_node,
)
from src.agents.research.state import ResearchState


class TestResearchSpecialized:
    """Research Agent 전문가 노드 테스트"""

    @pytest.mark.asyncio
    async def test_technical_analyst_node(self):
        """
        Technical Analyst 노드 테스트

        기술적 분석 결과가 올바르게 생성되는지 검증:
        - trend, signals, moving_average 등
        """
        print("\n[Test] Technical Analyst 노드")

        # 테스트 상태 준비
        state: ResearchState = {
            "messages": [HumanMessage(content="삼성전자 분석")],
            "stock_code": "005930",
            "current_task": {
                "id": "task_technical",
                "worker": "technical",
                "description": "기술적 분석"
            },
            "price_data": {
                "stock_code": "005930",
                "latest_close": 75000,
                "latest_volume": 10000000,
            },
            "technical_indicators": {
                "rsi": {"value": 55, "signal": "중립"},
                "macd": {"value": 100, "signal": "매수"},
                "overall_trend": "상승추세",
                "signals": ["골든크로스"],
            },
        }

        # 실행
        result = await technical_analyst_worker_node(state)

        # 검증
        assert "technical_analysis" in result, "기술적 분석 결과가 있어야 함"
        analysis = result["technical_analysis"]

        assert "trend" in analysis, "추세 정보가 있어야 함"
        assert "signals" in analysis or "technical_signals" in analysis, "기술적 신호가 있어야 함"
        assert "confidence" in analysis or "trend_strength" in analysis, "신뢰도가 있어야 함"

        print(f"  ✅ 추세: {analysis.get('trend', 'N/A')}")
        print(f"  ✅ 신호: {analysis.get('technical_signals', {})}")
        print(f"  ✅ 전망: {analysis.get('short_term_outlook', 'N/A')[:50]}...")

    @pytest.mark.asyncio
    async def test_trading_flow_analyst_node(self):
        """
        Trading Flow Analyst 노드 테스트

        거래 동향 분석 결과가 올바르게 생성되는지 검증:
        - 외국인/기관/개인 순매수 분석
        - 수급 전망
        """
        print("\n[Test] Trading Flow Analyst 노드")

        state: ResearchState = {
            "messages": [HumanMessage(content="거래 동향 분석")],
            "stock_code": "005930",
            "current_task": {
                "id": "task_trading_flow",
                "worker": "trading_flow",
                "description": "거래 동향 분석"
            },
            "price_data": {
                "latest_close": 75000,
            },
            "investor_trading_data": {
                "foreign_trend": "순매수",
                "foreign_net": 1000000000,
                "institution_trend": "순매도",
                "institution_net": -500000000,
            },
        }

        # 실행
        result = await trading_flow_analyst_worker_node(state)

        # 검증
        assert "trading_flow_analysis" in result, "거래 동향 분석 결과가 있어야 함"
        analysis = result["trading_flow_analysis"]

        assert "foreign_investor" in analysis, "외국인 투자자 분석이 있어야 함"
        assert "institutional_investor" in analysis, "기관 투자자 분석이 있어야 함"
        assert "supply_demand_analysis" in analysis, "수급 분석이 있어야 함"

        supply_demand = analysis["supply_demand_analysis"]
        assert "outlook" in supply_demand, "수급 전망이 있어야 함"
        assert supply_demand["outlook"] in ["긍정적", "부정적", "중립"], "수급 전망은 정의된 값이어야 함"

        print(f"  ✅ 외국인: {analysis['foreign_investor'].get('trend', 'N/A')}")
        print(f"  ✅ 기관: {analysis['institutional_investor'].get('trend', 'N/A')}")
        print(f"  ✅ 수급 전망: {supply_demand.get('outlook', 'N/A')}")

    @pytest.mark.asyncio
    async def test_information_analyst_node(self):
        """
        Information Analyst 노드 테스트

        정보 분석 결과가 올바르게 생성되는지 검증:
        - 호재/악재 요인
        - 시장 센티먼트
        - 리스크 레벨
        """
        print("\n[Test] Information Analyst 노드")

        state: ResearchState = {
            "messages": [HumanMessage(content="정보 분석")],
            "stock_code": "005930",
            "current_task": {
                "id": "task_information",
                "worker": "information",
                "description": "정보 분석"
            },
            "company_data": {
                "info": {
                    "corp_name": "삼성전자",
                }
            },
            "market_index_data": {
                "index": "KOSPI",
                "current": 2500,
            },
            "fundamental_data": {
                "PER": 15.5,
                "PBR": 1.2,
            },
        }

        # 실행
        result = await information_analyst_worker_node(state)

        # 검증
        assert "information_analysis" in result, "정보 분석 결과가 있어야 함"
        analysis = result["information_analysis"]

        assert "market_sentiment" in analysis, "시장 센티먼트가 있어야 함"
        assert analysis["market_sentiment"] in ["긍정적", "부정적", "중립"], "센티먼트는 정의된 값이어야 함"

        assert "risk_level" in analysis, "리스크 레벨이 있어야 함"
        assert analysis["risk_level"] in ["높음", "중간", "낮음"], "리스크 레벨은 정의된 값이어야 함"

        assert "positive_factors" in analysis, "호재 요인이 있어야 함"
        assert "negative_factors" in analysis, "악재 요인이 있어야 함"

        print(f"  ✅ 센티먼트: {analysis['market_sentiment']}")
        print(f"  ✅ 리스크: {analysis['risk_level']}")
        print(f"  ✅ 호재: {len(analysis.get('positive_factors', []))}개")
        print(f"  ✅ 악재: {len(analysis.get('negative_factors', []))}개")

    @pytest.mark.asyncio
    async def test_synthesis_with_specialist_analysis(self):
        """
        Research Synthesizer 통합 테스트

        전문가 분석 결과들이 올바르게 통합되는지 검증
        """
        print("\n[Test] Research Synthesizer (전문가 분석 통합)")

        state: ResearchState = {
            "messages": [HumanMessage(content="종합 분석")],
            "stock_code": "005930",
            "price_data": {
                "latest_close": 75000,
            },
            "fundamental_data": {
                "PER": 15.5,
                "PBR": 1.2,
            },
            "technical_indicators": {
                "overall_trend": "상승추세",
                "rsi": {"signal": "중립"},
            },
            # 전문가 분석 결과
            "technical_analysis": {
                "trend": "상승추세",
                "trend_strength": 4,
                "technical_signals": {
                    "rsi_signal": "중립",
                    "macd_signal": "매수",
                },
                "moving_average_analysis": {
                    "golden_cross": True,
                },
            },
            "trading_flow_analysis": {
                "foreign_investor": {"trend": "순매수"},
                "institutional_investor": {"trend": "순매수"},
                "supply_demand_analysis": {
                    "outlook": "긍정적",
                    "leading_investor": "외국인",
                },
            },
            "information_analysis": {
                "market_sentiment": "긍정적",
                "risk_level": "낮음",
                "positive_factors": ["강한 실적", "신제품 출시"],
                "negative_factors": [],
            },
            "bull_analysis": {
                "target_price": 85000,
                "confidence": 4,
                "positive_factors": ["실적 개선", "수출 증가"],
            },
            "bear_analysis": {
                "downside_target": 70000,
                "confidence": 2,
                "risk_factors": ["환율 리스크"],
            },
            "investor_trading_data": {
                "foreign_trend": "매수",
                "institution_trend": "매수",
            },
            "market_cap_data": {
                "market_cap": 500000000000000,
            },
        }

        # 실행
        result = await synthesis_node(state)

        # 검증
        assert "consensus" in result, "합의 의견이 있어야 함"
        consensus = result["consensus"]

        # 기본 필드 검증
        assert "recommendation" in consensus, "추천이 있어야 함"
        assert consensus["recommendation"] in ["BUY", "SELL", "HOLD"], "추천은 정의된 값이어야 함"

        assert "target_price" in consensus, "목표가가 있어야 함"
        assert "confidence" in consensus, "신뢰도가 있어야 함"

        # 전문가 분석 요약 검증
        assert "technical_summary" in consensus, "기술적 분석 요약이 있어야 함"
        assert "trading_flow_summary" in consensus, "거래 동향 요약이 있어야 함"
        assert "information_summary" in consensus, "정보 분석 요약이 있어야 함"

        tech_summary = consensus["technical_summary"]
        assert "trend" in tech_summary, "추세 정보가 있어야 함"

        flow_summary = consensus["trading_flow_summary"]
        assert "outlook" in flow_summary, "수급 전망이 있어야 함"

        info_summary = consensus["information_summary"]
        assert "sentiment" in info_summary, "센티먼트가 있어야 함"

        print(f"  ✅ 추천: {consensus['recommendation']}")
        print(f"  ✅ 목표가: {consensus['target_price']:,}원")
        print(f"  ✅ 신뢰도: {consensus['confidence']}/5")
        print(f"  ✅ 기술적 추세: {tech_summary.get('trend', 'N/A')}")
        print(f"  ✅ 수급 전망: {flow_summary.get('outlook', 'N/A')}")
        print(f"  ✅ 센티먼트: {info_summary.get('sentiment', 'N/A')}")


if __name__ == "__main__":
    """직접 실행 시"""
    async def run_tests():
        test_suite = TestResearchSpecialized()

        print("=" * 80)
        print("Research Agent 전문가 노드 테스트 시작")
        print("=" * 80)

        try:
            await test_suite.test_technical_analyst_node()
            await test_suite.test_trading_flow_analyst_node()
            await test_suite.test_information_analyst_node()
            await test_suite.test_synthesis_with_specialist_analysis()

            print("\n" + "=" * 80)
            print("✅ 모든 테스트 통과!")
            print("=" * 80)

        except AssertionError as e:
            print(f"\n❌ 테스트 실패: {e}")
        except Exception as e:
            print(f"\n❌ 예외 발생: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(run_tests())
