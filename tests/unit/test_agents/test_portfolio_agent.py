"""
Portfolio Agent 단위 테스트

포트폴리오 수집 → 최적화 → 리밸런싱 → 요약 노드를 검증한다.
"""
from __future__ import annotations

from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from src.agents.portfolio import nodes as portfolio_nodes
from src.agents.portfolio.nodes import (
    collect_portfolio_node,
    optimize_allocation_node,
    rebalance_plan_node,
    summary_node,
)
from src.services.portfolio_service import PortfolioSnapshot


@pytest.fixture
def base_state() -> dict:
    """포트폴리오 노드 공통 초기 상태."""
    return {
        "messages": [],
        "request_id": str(uuid4()),
        "user_id": "user-123",
        "portfolio_id": "portfolio-123",
        "automation_level": 2,
        "preferences": {},
        "agent_results": {},
    }


@pytest.mark.asyncio
async def test_collect_portfolio_node_populates_state(monkeypatch, base_state):
    """스냅샷을 불러와 포트폴리오 현황을 상태에 반영하는지 검증."""
    snapshot = PortfolioSnapshot(
        portfolio_data={
            "portfolio_id": "portfolio-123",
            "total_value": 120_000.0,
            "holdings": [
                {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.6, "value": 72_000.0},
                {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.4, "value": 48_000.0},
            ],
        },
        market_data={"beta": 0.95},
        profile={"risk_tolerance": "Aggressive"},
    )

    get_snapshot_mock = AsyncMock(return_value=snapshot)
    monkeypatch.setattr(
        portfolio_nodes.portfolio_service,
        "get_portfolio_snapshot",
        get_snapshot_mock,
    )

    result = await collect_portfolio_node(dict(base_state))

    get_snapshot_mock.assert_awaited_once()
    assert result["current_holdings"] == snapshot.portfolio_data["holdings"]
    assert result["total_value"] == pytest.approx(120_000.0)
    assert result["risk_profile"] == "aggressive"  # profile에서 추론된 값 소문자화
    assert result["portfolio_snapshot"]["portfolio_data"]["portfolio_id"] == "portfolio-123"


@pytest.mark.asyncio
async def test_collect_portfolio_node_syncs_when_snapshot_empty(monkeypatch, base_state):
    """보유 종목이 없을 때 KIS 동기화 결과를 재사용하는지 확인."""
    empty_snapshot = PortfolioSnapshot(
        portfolio_data={"portfolio_id": "portfolio-123", "total_value": 0.0, "holdings": []},
        market_data={},
        profile={},
    )
    synced_snapshot = PortfolioSnapshot(
        portfolio_data={
            "portfolio_id": "portfolio-123",
            "total_value": 80_000.0,
            "holdings": [
                {"stock_code": "035420", "stock_name": "NAVER", "weight": 1.0, "value": 80_000.0},
            ],
        },
        market_data={"volatility": 0.18},
        profile={"risk_tolerance": "Moderate"},
    )

    monkeypatch.setattr(
        portfolio_nodes.portfolio_service,
        "get_portfolio_snapshot",
        AsyncMock(return_value=empty_snapshot),
    )
    sync_mock = AsyncMock(return_value=synced_snapshot)
    monkeypatch.setattr(
        portfolio_nodes.portfolio_service,
        "sync_with_kis",
        sync_mock,
    )

    result = await collect_portfolio_node(dict(base_state))

    sync_mock.assert_awaited_once()
    assert result["current_holdings"][0]["stock_code"] == "035420"
    assert result["total_value"] == pytest.approx(80_000.0)
    assert result["risk_profile"] == "moderate"
    assert result["portfolio_snapshot"]["portfolio_data"]["holdings"]


@pytest.mark.asyncio
async def test_optimize_allocation_node_updates_target(monkeypatch, base_state):
    """포트폴리오 최적화 결과가 상태에 반영되는지 테스트."""
    state = {
        **base_state,
        "risk_profile": "moderate",
        "current_holdings": [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.6, "sector": "IT", "value": 60_000.0},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.4, "sector": "IT", "value": 40_000.0},
        ],
        "total_value": 100_000.0,
        "strategy_result": {"sector_overweights": {"IT": 0.1}},
    }

    proposed = [
        {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.5, "value": 50_000.0},
        {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.3, "value": 30_000.0},
    ]
    metrics = {
        "expected_return": 0.14,
        "expected_volatility": 0.18,
        "sharpe_ratio": 0.78,
        "rationale": "IT 중심 초과 수익 기대",
    }

    monkeypatch.setattr(
        portfolio_nodes.portfolio_optimizer,
        "calculate_target_allocation",
        AsyncMock(return_value=(proposed, metrics)),
    )

    result = await optimize_allocation_node(state)

    assert result["proposed_allocation"] == proposed
    assert result["expected_return"] == pytest.approx(0.14)
    assert result["rationale"] == "IT 중심 초과 수익 기대"


@pytest.mark.asyncio
async def test_rebalance_plan_node_creates_trades(base_state):
    """현재/목표 비중 차이를 기반으로 리밸런싱 지시와 HITL 여부를 판단한다."""
    state = {
        **base_state,
        "current_holdings": [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.7},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.3},
        ],
        "proposed_allocation": [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.5},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.25},
            {"stock_code": "CASH", "stock_name": "예수금", "weight": 0.25},
        ],
        "total_value": 200_000.0,
        "automation_level": 2,
    }

    result = await rebalance_plan_node(state)

    assert result["rebalancing_needed"] is True
    assert result["hitl_required"] is True  # 편차 0.2로 승인 필요
    trades = result["trades_required"]
    assert any(trade["stock_code"] == "005930" and trade["action"] == "SELL" for trade in trades)
    assert any(trade["stock_code"] == "CASH" and trade["action"] == "BUY" for trade in trades) is False


@pytest.mark.asyncio
async def test_summary_node_returns_report(base_state):
    """요약 노드가 사용자 보고서와 messages를 생성하는지 검증."""
    state = {
        **base_state,
        "portfolio_id": "portfolio-123",
        "current_holdings": [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.6},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.4},
        ],
        "proposed_allocation": [
            {"stock_code": "005930", "stock_name": "삼성전자", "weight": 0.55},
            {"stock_code": "000660", "stock_name": "SK하이닉스", "weight": 0.30},
            {"stock_code": "CASH", "stock_name": "예수금", "weight": 0.15},
        ],
        "expected_return": 0.12,
        "expected_volatility": 0.17,
        "sharpe_ratio": 0.8,
        "trades_required": [
            {"action": "BUY", "stock_code": "000660", "stock_name": "SK하이닉스", "amount": 30_000.0, "weight_delta": 0.1}
        ],
        "rebalancing_needed": True,
        "hitl_required": True,
        "risk_profile": "moderate",
        "messages": [AIMessage(content="이전 메시지")],
    }

    result = await summary_node(state)

    assert "summary" in result
    assert "예상 수익률" in result["summary"]
    assert result["agent_results"]["portfolio"]["rebalancing_needed"] is True
    assert isinstance(result["messages"][-1], AIMessage)
