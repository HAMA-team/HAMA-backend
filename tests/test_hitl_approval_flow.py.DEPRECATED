"""HITL 승인 흐름 통합 테스트"""
import asyncio
import logging
from uuid import uuid4

logging.basicConfig(level=logging.INFO)

async def test_hitl_approval_flow():
    """
    HITL 승인 흐름 전체 테스트

    1. 매수 요청 → interrupt 발생
    2. 승인 요청 → 실행
    3. 거부 요청 → 취소
    """
    from src.agents.graph_master import build_graph
    from langgraph.types import Command

    print("\n" + "="*60)
    print("🧪 HITL 승인 흐름 통합 테스트")
    print("="*60)

    # 1. Copilot 모드로 그래프 빌드 (승인 필요)
    app = build_graph(automation_level=2, backend_key="memory")

    user_id = str(uuid4())
    conversation_id = str(uuid4())

    config = {
        "configurable": {
            "thread_id": conversation_id,
        }
    }

    initial_state = {
        "messages": [],
        "user_query": "삼성전자 10주 매수해줘",
        "user_id": user_id,
        "automation_level": 2,
    }

    print("\n1️⃣ 매수 요청 실행...")
    print(f"User ID: {user_id}")
    print(f"Query: {initial_state['user_query']}")
    print(f"Automation Level: 2 (Copilot)")

    try:
        # 그래프 실행 (interrupt 발생 예상)
        result = await app.ainvoke(initial_state, config)

        # State 확인
        state = await app.aget_state(config)

        print(f"\n✅ 그래프 실행 완료")
        print(f"다음 노드: {state.next}")
        print(f"Interrupt 발생: {len(state.tasks) > 0}")

        if state.next:
            print("\n2️⃣ Interrupt 발생! 승인 대기 중...")

            # Interrupt 데이터 확인
            if state.tasks and state.tasks[0].interrupts:
                interrupt_info = state.tasks[0].interrupts[0]
                interrupt_data = interrupt_info.value

                print(f"\nInterrupt 데이터:")
                print(f"  - type: {interrupt_data.get('type')}")
                print(f"  - stock_code: {interrupt_data.get('stock_code')}")
                print(f"  - quantity: {interrupt_data.get('quantity')}")
                print(f"  - order_type: {interrupt_data.get('order_type')}")
                print(f"  - order_id: {interrupt_data.get('order_id')}")

            # 3-A. 승인 테스트
            print("\n3️⃣-A 승인 테스트...")
            resume_command = Command(resume={
                "approved": True,
                "decision": "approved",
                "user_notes": "테스트 승인",
            })

            result = await app.ainvoke(resume_command, config)

            print(f"✅ 승인 처리 완료")
            print(f"Final response: {result.get('final_response', {}).get('summary', 'N/A')}")

            # 새로운 요청으로 거부 테스트
            print("\n" + "="*60)
            print("3️⃣-B 거부 테스트 (새로운 요청)")
            print("="*60)

            # 새 conversation ID로 다시 시작
            conversation_id_2 = str(uuid4())
            config_2 = {
                "configurable": {
                    "thread_id": conversation_id_2,
                }
            }

            initial_state_2 = {
                "messages": [],
                "user_query": "SK하이닉스 5주 매수해줘",
                "user_id": user_id,
                "automation_level": 2,
            }

            result = await app.ainvoke(initial_state_2, config_2)
            state_2 = await app.aget_state(config_2)

            if state_2.next:
                print("\nInterrupt 발생, 거부 테스트 시작...")

                # aupdate_state로 거부 처리
                await app.aupdate_state(
                    config_2,
                    {
                        "final_response": {
                            "summary": "사용자가 거부함",
                            "cancelled": True,
                            "reason": "테스트 거부",
                        }
                    }
                )

                final_state_2 = await app.aget_state(config_2)
                print(f"✅ 거부 처리 완료")
                print(f"Final state: {final_state_2.values.get('final_response')}")

        else:
            print("⚠️ Interrupt가 발생하지 않았습니다 (automation_level=1일 가능성)")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("✅ 테스트 완료")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_hitl_approval_flow())
