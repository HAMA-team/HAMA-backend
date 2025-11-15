"""
HITL Trading Flow 통합 테스트

Portfolio Simulator 패턴이 적용된 매매 플로우를 테스트합니다:
1. request_trade tool 호출
2. trade_planner: 매매 제안 구조화
3. portfolio_simulator: 전/후 비교 계산
4. trade_hitl: HITL interrupt (전/후 데이터 포함)
5. 사용자 승인 또는 수정
6. execute_trade: 실제 실행
"""
import asyncio
import logging
import sys
from pathlib import Path
from uuid import uuid4

# PYTHONPATH 설정
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_basic_trade_approval():
    """기본 매매 승인 플로우 테스트"""
    from src.subgraphs.graph_master import build_graph
    from src.schemas.graph_state import GraphState
    from langchain_core.messages import HumanMessage
    from langgraph_sdk.schema import Command

    print("\n" + "="*80)
    print("🧪 테스트 1: 기본 매매 승인 플로우")
    print("="*80)

    # 그래프 생성
    graph = build_graph(intervention_required=False, use_checkpointer=False)

    # 초기 상태
    user_id = str(uuid4())
    conversation_id = str(uuid4())

    initial_state = GraphState(
        user_id=user_id,
        conversation_id=conversation_id,
        messages=[HumanMessage(content="삼성전자 10주 시장가로 매수해줘")],
    )

    thread_id = {"configurable": {"thread_id": conversation_id}}

    try:
        # 1단계: 매매 요청 (interrupt 발생까지)
        print("\n[1단계] 매매 요청 실행 중...")
        result = await graph.ainvoke(initial_state, config=thread_id)

        # Interrupt 발생 확인
        state = await graph.aget_state(config=thread_id)

        if state.next:
            print(f"✅ Interrupt 발생! 다음 노드: {state.next}")

            # Interrupt payload 확인
            if state.tasks:
                first_task = state.tasks[0]
                if hasattr(first_task, 'interrupts') and first_task.interrupts:
                    interrupt_data = first_task.interrupts[0].value
                    print(f"\n📊 HITL 데이터:")
                    print(f"  - 종목: {interrupt_data.get('stock_name', interrupt_data.get('stock_code'))}")
                    print(f"  - 액션: {interrupt_data.get('action')}")
                    print(f"  - 수량: {interrupt_data.get('quantity')}")
                    print(f"  - 가격: {interrupt_data.get('price')}")

                    # 전/후 비교 데이터 확인
                    if 'portfolio_before' in interrupt_data and 'portfolio_after' in interrupt_data:
                        print(f"\n📈 포트폴리오 전/후 비교:")
                        before = interrupt_data['portfolio_before']
                        after = interrupt_data['portfolio_after']
                        print(f"  - 총 자산: {before.get('total_value'):,.0f}원 → {after.get('total_value'):,.0f}원")
                        print(f"  - 현금: {before.get('cash_balance'):,.0f}원 → {after.get('cash_balance'):,.0f}원")

                        # 리스크 변화
                        risk_before = interrupt_data.get('risk_before', {})
                        risk_after = interrupt_data.get('risk_after', {})
                        if risk_before and risk_after:
                            print(f"\n📉 리스크 변화:")
                            print(f"  - 변동성: {risk_before.get('portfolio_volatility')} → {risk_after.get('portfolio_volatility')}")
                            print(f"  - VaR(95%): {risk_before.get('var_95')} → {risk_after.get('var_95')}")
                            print(f"  - Sharpe: {risk_before.get('sharpe_ratio')} → {risk_after.get('sharpe_ratio')}")

            # 2단계: 사용자 승인 (수정 없이)
            print("\n[2단계] 사용자 승인 처리 중...")
            resume_result = await graph.ainvoke(
                None,
                config=thread_id,
                command=Command(
                    resume={
                        "trade_approved": True,
                        "user_id": user_id,
                    }
                )
            )

            # 최종 상태 확인
            final_state = await graph.aget_state(config=thread_id)
            print(f"\n✅ 최종 상태:")
            print(f"  - trade_prepared: {final_state.values.get('trade_prepared')}")
            print(f"  - trade_approved: {final_state.values.get('trade_approved')}")
            print(f"  - trade_executed: {final_state.values.get('trade_executed')}")

            if final_state.values.get('trade_result'):
                print(f"  - 주문 결과: {final_state.values['trade_result']}")

            print("\n✅ 테스트 1 성공!")

        else:
            print("⚠️ Interrupt가 발생하지 않았습니다.")

    except Exception as exc:
        print(f"\n❌ 테스트 1 실패: {exc}")
        import traceback
        traceback.print_exc()


async def test_modified_trade():
    """매매 수정 후 재시뮬레이션 테스트"""
    from src.subgraphs.graph_master import build_graph
    from src.schemas.graph_state import GraphState
    from langchain_core.messages import HumanMessage
    from langgraph_sdk.schema import Command

    print("\n" + "="*80)
    print("🧪 테스트 2: 매매 수정 후 재시뮬레이션")
    print("="*80)

    # 그래프 생성
    graph = build_graph(intervention_required=False, use_checkpointer=False)

    # 초기 상태
    user_id = str(uuid4())
    conversation_id = str(uuid4())

    initial_state = GraphState(
        user_id=user_id,
        conversation_id=conversation_id,
        messages=[HumanMessage(content="삼성전자 10주 75000원에 매수해줘")],
    )

    thread_id = {"configurable": {"thread_id": conversation_id}}

    try:
        # 1단계: 매매 요청
        print("\n[1단계] 매매 요청 실행 중...")
        await graph.ainvoke(initial_state, config=thread_id)

        state = await graph.aget_state(config=thread_id)

        if state.next:
            print(f"✅ 첫 번째 Interrupt 발생! 다음 노드: {state.next}")

            # 2단계: 사용자가 수정 (수량을 5주로 변경)
            print("\n[2단계] 사용자 수정사항 반영 (10주 → 5주)...")
            await graph.ainvoke(
                None,
                config=thread_id,
                command=Command(
                    resume={
                        "trade_approved": True,
                        "user_modifications": {
                            "quantity": 5,  # 10주 → 5주
                        },
                        "user_id": user_id,
                    }
                )
            )

            # 재시뮬레이션 후 두 번째 interrupt 확인
            state2 = await graph.aget_state(config=thread_id)

            if state2.next:
                print(f"✅ 재시뮬레이션 후 두 번째 Interrupt 발생! 다음 노드: {state2.next}")

                # 수정된 데이터 확인
                if state2.tasks:
                    first_task = state2.tasks[0]
                    if hasattr(first_task, 'interrupts') and first_task.interrupts:
                        interrupt_data = first_task.interrupts[0].value
                        print(f"\n📊 수정된 HITL 데이터:")
                        print(f"  - 수량: {interrupt_data.get('quantity')} (변경됨!)")

                        # 재시뮬레이션된 전/후 비교
                        if 'portfolio_after' in interrupt_data:
                            after = interrupt_data['portfolio_after']
                            print(f"  - 재계산된 현금: {after.get('cash_balance'):,.0f}원")

                # 3단계: 최종 승인
                print("\n[3단계] 수정된 주문 최종 승인...")
                await graph.ainvoke(
                    None,
                    config=thread_id,
                    command=Command(
                        resume={
                            "trade_approved": True,
                            "user_id": user_id,
                        }
                    )
                )

                final_state = await graph.aget_state(config=thread_id)
                print(f"\n✅ 최종 상태:")
                print(f"  - trade_quantity: {final_state.values.get('trade_quantity')} (5주로 변경 확인)")
                print(f"  - trade_executed: {final_state.values.get('trade_executed')}")

                print("\n✅ 테스트 2 성공!")

            else:
                print("⚠️ 재시뮬레이션 후 Interrupt가 발생하지 않았습니다.")

        else:
            print("⚠️ 첫 번째 Interrupt가 발생하지 않았습니다.")

    except Exception as exc:
        print(f"\n❌ 테스트 2 실패: {exc}")
        import traceback
        traceback.print_exc()


async def main():
    """전체 테스트 실행"""
    print("\n" + "="*80)
    print("🚀 HITL Trading Flow 통합 테스트 시작")
    print("="*80)

    # 테스트 1: 기본 승인
    await test_basic_trade_approval()

    # 테스트 2: 수정 후 재시뮬레이션
    await test_modified_trade()

    print("\n" + "="*80)
    print("✅ 모든 테스트 완료!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
