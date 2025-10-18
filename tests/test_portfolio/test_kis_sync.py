import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.models.database import Base, SessionLocal, engine
from src.models import portfolio as portfolio_models
from src.services.portfolio_service import portfolio_service


def _reset_portfolio_tables():
    """테스트마다 포트폴리오 관련 테이블을 깨끗하게 초기화합니다."""
    Base.metadata.drop_all(bind=engine)
    # 포트폴리오 관련 모델이 metadata에 등록되어 있도록 import 유지
    Base.metadata.create_all(bind=engine)


@pytest.mark.asyncio
async def test_sync_with_kis_updates_portfolio(monkeypatch):
    _reset_portfolio_tables()

    portfolio_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # 테스트용 포트폴리오 생성
    with SessionLocal() as session:
        portfolio = portfolio_models.Portfolio(
            portfolio_id=portfolio_id,
            user_id=user_id,
            portfolio_name="테스트 포트폴리오",
            strategy_type="test",
            total_value=Decimal("0"),
            cash_balance=Decimal("0"),
            invested_amount=Decimal("0"),
        )
        session.add(portfolio)
        session.commit()

    # KIS API 응답 모킹
    kis_balance = {
        "total_assets": 1_000_000,
        "cash_balance": 200_000,
        "stocks": [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "quantity": 10,
                "avg_price": 50_000,
                "current_price": 60_000,
                "eval_amount": 600_000,
                "profit_loss": 100_000,
                "profit_rate": 0.2,
            },
        ],
    }

    async_mock = AsyncMock(return_value=kis_balance)
    monkeypatch.setattr(
        "src.services.kis_service.kis_service.get_account_balance",
        async_mock,
    )

    snapshot = await portfolio_service.sync_with_kis(portfolio_id=str(portfolio_id))

    assert snapshot is not None
    assert snapshot.portfolio_data["data_source"] == "kis_api"
    assert snapshot.portfolio_data["total_value"] == pytest.approx(kis_balance["total_assets"])
    assert snapshot.portfolio_data["cash_balance"] == pytest.approx(kis_balance["cash_balance"])

    with SessionLocal() as session:
        portfolio = session.query(portfolio_models.Portfolio).filter_by(portfolio_id=portfolio_id).one()
        assert float(portfolio.total_value) == pytest.approx(kis_balance["total_assets"])
        assert float(portfolio.cash_balance) == pytest.approx(kis_balance["cash_balance"])

        positions = session.query(portfolio_models.Position).filter_by(portfolio_id=portfolio_id).all()
        assert len(positions) == 1

        position = positions[0]
        assert position.stock_code == "005930"
        assert position.quantity == kis_balance["stocks"][0]["quantity"]
        assert float(position.market_value) == pytest.approx(kis_balance["stocks"][0]["eval_amount"])
        assert float(position.current_price) == pytest.approx(kis_balance["stocks"][0]["current_price"])
        assert float(position.weight) == pytest.approx((kis_balance["stocks"][0]["eval_amount"]) / kis_balance["total_assets"])

