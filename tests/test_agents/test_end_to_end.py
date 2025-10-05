"""
종단간(End-to-End) 통합 테스트

최근 변경사항 종합 테스트:
- Portfolio Agent 서브그래프
- Master Supervisor 패턴
- 전체 시스템 통합 플로우
"""
import os
import pytest
from src.agents.graph_master import run_graph
from src.agents.portfolio import portfolio_agent

# Supervisor가 필요한 테스트는 유효한 API 키가 있을 때만 실행
skip_if_no_api_key = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY") == "test-key-not-used",
    reason="Supervisor requires valid ANTHROPIC_API_KEY"
)


class TestEndToEndIntegration:
    """종단간 통합 테스트"""

    @pytest.mark.asyncio
    @skip_if_no_api_key
    async def test_full_investment_workflow(self):
        """전체 투자 워크플로우 테스트: 분석 → 전략 → 포트폴리오"""
        # 1단계: 종목 분석 요청
        analysis_result = await run_graph(
            query="삼성전자 분석해줘",
            automation_level=2,
            request_id="e2e_analysis"
        )

        assert analysis_result is not None
        assert "message" in analysis_result

        print("\n✅ 1단계: 종목 분석 완료")
        print(f"   분석 결과: {analysis_result['message'][:100]}...")

        # 2단계: 투자 전략 요청
        strategy_result = await run_graph(
            query="보수적인 투자 전략을 세워줘",
            automation_level=2,
            request_id="e2e_strategy"
        )

        assert strategy_result is not None
        print("\n✅ 2단계: 투자 전략 수립 완료")

        # 3단계: 포트폴리오 구성
        portfolio_result = await run_graph(
            query="내 포트폴리오를 리밸런싱해줘",
            automation_level=2,
            request_id="e2e_portfolio"
        )

        assert portfolio_result is not None
        print("\n✅ 3단계: 포트폴리오 리밸런싱 완료")

    @pytest.mark.asyncio
    async def test_portfolio_direct_invocation(self):
        """Portfolio Agent 직접 호출 테스트"""
        initial_state = {
            "request_id": "e2e_direct",
            "automation_level": 2,
            "risk_profile": "moderate",
            "current_holdings": [
                {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.50},
                {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.30},
                {"stock_code": "CASH", "stock_name": "현금", "weight": 0.20},
            ],
            "total_value": 10_000_000,
            "hitl_required": False,
        }

        config = {"configurable": {"thread_id": "e2e_direct_portfolio"}}

        result = await portfolio_agent.ainvoke(initial_state, config=config)

        assert result is not None
        assert result.get("portfolio_report") is not None

        report = result["portfolio_report"]

        print("\n✅ Portfolio Agent 직접 호출 성공")
        print(f"   리밸런싱 필요: {report['rebalancing_needed']}")
        print(f"   예상 수익률: {report.get('expected_return', 0):.1%}")
        print(f"   예상 변동성: {report.get('expected_volatility', 0):.1%}")

    @pytest.mark.asyncio
    @skip_if_no_api_key
    async def test_user_conversation_flow(self):
        """실제 사용자 대화 시나리오"""
        thread_id = "e2e_conversation"

        # 사용자: "안녕하세요"
        greeting = await run_graph(
            query="안녕하세요",
            automation_level=2,
            thread_id=thread_id
        )
        assert greeting is not None

        # 사용자: "삼성전자에 대해 알려주세요"
        info = await run_graph(
            query="삼성전자에 대해 알려주세요",
            automation_level=2,
            thread_id=thread_id
        )
        assert info is not None

        # 사용자: "이 종목에 투자해야 할까요?"
        advice = await run_graph(
            query="이 종목에 투자해야 할까요?",
            automation_level=2,
            thread_id=thread_id
        )
        assert advice is not None

        # 사용자: "보수적인 포트폴리오로 구성해주세요"
        portfolio = await run_graph(
            query="보수적인 포트폴리오로 구성해주세요",
            automation_level=2,
            thread_id=thread_id
        )
        assert portfolio is not None

        print("\n✅ 사용자 대화 플로우 테스트 완료")
        print(f"   총 {4}개 질의 처리 성공")

    @pytest.mark.asyncio
    @skip_if_no_api_key
    async def test_risk_analysis_integration(self):
        """리스크 분석 통합 테스트"""
        # 고위험 포트폴리오로 리스크 체크 요청
        result = await run_graph(
            query="내 포트폴리오의 리스크를 분석해줘",
            automation_level=2,
            request_id="e2e_risk"
        )

        assert result is not None
        print("\n✅ 리스크 분석 통합 완료")

    @pytest.mark.asyncio
    @skip_if_no_api_key
    async def test_multiple_agents_parallel(self):
        """여러 에이전트 병렬 실행 테스트"""
        # "삼성전자 분석하고 리스크도 체크해줘" → Research + Risk 병렬 호출
        result = await run_graph(
            query="삼성전자 분석하고 리스크도 체크해줘",
            automation_level=2,
            request_id="e2e_parallel"
        )

        assert result is not None
        print("\n✅ 병렬 에이전트 실행 완료")

    @pytest.mark.asyncio
    @skip_if_no_api_key
    async def test_automation_level_differences(self):
        """자동화 레벨별 동작 차이 테스트"""
        query = "삼성전자 10주 매수해줘"

        # 레벨 1: Pilot (자동)
        result_pilot = await run_graph(
            query=query,
            automation_level=1,
            request_id="e2e_pilot"
        )
        assert result_pilot is not None

        # 레벨 2: Copilot (승인 필요)
        result_copilot = await run_graph(
            query=query,
            automation_level=2,
            request_id="e2e_copilot"
        )
        assert result_copilot is not None

        # 레벨 3: Advisor (모든 결정 승인)
        result_advisor = await run_graph(
            query=query,
            automation_level=3,
            request_id="e2e_advisor"
        )
        assert result_advisor is not None

        print("\n✅ 자동화 레벨별 동작 확인 완료")
        print(f"   Pilot: {len(result_pilot.get('messages', []))} 메시지")
        print(f"   Copilot: {len(result_copilot.get('messages', []))} 메시지")
        print(f"   Advisor: {len(result_advisor.get('messages', []))} 메시지")


if __name__ == "__main__":
    """직접 실행 시 모든 테스트 실행"""
    import asyncio
    import sys

    async def run_all_tests():
        print("=" * 60)
        print("종단간 통합 테스트")
        print("=" * 60)

        test_suite = TestEndToEndIntegration()

        tests = [
            ("전체 투자 워크플로우", test_suite.test_full_investment_workflow),
            ("Portfolio 직접 호출", test_suite.test_portfolio_direct_invocation),
            ("사용자 대화 시나리오", test_suite.test_user_conversation_flow),
            ("리스크 분석 통합", test_suite.test_risk_analysis_integration),
            ("병렬 에이전트 실행", test_suite.test_multiple_agents_parallel),
            ("자동화 레벨 차이", test_suite.test_automation_level_differences),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                print(f"\n[테스트] {name}")
                await test_func()
                passed += 1
            except AssertionError as e:
                print(f"❌ 실패: {e}")
                failed += 1
            except Exception as e:
                print(f"❌ 에러: {e}")
                import traceback
                traceback.print_exc()
                failed += 1

        print("\n" + "=" * 60)
        print(f"테스트 결과: {passed} 성공, {failed} 실패")
        print("=" * 60)

        return failed == 0

    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
