"""Portfolio Agent Module - 포트폴리오 구축 및 최적화 (Langgraph 서브그래프)"""

from .graph import build_portfolio_subgraph
from langgraph.checkpoint.memory import MemorySaver

# Compiled Agent로 export (Supervisor 패턴 사용)
portfolio_agent = build_portfolio_subgraph().compile(
    name="portfolio_agent",
    checkpointer=MemorySaver(),
    interrupt_before=["approval_rebalance"]  # 자동화 레벨 2+ 시 승인 필요
)

__all__ = ["portfolio_agent"]
