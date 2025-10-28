"""
Trading Agent 단위 테스트

테스트 범위:
1. 주문 생성 (prepare_trade)
2. HITL 승인 (approval_trade + interrupt)
3. 거래 실행 (execute_trade)
4. 멱등성 검증
5. 전체 플로우

사용법:
    pytest tests/unit/test_agents/test_trading_agent.py -v
    python tests/unit/test_agents/test_trading_agent.py  # 직접 실행
"""
import asyncio
import pytest
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from src.agents.trading import trading_agent
from tests.conftest import create_test_portfolio, create_test_chat_session


class TestTradingAgent:
    """Trading Agent 단위 테스트"""

    @pytest.mark.asyncio
    async def test_prepare_trade_buy_order(self, clean_db, db_session):
        """
        1단계: 매수 주문 생성 테스트

        prepare_trade_node가 정상적으로 주문을 생성하는지 검증
        """
        print("\n[Test] 매수 주문 생성")

        # 테스트 포트폴리오 생성
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

        # Trading Agent 초기 상태
        initial_state = {
            "messages": [HumanMessage(content="삼성전자 10주 매수")],
            "request_id": str(uuid4()),
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "query": "삼성전자 10주 매수",
            "automation_level": 2,
            "stock_code": "005930",
            "quantity": 10,
            "order_type": "BUY",
            "order_price": 75000.0,
            "trade_prepared": False,
            "trade_approved": False,
            "trade_executed": False,
        }

        config = {
            "configurable": {
                "thread_id": str(uuid4())
            }
        }

        # prepare_trade까지만 실행 (interrupt 전)
        result = await trading_agent.ainvoke(initial_state, config)

        # 검증
        assert result["trade_prepared"] is True, "주문이 준비되어야 함"
        assert "trade_order_id" in result, "주문 ID가 생성되어야 함"
        assert result["trade_summary"] is not None, "주문 요약이 있어야 함"

        order_summary = result["trade_summary"]
        assert order_summary["stock_code"] == "005930"
        assert order_summary["order_quantity"] == 10
        assert order_summary["order_type"] == "BUY"

        print(f"  ✅ 주문 생성 완료: {result['trade_order_id']}")
        print(f"  📋 주문 정보: {order_summary['stock_code']} {order_summary['order_quantity']}주")

    @pytest.mark.asyncio
    async def test_prepare_trade_sell_order(self, clean_db, db_session):
        """
        1단계: 매도 주문 생성 테스트
        """
        print("\n[Test] 매도 주문 생성")

        portfolio = create_test_portfolio(
            db_session,
            holdings=[
                {
                    "stock_code": "000660",
                    "stock_name": "SK하이닉스",
                    "quantity": 20,
                    "avg_price": 90000,
                    "current_price": 95000,
                    "market_value": 1900000,
                    "weight": 0.4
                }
            ]
        )

        initial_state = {
            "messages": [HumanMessage(content="SK하이닉스 5주 매도")],
            "request_id": str(uuid4()),
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "query": "SK하이닉스 5주 매도",
            "automation_level": 2,
            "stock_code": "000660",
            "quantity": 5,
            "order_type": "SELL",
            "order_price": 95000.0,
            "trade_prepared": False,
            "trade_approved": False,
            "trade_executed": False,
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        result = await trading_agent.ainvoke(initial_state, config)

        # 검증
        assert result["trade_prepared"] is True
        assert result["trade_summary"]["order_type"] == "SELL"
        assert result["trade_summary"]["order_quantity"] == 5

        print(f"  ✅ 매도 주문 생성: {result['trade_order_id']}")

    @pytest.mark.asyncio
    async def test_approval_interrupt_triggered(self, clean_db, db_session):
        """
        2단계: HITL Interrupt 발생 테스트

        automation_level=2에서 approval_trade 노드가 interrupt를 발생시키는지 검증
        """
        print("\n[Test] HITL Interrupt 발생")

        portfolio = create_test_portfolio(db_session)

        initial_state = {
            "messages": [HumanMessage(content="삼성전자 10주 매수")],
            "request_id": str(uuid4()),
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "query": "삼성전자 10주 매수",
            "automation_level": 2,  # Copilot: 승인 필요
            "stock_code": "005930",
            "quantity": 10,
            "order_type": "BUY",
            "trade_prepared": False,
            "trade_approved": False,
            "trade_executed": False,
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        # 실행 (interrupt 발생 예상)
        result = await trading_agent.ainvoke(initial_state, config)

        # State 조회
        state = await trading_agent.aget_state(config)

        # 검증
        assert state.next is not None, "다음 노드가 있어야 함 (중단됨)"
        assert "approval_trade" in state.next, "approval_trade 노드에서 중단되어야 함"
        assert state.tasks is not None, "Interrupt task가 있어야 함"

        # Interrupt 데이터 확인
        if state.tasks:
            task = state.tasks[0]
            if task.interrupts:
                interrupt_data = task.interrupts[0].value
                assert interrupt_data["type"] == "trade_approval"
                assert interrupt_data["stock_code"] == "005930"
                assert interrupt_data["quantity"] == 10
                print(f"  ✅ Interrupt 발생: {interrupt_data}")

    @pytest.mark.asyncio
    async def test_approval_trade_approved(self, clean_db, db_session):
        """
        2단계: 승인 처리 테스트

        interrupt 후 Command(resume)로 승인 처리
        """
        print("\n[Test] 거래 승인 처리")

        portfolio = create_test_portfolio(db_session)

        initial_state = {
            "messages": [HumanMessage(content="삼성전자 5주 매수")],
            "request_id": str(uuid4()),
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "query": "삼성전자 5주 매수",
            "automation_level": 2,
            "stock_code": "005930",
            "quantity": 5,
            "order_type": "BUY",
            "order_price": 75000.0,
            "trade_prepared": False,
            "trade_approved": False,
            "trade_executed": False,
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        # 1단계: Interrupt 발생까지 실행
        await trading_agent.ainvoke(initial_state, config)

        # 2단계: 승인 (resume)
        resume_value = {
            "approved": True,
            "user_id": str(portfolio.user_id),
            "notes": "테스트 승인"
        }

        result = await trading_agent.ainvoke(Command(resume=resume_value), config)

        # 검증
        assert result["trade_approved"] is True, "거래가 승인되어야 함"
        assert result["trade_executed"] is True, "거래가 실행되어야 함"
        assert "trade_result" in result, "거래 결과가 있어야 함"

        trade_result = result["trade_result"]
        assert trade_result["status"] in ["pending", "filled"], "거래 상태 확인"

        print(f"  ✅ 거래 승인 및 실행 완료")
        print(f"  📊 거래 결과: {trade_result}")

    @pytest.mark.asyncio
    async def test_idempotency_prepare_trade(self, clean_db, db_session):
        """
        멱등성 테스트: prepare_trade가 이미 실행된 경우

        trade_prepared=True일 때 중복 실행되지 않는지 검증
        """
        print("\n[Test] 멱등성 - 주문 준비")

        portfolio = create_test_portfolio(db_session)

        initial_state = {
            "messages": [HumanMessage(content="삼성전자 10주 매수")],
            "request_id": str(uuid4()),
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "query": "삼성전자 10주 매수",
            "automation_level": 2,
            "stock_code": "005930",
            "quantity": 10,
            "order_type": "BUY",
            "trade_prepared": True,  # 이미 준비됨
            "trade_order_id": "existing-order-123",
            "trade_summary": {
                "order_id": "existing-order-123",
                "stock_code": "005930",
                "order_quantity": 10,
                "order_type": "BUY"
            },
            "trade_approved": False,
            "trade_executed": False,
        }

        config = {"configurable": {"thread_id": str(uuid4())}}

        result = await trading_agent.ainvoke(initial_state, config)

        # 검증: 기존 order_id 유지
        assert result["trade_order_id"] == "existing-order-123", "기존 주문 ID 유지"
        assert result["trade_prepared"] is True

        print(f"  ✅ 멱등성 보장: 기존 주문 재사용")

    @pytest.mark.asyncio
    async def test_execute_trade_without_approval(self, clean_db, db_session):
        """
        에러 케이스: 승인 없이 실행 시도

        trade_approved=False일 때 execute_trade가 에러 반환하는지 검증
        """
        print("\n[Test] 에러 케이스 - 승인 없이 실행")

        portfolio = create_test_portfolio(db_session)

        initial_state = {
            "messages": [HumanMessage(content="삼성전자 10주 매수")],
            "request_id": str(uuid4()),
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "query": "삼성전자 10주 매수",
            "automation_level": 2,
            "stock_code": "005930",
            "quantity": 10,
            "order_type": "BUY",
            "trade_prepared": True,
            "trade_order_id": "test-order-456",
            "trade_approved": False,  # 승인 안 됨
            "trade_executed": False,
        }

        # 강제로 execute_trade까지 진행 (approval 건너뛰기)
        # Note: 실제로는 그래프 구조상 불가능하지만 노드 개별 테스트
        from src.agents.trading.nodes import execute_trade_node

        result = await execute_trade_node(initial_state)

        # 검증
        assert "error" in result, "에러가 발생해야 함"
        assert "승인되지 않았습니다" in result["error"]

        print(f"  ✅ 에러 처리: {result['error']}")

    @pytest.mark.asyncio
    async def test_full_trading_workflow(self, clean_db, db_session):
        """
        전체 플로우 테스트: prepare → approval → execute

        실제 사용자 시나리오를 완전히 재현
        """
        print("\n[Test] 전체 매매 플로우")

        # 1. 포트폴리오 준비
        portfolio = create_test_portfolio(
            db_session,
            holdings=[
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "quantity": 5,
                    "avg_price": 70000,
                    "current_price": 75000,
                    "market_value": 375000,
                    "weight": 0.25
                }
            ]
        )

        print(f"  📁 포트폴리오 ID: {portfolio.portfolio_id}")

        # 2. 초기 상태
        initial_state = {
            "messages": [HumanMessage(content="삼성전자 10주 추가 매수")],
            "request_id": str(uuid4()),
            "user_id": str(portfolio.user_id),
            "portfolio_id": str(portfolio.portfolio_id),
            "query": "삼성전자 10주 추가 매수",
            "automation_level": 2,
            "stock_code": "005930",
            "quantity": 10,
            "order_type": "BUY",
            "order_price": 76000.0,
            "trade_prepared": False,
            "trade_approved": False,
            "trade_executed": False,
        }

        thread_id = str(uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        # 3. 실행 (interrupt 발생)
        print("  🚀 1단계: 주문 생성 및 승인 요청")
        result1 = await trading_agent.ainvoke(initial_state, config)

        state1 = await trading_agent.aget_state(config)
        assert state1.next is not None, "Interrupt 발생"
        print(f"  ⏸️  Interrupt 발생: {state1.next}")

        # 4. 승인
        print("  ✅ 2단계: 사용자 승인")
        resume_value = {
            "approved": True,
            "user_id": str(portfolio.user_id),
        }

        result2 = await trading_agent.ainvoke(Command(resume=resume_value), config)

        # 5. 최종 검증
        assert result2["trade_prepared"] is True
        assert result2["trade_approved"] is True
        assert result2["trade_executed"] is True
        assert "trade_result" in result2

        trade_result = result2["trade_result"]
        print(f"  💰 3단계: 거래 실행 완료")
        print(f"     종목: {trade_result.get('stock_code')}")
        print(f"     수량: {trade_result.get('quantity')}주")
        print(f"     가격: {trade_result.get('price'):,.0f}원")
        print(f"     상태: {trade_result.get('status')}")

        print("\n  ✅ 전체 플로우 성공!")


if __name__ == "__main__":
    """직접 실행"""
    async def main():
        from tests.conftest import clean_db, db_session as get_db_session
        from src.models.database import SessionLocal

        print("=" * 60)
        print("Trading Agent 단위 테스트")
        print("=" * 60)

        # DB 초기화
        from src.models.database import Base, engine
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        db = SessionLocal()

        tester = TestTradingAgent()

        tests = [
            ("매수 주문 생성", tester.test_prepare_trade_buy_order),
            ("매도 주문 생성", tester.test_prepare_trade_sell_order),
            ("HITL Interrupt 발생", tester.test_approval_interrupt_triggered),
            ("거래 승인 처리", tester.test_approval_trade_approved),
            ("멱등성 검증", tester.test_idempotency_prepare_trade),
            ("에러 케이스 (승인 없이 실행)", tester.test_execute_trade_without_approval),
            ("전체 매매 플로우", tester.test_full_trading_workflow),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                print(f"\n{'='*60}")
                print(f"[테스트] {name}")
                print("="*60)

                # clean_db와 db_session을 전달
                # Note: pytest fixture를 직접 실행할 수 없으므로 수동으로 처리
                await test_func(None, db)

                passed += 1
                print(f"\n✅ {name} 성공")
            except Exception as e:
                failed += 1
                print(f"\n❌ {name} 실패: {e}")
                import traceback
                traceback.print_exc()

        db.close()

        print("\n" + "=" * 60)
        print(f"테스트 결과: {passed} 성공, {failed} 실패")
        print("=" * 60)

        return failed == 0

    success = asyncio.run(main())
    exit(0 if success else 1)
