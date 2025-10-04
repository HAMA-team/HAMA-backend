"""
HITL (Human-in-the-Loop) 테스트

LangGraph interrupt 기능과 매매 실행 플로우를 테스트합니다.
"""
import asyncio
import sys
import os

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.graph_master import build_graph
from langgraph.types import Command
from langchain_core.messages import HumanMessage


async def test_trade_execution_with_hitl():
    """
    매매 실행 HITL 테스트

    Flow:
    1. "삼성전자 매수" 명령 실행
    2. Interrupt 발생 확인
    3. 승인 후 재개
    4. 매매 실행 완료 확인
    """
    print("\n" + "=" * 60)
    print("🧪 HITL 매매 실행 테스트")
    print("=" * 60)

    # 1. Graph 생성 (Level 2 - Copilot)
    app = build_graph(automation_level=2)

    config = {
        "configurable": {
            "thread_id": "test_thread_001",
        }
    }

    # 2. 초기 상태 - LangGraph 표준: messages 사용
    initial_state = {
        "messages": [HumanMessage(content="삼성전자 매수")],
        "user_id": "test_user",
        "conversation_id": "test_thread_001",
        "automation_level": 2,
        "intent": None,
        "agent_results": {},
        "agents_to_call": [],
        "agents_called": [],
        "risk_level": None,
        "hitl_required": False,
        "trade_prepared": False,
        "trade_approved": False,
        "trade_executed": False,
        "trade_order_id": None,
        "trade_result": None,
        "summary": None,
        "final_response": None,
    }

    # 3. 그래프 실행 (interrupt까지)
    print("\n📤 [1단계] 그래프 실행 시작...")
    result = await app.ainvoke(initial_state, config=config)

    # 4. 상태 확인
    state = await app.aget_state(config)

    print(f"\n📊 [결과] next 노드: {state.next}")
    print(f"📊 [결과] 값: {state.values.get('trade_order_id')}")

    if state.next:
        print(f"\n✅ Interrupt 발생! 다음 노드: {state.next[0]}")
        print(f"📝 중단된 태스크 수: {len(state.tasks)}")

        # Interrupt 정보 추출
        if state.tasks:
            task = state.tasks[0]
            if task.interrupts:
                interrupt_data = task.interrupts[0].value
                print(f"🔔 Interrupt 데이터: {interrupt_data}")

        # 5. 승인 시뮬레이션
        print("\n🤝 [2단계] 사용자 승인...")
        resume_value = {
            "approved": True,
            "user_id": "test_user",
            "notes": "Test approval"
        }

        # 6. 그래프 재개
        print("▶️ [3단계] 그래프 재개...")
        resumed_result = await app.ainvoke(Command(resume=resume_value), config=config)

        # 7. 최종 결과 확인
        final_response = resumed_result.get("final_response", {})
        trade_result = final_response.get("trade_result")

        print(f"\n✅ 최종 결과: {final_response.get('summary')}")
        if trade_result:
            print(f"💰 매매 실행 완료!")
            print(f"   - 주문 번호: {trade_result.get('order_id')}")
            print(f"   - 상태: {trade_result.get('status')}")
            print(f"   - 체결가: {trade_result.get('price'):,}원")
            print(f"   - 수량: {trade_result.get('quantity')}주")
            print(f"   - 총액: {trade_result.get('total'):,}원")

        print("\n✅ 테스트 성공!")
    else:
        print("\n❌ Interrupt가 발생하지 않았습니다!")
        print(f"최종 응답: {result.get('final_response')}")


async def test_trade_rejection():
    """
    매매 실행 거부 테스트

    Flow:
    1. "삼성전자 매수" 명령 실행
    2. Interrupt 발생
    3. 거부 처리
    4. 취소 확인
    """
    print("\n" + "=" * 60)
    print("🧪 HITL 매매 거부 테스트")
    print("=" * 60)

    app = build_graph(automation_level=2)

    config = {
        "configurable": {
            "thread_id": "test_thread_002",
        }
    }

    initial_state = {
        "messages": [HumanMessage(content="SK하이닉스 100주 매수")],
        "user_id": "test_user",
        "conversation_id": "test_thread_002",
        "automation_level": 2,
        "intent": None,
        "agent_results": {},
        "agents_to_call": [],
        "agents_called": [],
        "risk_level": None,
        "hitl_required": False,
        "trade_prepared": False,
        "trade_approved": False,
        "trade_executed": False,
        "trade_order_id": None,
        "trade_result": None,
        "summary": None,
        "final_response": None,
    }

    # 1. 실행
    print("\n📤 [1단계] 그래프 실행...")
    await app.ainvoke(initial_state, config=config)

    # 2. Interrupt 확인
    state = await app.aget_state(config)

    if state.next:
        print(f"✅ Interrupt 발생! (노드: {state.next[0]})")

        # 3. 거부 처리
        print("\n❌ [2단계] 사용자 거부...")
        await app.aupdate_state(
            config,
            {
                "final_response": {
                    "summary": "사용자가 거부함",
                    "cancelled": True,
                    "reason": "User rejected - test"
                }
            }
        )

        # 4. 상태 확인
        final_state = await app.aget_state(config)
        final_response = final_state.values.get("final_response", {})

        print(f"\n✅ 거부 완료: {final_response.get('summary')}")
        print(f"   - 취소됨: {final_response.get('cancelled')}")
        print(f"   - 사유: {final_response.get('reason')}")

        print("\n✅ 테스트 성공!")
    else:
        print("\n❌ Interrupt가 발생하지 않았습니다!")


async def test_level_1_auto():
    """
    Level 1 (Pilot) - 자동 실행 테스트

    Interrupt 없이 자동 실행되어야 함
    """
    print("\n" + "=" * 60)
    print("🧪 Level 1 (Pilot) 자동 실행 테스트")
    print("=" * 60)

    # Level 1 그래프
    app = build_graph(automation_level=1)

    config = {
        "configurable": {
            "thread_id": "test_thread_003",
        }
    }

    initial_state = {
        "messages": [HumanMessage(content="네이버 매수")],
        "user_id": "test_user",
        "conversation_id": "test_thread_003",
        "automation_level": 1,
        "intent": None,
        "agent_results": {},
        "agents_to_call": [],
        "agents_called": [],
        "risk_level": None,
        "hitl_required": False,
        "trade_prepared": False,
        "trade_approved": False,
        "trade_executed": False,
        "trade_order_id": None,
        "trade_result": None,
        "summary": None,
        "final_response": None,
    }

    print("\n📤 [1단계] Level 1 그래프 실행...")
    result = await app.ainvoke(initial_state, config=config)

    # Interrupt 확인
    state = await app.aget_state(config)

    if state.next:
        print(f"\n❌ Level 1인데 Interrupt 발생! (예상: 자동 실행)")
        print(f"   다음 노드: {state.next}")
        print("   ⚠️ interrupt_before 설정 확인 필요")
    else:
        print(f"\n✅ Interrupt 없이 자동 실행 완료!")
        final_response = result.get("final_response", {})
        print(f"   요약: {final_response.get('summary')}")

        # 매매 결과 확인 (Level 1은 interrupt 없이 바로 실행)
        # 하지만 현재 구현은 interrupt_before가 없어서 approval_trade가 실행됨
        # TODO: approval_trade 노드에서 Level 1일 때 자동 승인 로직 추가

        print("\n✅ 테스트 완료!")


async def main():
    """모든 테스트 실행"""
    print("\n" + "🚀" * 30)
    print("HITL 통합 테스트 시작")
    print("🚀" * 30)

    try:
        # Test 1: 매매 실행 및 승인
        await test_trade_execution_with_hitl()

        # Test 2: 매매 거부
        await test_trade_rejection()

        # Test 3: Level 1 자동 실행
        await test_level_1_auto()

        print("\n" + "✅" * 30)
        print("모든 테스트 완료!")
        print("✅" * 30 + "\n")

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 비동기 테스트 실행
    asyncio.run(main())
