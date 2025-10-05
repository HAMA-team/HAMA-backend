"""
그래프 실행 디버깅
"""
import asyncio
import sys
sys.path.insert(0, "/Users/elaus/PycharmProjects/HAMA-backend")

from langchain_core.messages import HumanMessage
from src.agents.graph_master import build_graph


async def debug_graph():
    app = build_graph(automation_level=2)

    initial_state = {
        "messages": [HumanMessage(content="삼성전자 분석하고 투자 전략 세워줘")],
        "user_id": "test_user",
        "conversation_id": "test_debug",
        "automation_level": 2,
        "intent": None,
        "agents_to_call": [],
        "agents_called": [],
        "agent_results": {},
        "risk_status": "safe",
        "requires_approval": False,
        "approval_type": None,
        "final_response": None,
        "summary": None,
    }

    config = {"configurable": {"thread_id": "test_debug"}}

    # Stream events
    count = 0
    max_events = 20  # 최대 20개 이벤트만 확인

    async for event in app.astream(initial_state, config=config):
        node_name = list(event.keys())[0] if event else "unknown"
        print(f"{count}: {node_name}")

        count += 1
        if count >= max_events:
            print(f"\n⚠️  {max_events}개 이벤트 초과, 중단")
            break

    if count < max_events:
        print(f"\n✅ 완료 ({count}개 이벤트)")


if __name__ == "__main__":
    asyncio.run(debug_graph())
