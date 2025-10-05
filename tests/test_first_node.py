"""
첫 노드 수동 테스트
"""
import sys
sys.path.insert(0, "/Users/elaus/PycharmProjects/HAMA-backend")

from langchain_core.messages import HumanMessage
from src.agents.graph_master import analyze_intent_node

state = {
    "messages": [HumanMessage(content="삼성전자 분석하고 투자 전략 세워줘")],
    "user_id": "test_user",
    "conversation_id": "test",
    "automation_level": 2,
    "intent": None,
    "agents_to_call": [],
    "agents_called": [],
    "agent_results": {},
}

print("Testing analyze_intent_node...")
result = analyze_intent_node(state)
print(f"Result: {result}")
print("✅ Success")
