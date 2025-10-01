"""
Portfolio-related database models
"""
from sqlalchemy import Column, String, Integer, TIMESTAMP, DECIMAL, Date, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from src.models.database import Base


class Portfolio(Base):
    """포트폴리오"""
    __tablename__ = "portfolios"

    portfolio_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # 포트폴리오 정보
    portfolio_name = Column(String(200), nullable=False, default="My Portfolio")
    strategy_type = Column(String(50))

    # 자산 정보
    total_value = Column(DECIMAL(15, 2), nullable=False, default=0)
    cash_balance = Column(DECIMAL(15, 2), nullable=False, default=0)
    invested_amount = Column(DECIMAL(15, 2), nullable=False, default=0)

    # 성과 지표
    total_return = Column(DECIMAL(10, 6))
    annual_return = Column(DECIMAL(10, 6))
    sharpe_ratio = Column(DECIMAL(10, 6))
    max_drawdown = Column(DECIMAL(10, 6))

    # 리스크 지표
    volatility = Column(DECIMAL(10, 6))
    var_95 = Column(DECIMAL(10, 6))

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), index=True)
    last_rebalanced_at = Column(TIMESTAMP)


class Position(Base):
    """포트폴리오 포지션 (보유 종목)"""
    __tablename__ = "positions"

    position_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    stock_code = Column(String(20), nullable=False, index=True)

    # 보유 정보
    quantity = Column(Integer, nullable=False)
    average_price = Column(DECIMAL(15, 2), nullable=False)
    current_price = Column(DECIMAL(15, 2))

    # 계산 필드
    market_value = Column(DECIMAL(15, 2))
    unrealized_pnl = Column(DECIMAL(15, 2))
    unrealized_pnl_rate = Column(DECIMAL(10, 6))

    # 비중
    weight = Column(DECIMAL(5, 4))

    first_purchased_at = Column(TIMESTAMP)
    last_updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Transaction(Base):
    """거래 내역"""
    __tablename__ = "transactions"

    transaction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    stock_code = Column(String(20), nullable=False, index=True)

    # 거래 정보
    transaction_type = Column(String(10), nullable=False, index=True)  # BUY, SELL
    quantity = Column(Integer, nullable=False)
    price = Column(DECIMAL(15, 2), nullable=False)
    total_amount = Column(DECIMAL(15, 2), nullable=False)
    fee = Column(DECIMAL(15, 2), default=0)
    tax = Column(DECIMAL(15, 2), default=0)

    # 주문 정보 (Phase 2)
    order_id = Column(UUID(as_uuid=True))
    order_status = Column(String(20))

    # AI 추천 추적
    signal_id = Column(UUID(as_uuid=True))

    executed_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    notes = Column(Text)


class PortfolioSnapshot(Base):
    """포트폴리오 히스토리 (일별 스냅샷)"""
    __tablename__ = "portfolio_snapshots"

    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    snapshot_date = Column(Date, nullable=False, index=True)

    # 자산 정보
    total_value = Column(DECIMAL(15, 2), nullable=False)
    cash_balance = Column(DECIMAL(15, 2), nullable=False)
    invested_amount = Column(DECIMAL(15, 2), nullable=False)

    # 수익률
    daily_return = Column(DECIMAL(10, 6))
    cumulative_return = Column(DECIMAL(10, 6))

    # 포지션 상세 (JSON)
    positions_detail = Column(JSON)

    created_at = Column(TIMESTAMP, server_default=func.now())