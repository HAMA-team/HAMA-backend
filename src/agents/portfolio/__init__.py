"""
Portfolio Agent Module - 포트폴리오 구축 및 최적화 (Langgraph 서브그래프)

⚠️ DEPRECATED: 이 모듈은 곧 제거될 예정입니다.
새로운 아키텍처에서는 다음 tools로 대체됩니다:
- optimize_portfolio tool
- rebalance_portfolio tool
"""
import warnings

warnings.warn(
    "Portfolio Agent는 deprecated되었습니다. "
    "src/subgraphs/tools/portfolio_tools.py의 tools로 마이그레이션하세요.",
    DeprecationWarning,
    stacklevel=2
)

from .graph import build_portfolio_subgraph

# Compiled Agent로 export (Supervisor 패턴 사용)
# checkpointer는 Supervisor에서 자동 상속되므로 생략
portfolio_agent = build_portfolio_subgraph().compile(
    name="portfolio_agent",
    interrupt_before=["approval_rebalance"]  # 자동화 레벨 2+ 시 승인 필요
)

__all__ = ["portfolio_agent"]
