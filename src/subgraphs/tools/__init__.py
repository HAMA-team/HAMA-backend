"""
Supervisor Tools 통합 모듈

Supervisor가 직접 사용할 수 있는 모든 tools를 통합하여 제공합니다.
"""
from typing import List

from langchain_core.tools import BaseTool

from src.subgraphs.tools.kis_tools import get_kis_tools
from src.subgraphs.tools.ticker_tools import get_ticker_tools
from src.subgraphs.tools.risk_tools import get_risk_tools
from src.subgraphs.tools.portfolio_tools import get_portfolio_tools
from src.subgraphs.tools.report_tools import get_report_tools
from src.subgraphs.tools.trading_tools import get_trading_tools


def get_all_tools() -> List[BaseTool]:
    """
    Supervisor가 사용할 모든 tools를 반환합니다.

    포함된 tools:
    - KIS Tools (3개): get_current_price, get_account_balance, get_portfolio_positions
    - Ticker Tools (1개): resolve_ticker
    - Risk Tools (1개): calculate_portfolio_risk
    - Portfolio Tools (2개): optimize_portfolio, rebalance_portfolio
    - Report Tools (1개): generate_investment_report
    - Trading Tools (1개): request_trade (HITL 패턴)

    총 10개 tools (Handoff tools는 create_supervisor가 자동 생성)

    Returns:
        List[BaseTool]: 모든 tools의 리스트
    """
    all_tools = []

    # KIS Tools
    all_tools.extend(get_kis_tools())

    # Ticker Tools
    all_tools.extend(get_ticker_tools())

    # Risk Tools
    all_tools.extend(get_risk_tools())

    # Portfolio Tools
    all_tools.extend(get_portfolio_tools())

    # Report Tools
    all_tools.extend(get_report_tools())

    # Trading Tools (HITL 패턴)
    all_tools.extend(get_trading_tools())

    return all_tools


__all__ = [
    "get_all_tools",
    "get_kis_tools",
    "get_ticker_tools",
    "get_risk_tools",
    "get_portfolio_tools",
    "get_report_tools",
    "get_trading_tools",
]
