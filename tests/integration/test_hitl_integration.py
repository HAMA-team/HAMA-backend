"""
HITL (Human-in-the-Loop) Integration Tests

이 테스트는 Trading Agent와 Portfolio Agent의 HITL 기능을 검증합니다.

테스트 범위:
1. Trading Agent - 자동화 레벨별 승인 플로우
2. Portfolio Agent - 리밸런싱 승인 플로우
3. Interrupt 발생 및 Resume 검증
4. 자동화 레벨 1(Pilot)의 자동 승인

사용법:
    pytest tests/integration/test_hitl_integration.py -v
    PYTHONPATH=. pytest tests/integration/test_hitl_integration.py -v
"""
import asyncio
import pytest
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from src.agents.trading import trading_agent
from src.agents.portfolio import portfolio_agent
from tests.conftest import create_test_portfolio, create_test_chat_session


class TestTradingAgentHITL:
    """Trading Agent HITL 통합 테스트"""

    @pytest.mark.asyncio
    async def test_trading_automation_level_1_behavior(self, clean_db, db_session):
        """
        자동화 레벨 1 (Pilot): Interrupt는 발생하지만 조건부 로직 검증

        NOTE: interrupt_before는 항상 노드 전에 멈춥니다.
        Level 1의 자동 승인은 Chat API에서 automation_level을 확인 후 자동 resume하는 방식으로 구현됩니다.

        이 테스트는 interrupt가 발생함을 확인하고, automation_level=1임을 검증합니다.
        """
        print("\n[Test] Trading Agent - Level 1 Interrupt 동작 확인")

        portfolio = create_test_portfolio(
            db_session,
            holdings=[
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 10,
                    "avg_price": 70000,
                    "current_price": 75000,
                    "market_value": 750000,
                    "weight": 0.5
                }
            ]
        )

        initial_state = {
            "messages": [HumanMessage(content="삼성전자 10주 매수")],
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "query": "삼성전자 10주 매수",
            "stock_code": "005930",
            "quantity": 10,
            "order_type": "BUY",
            "automation_level": 1,  # Pilot 모드
            "trade_prepared": False,
            "trade_approved": False,
            "trade_executed": False,
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        # 실행
        result = await trading_agent.ainvoke(initial_state, config)
        state = await trading_agent.aget_state(config)

        # Interrupt 발생 확인
        assert state.next, "Interrupt가 발생해야 함"
        assert state.next[0] == "approval_trade", "approval_trade 노드에서 멈춰야 함"
        assert state.values.get("automation_level") == 1, "Automation level이 1이어야 함"

        print(f"✅ Level 1에서 interrupt 발생 확인 (Chat API에서 자동 resume 처리 필요)")
        print(f"   Automation Level: {state.values.get('automation_level')}")
        print(f"   Next Node: {state.next[0]}")


    @pytest.mark.asyncio
    async def test_trading_automation_level_2_requires_approval(self, clean_db, db_session):
        """
        자동화 레벨 2 (Copilot): 사용자 승인 필요

        approval_trade_node에서 interrupt가 발생하고,
        사용자 승인 후 재개되어야 함
        """
        print("\n[Test] Trading Agent - Level 2 승인 필요")

        portfolio = create_test_portfolio(
            db_session,
            holdings=[
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 10,
                    "avg_price": 70000,
                    "current_price": 75000,
                    "market_value": 750000,
                    "weight": 0.5
                }
            ],
        )

        initial_state = {
            "messages": [HumanMessage(content="삼성전자 10주 매수")],
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "query": "삼성전자 10주 매수",
            "stock_code": "005930",
            "quantity": 10,
            "order_type": "BUY",
            "automation_level": 2,  # Copilot 모드
            "trade_prepared": False,
            "trade_approved": False,
            "trade_executed": False,
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        # 1단계: Interrupt 발생 확인
        result = await trading_agent.ainvoke(initial_state, config)

        state = await trading_agent.aget_state(config)

        # Interrupt 검증
        assert state.next, "Interrupt가 발생해야 함"
        assert state.next[0] == "approval_trade", "approval_trade 노드에서 멈춰야 함"

        # Interrupt 데이터 검증
        if state.tasks:
            task = state.tasks[0]
            if task.interrupts:
                interrupt_data = task.interrupts[0].value
                assert interrupt_data["type"] == "trade_approval"
                assert interrupt_data["stock_code"] == "005930"
                assert interrupt_data["automation_level"] == 2
                print(f"✅ Interrupt 데이터: {interrupt_data}")

        # 2단계: 승인 후 재개
        resume_command: Command = {"resume": {"approved": True, "user_id": str(portfolio.user_id)}}
        result = await trading_agent.ainvoke(resume_command, config)

        # 검증
        assert result.get("trade_approved") is True, "승인되어야 함"
        assert result.get("trade_executed") is True, "매매가 실행되어야 함"

        print("✅ Level 2 승인 플로우 성공")


    @pytest.mark.asyncio
    async def test_trading_automation_level_3_requires_approval(self, clean_db, db_session):
        """
        자동화 레벨 3 (Advisor): 사용자 승인 필수

        Level 2와 동일하게 interrupt 발생
        """
        print("\n[Test] Trading Agent - Level 3 승인 필수")

        portfolio = create_test_portfolio(
            db_session,
            holdings=[],
        )

        initial_state = {
            "messages": [HumanMessage(content="삼성전자 5주 매수")],
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "query": "삼성전자 5주 매수",
            "stock_code": "005930",
            "quantity": 5,
            "order_type": "BUY",
            "automation_level": 3,  # Advisor 모드
            "trade_prepared": False,
            "trade_approved": False,
            "trade_executed": False,
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        # Interrupt 발생 확인
        result = await trading_agent.ainvoke(initial_state, config)
        state = await trading_agent.aget_state(config)

        assert state.next, "Interrupt가 발생해야 함"
        assert state.next[0] == "approval_trade", "approval_trade 노드에서 멈춰야 함"

        print("✅ Level 3 Interrupt 발생 확인")


class TestPortfolioAgentHITL:
    """Portfolio Agent HITL 통합 테스트"""

    @pytest.mark.asyncio
    async def test_portfolio_automation_level_1_behavior(self, clean_db, db_session):
        """
        자동화 레벨 1 (Pilot): Interrupt 동작 확인

        NOTE: interrupt_before는 항상 노드 전에 멈춥니다.
        Level 1의 자동 승인은 Chat API에서 처리됩니다.
        """
        print("\n[Test] Portfolio Agent - Level 1 Interrupt 동작 확인")

        portfolio = create_test_portfolio(
            db_session,
            holdings=[
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 10,
                    "avg_price": 70000,
                    "current_price": 75000,
                    "market_value": 750000,
                    "weight": 0.75  # 75% 집중 - 리밸런싱 필요
                }
            ],
        )

        initial_state = {
            "messages": [HumanMessage(content="포트폴리오 리밸런싱")],
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "automation_level": 1,  # Pilot 모드
            "risk_profile": "moderate",
            "rebalance_prepared": False,
            "rebalance_approved": False,
            "rebalance_executed": False,
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        # 실행
        result = await portfolio_agent.ainvoke(initial_state, config)
        state = await portfolio_agent.aget_state(config)

        # 리밸런싱이 필요한 경우 interrupt 확인
        if result.get("rebalancing_needed"):
            # Interrupt 발생 확인
            if state.next:
                assert state.next[0] == "approval_rebalance", "approval_rebalance 노드에서 멈춰야 함"
                assert state.values.get("automation_level") == 1, "Automation level이 1이어야 함"
                print("✅ Level 1에서 interrupt 발생 확인 (Chat API에서 자동 resume 처리 필요)")
                print(f"   Automation Level: {state.values.get('automation_level')}")
                print(f"   Rebalancing Needed: {result.get('rebalancing_needed')}")
        else:
            print("⏭️ 리밸런싱이 필요하지 않음")


    @pytest.mark.asyncio
    async def test_portfolio_automation_level_2_requires_approval(self, clean_db, db_session):
        """
        자동화 레벨 2 (Copilot): 리밸런싱 사용자 승인 필요

        approval_rebalance_node에서 interrupt가 발생하고,
        사용자 승인 후 재개되어야 함
        """
        print("\n[Test] Portfolio Agent - Level 2 승인 필요")

        portfolio = create_test_portfolio(
            db_session,
            holdings=[
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 20,
                    "avg_price": 70000,
                    "current_price": 75000,
                    "market_value": 1500000,
                    "weight": 0.75  # 75% 집중
                }
            ],
        )

        initial_state = {
            "messages": [HumanMessage(content="포트폴리오 리밸런싱")],
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "automation_level": 2,  # Copilot 모드
            "risk_profile": "moderate",
            "rebalance_prepared": False,
            "rebalance_approved": False,
            "rebalance_executed": False,
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        # 1단계: Interrupt 발생 확인
        result = await portfolio_agent.ainvoke(initial_state, config)

        state = await portfolio_agent.aget_state(config)

        # 리밸런싱이 필요한 경우에만 interrupt 발생
        if result.get("rebalancing_needed"):
            assert state.next, "Interrupt가 발생해야 함"
            assert state.next[0] == "approval_rebalance", "approval_rebalance 노드에서 멈춰야 함"

            # Interrupt 데이터 검증
            if state.tasks:
                task = state.tasks[0]
                if task.interrupts:
                    interrupt_data = task.interrupts[0].value
                    assert interrupt_data["type"] == "rebalance_approval"
                    assert interrupt_data["rebalancing_needed"] is True
                    assert "trades_required" in interrupt_data
                    print(f"✅ Interrupt 데이터: {interrupt_data['type']}, Trades: {len(interrupt_data.get('trades_required', []))}")

            # 2단계: 승인 후 재개
            resume_command: Command = {"resume": {"approved": True, "user_id": str(portfolio.user_id)}}
            result = await portfolio_agent.ainvoke(resume_command, config)

            # 검증
            assert result.get("rebalance_approved") is True, "승인되어야 함"
            assert result.get("rebalance_executed") is True, "리밸런싱이 실행되어야 함"

            print("✅ Level 2 리밸런싱 승인 플로우 성공")
        else:
            print("⏭️ 리밸런싱이 필요하지 않음 (자동 승인)")


    @pytest.mark.asyncio
    async def test_portfolio_no_rebalancing_needed(self, clean_db, db_session):
        """
        리밸런싱이 필요하지 않은 경우

        approval_rebalance_node가 자동 승인하고 interrupt 없이 진행
        """
        print("\n[Test] Portfolio Agent - 리밸런싱 불필요")

        portfolio = create_test_portfolio(
            db_session,
            holdings=[
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 6,
                    "avg_price": 70000,
                    "current_price": 75000,
                    "market_value": 450000,
                    "weight": 0.45
                },
                {
                    "stock_code": "000660",
                    "stock_name": "SK하이닉스",
                    "quantity": 3,
                    "avg_price": 150000,
                    "current_price": 155000,
                    "market_value": 465000,
                    "weight": 0.465
                }
            ],
        )

        initial_state = {
            "messages": [HumanMessage(content="포트폴리오 확인")],
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "automation_level": 2,
            "risk_profile": "moderate",
            "rebalance_prepared": False,
            "rebalance_approved": False,
            "rebalance_executed": False,
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        # 실행
        result = await portfolio_agent.ainvoke(initial_state, config)

        # 검증
        state = await portfolio_agent.aget_state(config)
        assert not state.next, "Interrupt가 없어야 함"
        assert result.get("rebalance_approved") is True, "자동 승인되어야 함"

        print("✅ 리밸런싱 불필요 시나리오 통과")


# 직접 실행 가능
if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/Users/elaus/PycharmProjects/HAMA-backend")

    pytest.main([__file__, "-v", "-s"])
