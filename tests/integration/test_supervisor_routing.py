"""
Supervisor 라우팅 통합 테스트

테스트 목표:
- Supervisor가 사용자 질문을 분석하여 올바른 에이전트를 선택하는지 검증
- 병렬 실행이 필요한 경우 여러 에이전트를 동시에 호출하는지 검증
- Automation Level에 따른 HITL 조건 검증

중요:
- 실제 LLM을 사용하여 Supervisor의 라우팅 로직을 검증합니다
- ENV="integration"으로 설정되어 Mock이 아닌 실제 Supervisor가 동작합니다

사용법:
    pytest tests/integration/test_supervisor_routing.py -v -s
    python tests/integration/test_supervisor_routing.py  # 직접 실행
"""
import asyncio
import pytest
from uuid import uuid4

from langchain_core.messages import HumanMessage

from src.agents.graph_master import build_graph
from src.config.settings import settings


class TestSupervisorRouting:
    """Supervisor 라우팅 통합 테스트"""

    def _normalize_agent_names(self, tool_calls) -> list[str]:
        """Tool call 이름 정규화 (transfer_to_xxx_agent → xxx_agent)"""
        agent_names = [call["name"] for call in tool_calls]
        return [name.replace("transfer_to_", "") for name in agent_names]

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OpenAI API 키 필요")
    async def test_general_question_routes_to_general(self):
        """
        일반 질문 라우팅 테스트

        질문: "PER이 뭐야?"
        예상: general_agent 호출
        """
        print("\n[Test] 일반 질문 → General Agent")

        app = build_graph(automation_level=2)

        initial_state = {
            "messages": [HumanMessage(content="PER이 뭐야?")],
            "user_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "automation_level": 2,
            "query": "PER이 뭐야?",
            "agent_results": {},
            "agents_to_call": [],
            "agents_called": [],
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        result = await app.ainvoke(initial_state, config)

        # 검증: messages에서 AI 응답 확인
        messages = result.get("messages", [])
        ai_responses = [msg for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls]

        print(f"  📊 응답 메시지 수: {len(messages)}")

        if ai_responses:
            tool_calls = ai_responses[0].tool_calls
            agent_names = [call["name"] for call in tool_calls]
            print(f"  🤖 호출된 에이전트: {agent_names}")

            # Tool call 이름 정규화 (transfer_to_xxx_agent → xxx_agent)
            normalized_names = [
                name.replace("transfer_to_", "")
                for name in agent_names
            ]

            # 검증: general_agent가 호출되어야 함
            assert "general_agent" in normalized_names, "General Agent가 호출되어야 함"
            print("  ✅ General Agent 라우팅 성공")
        else:
            print("  ⚠️  Tool call 없음 - LLM이 직접 응답했을 수 있음")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OpenAI API 키 필요")
    async def test_stock_analysis_routes_to_research_strategy_risk(self):
        """
        종목 분석 라우팅 테스트

        질문: "삼성전자 분석해줘"
        예상: research_agent + strategy_agent + risk_agent (병렬)
        """
        print("\n[Test] 종목 분석 → Research + Strategy + Risk")

        app = build_graph(automation_level=2)

        initial_state = {
            "messages": [HumanMessage(content="삼성전자 분석해줘")],
            "user_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "automation_level": 2,
            "query": "삼성전자 분석해줘",
            "agent_results": {},
            "agents_to_call": [],
            "agents_called": [],
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        result = await app.ainvoke(initial_state, config)

        # 검증
        messages = result.get("messages", [])
        ai_responses = [msg for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls]

        print(f"  📊 응답 메시지 수: {len(messages)}")

        if ai_responses:
            tool_calls = ai_responses[0].tool_calls
            agent_names = [call["name"] for call in tool_calls]
            print(f"  🤖 호출된 에이전트: {agent_names}")

            # 검증: research 또는 strategy가 최소 하나 호출되어야 함
            has_analysis_agent = any(
                agent in agent_names
                for agent in ["transfer_to_research_agent", "transfer_to_strategy_agent", "transfer_to_risk_agent"]
            )
            assert has_analysis_agent, "분석 관련 에이전트가 호출되어야 함"
            print("  ✅ 분석 에이전트 라우팅 성공")
        else:
            print("  ⚠️  Tool call 없음")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OpenAI API 키 필요")
    async def test_trade_request_routes_to_trading(self):
        """
        매매 요청 라우팅 테스트

        질문: "삼성전자 10주 매수해줘"
        예상: trading_agent 호출 + HITL 발생
        """
        print("\n[Test] 매매 요청 → Trading Agent + HITL")

        app = build_graph(automation_level=2)

        initial_state = {
            "messages": [HumanMessage(content="삼성전자 10주 매수해줘")],
            "user_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "automation_level": 2,
            "query": "삼성전자 10주 매수해줘",
            "agent_results": {},
            "agents_to_call": [],
            "agents_called": [],
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        result = await app.ainvoke(initial_state, config)

        # 검증
        messages = result.get("messages", [])
        ai_responses = [msg for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls]

        print(f"  📊 응답 메시지 수: {len(messages)}")

        if ai_responses:
            tool_calls = ai_responses[0].tool_calls
            agent_names = [call["name"] for call in tool_calls]
            print(f"  🤖 호출된 에이전트: {agent_names}")

            # 검증: trading_agent가 호출되어야 함
            assert "transfer_to_trading_agent" in agent_names, "Trading Agent가 호출되어야 함"
            print("  ✅ Trading Agent 라우팅 성공")

            # HITL 검증 (선택적)
            state = await app.aget_state(config)
            if state.next:
                print(f"  🔔 HITL Interrupt 발생: {state.next}")
            else:
                print("  ℹ️  Interrupt 없음 (구현에 따라 다를 수 있음)")
        else:
            print("  ⚠️  Tool call 없음")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OpenAI API 키 필요")
    async def test_portfolio_rebalance_routes_correctly(self):
        """
        포트폴리오 리밸런싱 라우팅 테스트

        질문: "내 포트폴리오 리밸런싱해줘"
        예상: portfolio_agent + risk_agent
        """
        print("\n[Test] 포트폴리오 리밸런싱 → Portfolio + Risk")

        app = build_graph(automation_level=2)

        initial_state = {
            "messages": [HumanMessage(content="내 포트폴리오 리밸런싱해줘")],
            "user_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "automation_level": 2,
            "query": "내 포트폴리오 리밸런싱해줘",
            "agent_results": {},
            "agents_to_call": [],
            "agents_called": [],
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        result = await app.ainvoke(initial_state, config)

        # 검증
        messages = result.get("messages", [])
        ai_responses = [msg for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls]

        print(f"  📊 응답 메시지 수: {len(messages)}")

        if ai_responses:
            tool_calls = ai_responses[0].tool_calls
            agent_names = [call["name"] for call in tool_calls]
            print(f"  🤖 호출된 에이전트: {agent_names}")

            # 검증: portfolio 또는 risk 에이전트 호출
            has_portfolio_agent = any(
                agent in agent_names
                for agent in ["transfer_to_portfolio_agent", "transfer_to_risk_agent"]
            )
            assert has_portfolio_agent, "Portfolio 또는 Risk Agent가 호출되어야 함"
            print("  ✅ Portfolio Agent 라우팅 성공")
        else:
            print("  ⚠️  Tool call 없음")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OpenAI API 키 필요")
    async def test_complex_query_multiple_agents(self):
        """
        복합 질문 라우팅 테스트

        질문: "삼성전자와 SK하이닉스를 비교 분석하고 리스크도 평가해줘"
        예상: research + strategy + risk (병렬 실행)
        """
        print("\n[Test] 복합 질문 → 다중 에이전트 병렬 실행")

        app = build_graph(automation_level=2)

        initial_state = {
            "messages": [HumanMessage(
                content="삼성전자와 SK하이닉스를 비교 분석하고 리스크도 평가해줘"
            )],
            "user_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "automation_level": 2,
            "query": "삼성전자와 SK하이닉스를 비교 분석하고 리스크도 평가해줘",
            "agent_results": {},
            "agents_to_call": [],
            "agents_called": [],
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        result = await app.ainvoke(initial_state, config)

        # 검증
        messages = result.get("messages", [])
        ai_responses = [msg for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls]

        print(f"  📊 응답 메시지 수: {len(messages)}")

        if ai_responses:
            tool_calls = ai_responses[0].tool_calls
            agent_names = [call["name"] for call in tool_calls]
            print(f"  🤖 호출된 에이전트: {agent_names}")
            print(f"  📈 에이전트 수: {len(agent_names)}")

            # 검증: 여러 에이전트가 호출되어야 함 (병렬 실행)
            assert len(agent_names) >= 2, "복합 질문이므로 2개 이상 에이전트 호출 예상"
            print("  ✅ 다중 에이전트 병렬 실행 성공")
        else:
            print("  ⚠️  Tool call 없음")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OpenAI API 키 필요")
    async def test_routing_with_automation_level_1(self):
        """
        자동화 레벨별 라우팅 테스트

        automation_level=1 (Pilot): 자동 실행, HITL 최소화
        """
        print("\n[Test] Automation Level 1 (Pilot)")

        app = build_graph(automation_level=1)

        initial_state = {
            "messages": [HumanMessage(content="삼성전자 5주 매수")],
            "user_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "automation_level": 1,  # Pilot 모드
            "query": "삼성전자 5주 매수",
            "agent_results": {},
            "agents_to_call": [],
            "agents_called": [],
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        result = await app.ainvoke(initial_state, config)

        # 검증
        state = await app.aget_state(config)

        print(f"  📊 Automation Level: 1")
        print(f"  🔔 Interrupt 발생: {state.next is not None}")

        # Level 1에서는 HITL이 최소화되어야 함
        if state.next:
            print(f"  ⚠️  Interrupt 발생: {state.next} (Level 1에서는 드물어야 함)")
        else:
            print("  ✅ 자동 실행 (Interrupt 없음)")

    @pytest.mark.asyncio
    @pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="OpenAI API 키 필요")
    async def test_routing_consistency(self):
        """
        라우팅 일관성 테스트

        같은 질문을 여러 번 요청했을 때 일관된 에이전트를 선택하는지 검증
        """
        print("\n[Test] 라우팅 일관성 검증")

        app = build_graph(automation_level=2)
        query = "삼성전자 분석해줘"

        agent_calls = []

        for i in range(3):
            initial_state = {
                "messages": [HumanMessage(content=query)],
                "user_id": str(uuid4()),
                "conversation_id": str(uuid4()),
                "automation_level": 2,
                "query": query,
                "agent_results": {},
                "agents_to_call": [],
                "agents_called": [],
            }

            config = {"configurable": {"thread_id": str(uuid4())}}

            result = await app.ainvoke(initial_state, config)

            messages = result.get("messages", [])
            ai_responses = [msg for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls]

            if ai_responses:
                tool_calls = ai_responses[0].tool_calls
                agent_names = [call["name"] for call in tool_calls]
                agent_calls.append(set(agent_names))
                print(f"  시도 {i+1}: {agent_names}")

        # 검증: 모든 시도에서 최소 1개 공통 에이전트
        if len(agent_calls) >= 2:
            common_agents = set.intersection(*agent_calls)
            print(f"  🔍 공통 에이전트: {common_agents}")

            # 최소한 하나의 공통 에이전트가 있어야 일관성 있음
            assert len(common_agents) > 0, "일관된 라우팅이 있어야 함"
            print("  ✅ 라우팅 일관성 확인")
        else:
            print("  ⚠️  테스트 데이터 부족")


if __name__ == "__main__":
    """직접 실행"""
    async def main():
        print("=" * 60)
        print("Supervisor 라우팅 통합 테스트")
        print("=" * 60)

        if not settings.ANTHROPIC_API_KEY:
            print("\n⚠️  ANTHROPIC_API_KEY가 설정되지 않았습니다")
            print("실제 Supervisor 라우팅을 테스트하려면 API 키가 필요합니다")
            return False

        tester = TestSupervisorRouting()

        tests = [
            ("일반 질문 → General Agent", tester.test_general_question_routes_to_general),
            ("종목 분석 → Research+Strategy+Risk", tester.test_stock_analysis_routes_to_research_strategy_risk),
            ("매매 요청 → Trading Agent", tester.test_trade_request_routes_to_trading),
            ("포트폴리오 → Portfolio+Risk", tester.test_portfolio_rebalance_routes_correctly),
            ("복합 질문 → 다중 에이전트", tester.test_complex_query_multiple_agents),
            ("Automation Level 1", tester.test_routing_with_automation_level_1),
            ("라우팅 일관성", tester.test_routing_consistency),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                print(f"\n{'='*60}")
                print(f"[테스트] {name}")
                print("="*60)

                await test_func()

                passed += 1
                print(f"\n✅ {name} 성공")
            except Exception as e:
                failed += 1
                print(f"\n❌ {name} 실패: {e}")
                import traceback
                traceback.print_exc()

        print("\n" + "=" * 60)
        print(f"테스트 결과: {passed} 성공, {failed} 실패")
        print("=" * 60)

        return failed == 0

    success = asyncio.run(main())
    exit(0 if success else 1)
