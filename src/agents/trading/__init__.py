"""
Trading Agent Module - 매매 실행 (Langgraph 서브그래프)
"""
from .graph import build_trading_subgraph
from langgraph.checkpoint.memory import MemorySaver

# Compiled Agent로 export (Supervisor 패턴 사용)
trading_agent = build_trading_subgraph().compile(
    name="trading_agent",
    checkpointer=MemorySaver(),
    interrupt_before=["approval_trade"]  # 자동화 레벨 2+ 시 승인 필요
)

__all__ = ["trading_agent"]
