"""
그래프 구조 확인
"""
import sys
sys.path.insert(0, "/Users/elaus/PycharmProjects/HAMA-backend")

from src.agents.graph_master import build_graph

print("Building graph...")
app = build_graph(automation_level=2)

print(f"✅ Graph built successfully")
print(f"Nodes: {list(app.nodes.keys())}")
print(f"Entry point: {app.entry_point}")

# 그래프 구조 시각화
print("\nGraph structure:")
for node_name in app.nodes.keys():
    print(f"  - {node_name}")