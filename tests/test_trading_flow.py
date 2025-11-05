"""Trading Agent 흐름 디버깅 테스트"""
import asyncio
import logging
from uuid import uuid4

logging.basicConfig(level=logging.INFO)

async def test_trading_flow():
    """Trading Agent 전체 흐름 테스트"""
    from src.agents.trading.graph import build_trading_subgraph
    from src.agents.trading.state import TradingState

    # 1. 서브그래프 생성
    workflow = build_trading_subgraph()
    graph = workflow.compile()

    # 2. 초기 상태 생성
    user_id = str(uuid4())
    portfolio_id = str(uuid4())

    initial_state = TradingState(
        user_id=user_id,
        portfolio_id=portfolio_id,
        stock_code="005930",  # 삼성전자
        order_type="BUY",
        quantity=10,
        automation_level=1,  # Pilot 모드 (자동 실행)
        messages=[],
    )

    print("\n" + "="*60)
    print("🧪 Trading Agent 흐름 테스트")
    print("="*60)
    print(f"종목: 삼성전자 (005930)")
    print(f"주문: BUY 10주")
    print(f"자동화 레벨: 1 (Pilot - 자동 실행)")
    print("="*60 + "\n")

    # 3. 그래프 실행
    try:
        final_state = await graph.ainvoke(initial_state)

        print("\n" + "="*60)
        print("✅ 실행 완료!")
        print("="*60)
        print(f"trade_approved: {final_state.get('trade_approved')}")
        print(f"trade_executed: {final_state.get('trade_executed')}")
        print(f"trade_order_id: {final_state.get('trade_order_id')}")

        if final_state.get('trade_result'):
            result = final_state['trade_result']
            print(f"\n주문 결과:")
            print(f"  상태: {result.get('status')}")
            print(f"  KIS 주문번호: {result.get('kis_order_no')}")
            print(f"  KIS 실행 여부: {result.get('kis_executed')}")

        if final_state.get('error'):
            print(f"\n⚠️ 오류: {final_state['error']}")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_trading_flow())
