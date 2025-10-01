"""
Stock-related database models
"""
from sqlalchemy import Column, String, Integer, TIMESTAMP, Date, DECIMAL, BigInteger, Text, JSON, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from src.models.database import Base


class Stock(Base):
    """종목 기본 정보"""
    __tablename__ = "stocks"

    stock_code = Column(String(20), primary_key=True)
    stock_name = Column(String(200), nullable=False)
    stock_name_en = Column(String(200))

    # 분류
    market = Column(String(20), nullable=False, index=True)  # KOSPI, KOSDAQ, KONEX
    sector = Column(String(100), index=True)
    industry = Column(String(100))

    # 기본 정보
    listing_date = Column(Date)
    listing_shares = Column(BigInteger)
    par_value = Column(DECIMAL(10, 2))

    # 상태
    status = Column(String(20), default="active", index=True)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class StockPrice(Base):
    """주가 데이터 (시계열)"""
    __tablename__ = "stock_prices"

    price_id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)

    # 가격 데이터
    date = Column(Date, nullable=False, index=True)
    open_price = Column(DECIMAL(15, 2))
    high_price = Column(DECIMAL(15, 2))
    low_price = Column(DECIMAL(15, 2))
    close_price = Column(DECIMAL(15, 2), nullable=False)

    # 거래량
    volume = Column(BigInteger)
    trading_value = Column(DECIMAL(20, 2))

    # 조정 가격
    adjusted_close = Column(DECIMAL(15, 2))

    # 변동률
    change_amount = Column(DECIMAL(15, 2))
    change_rate = Column(DECIMAL(10, 6))

    created_at = Column(TIMESTAMP, server_default=func.now())


class FinancialStatement(Base):
    """재무제표"""
    __tablename__ = "financial_statements"

    statement_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_code = Column(String(20), nullable=False, index=True)

    # 기간
    fiscal_year = Column(Integer, nullable=False)
    fiscal_quarter = Column(Integer)
    report_type = Column(String(20), nullable=False)

    # 손익계산서
    revenue = Column(DECIMAL(20, 2))
    operating_profit = Column(DECIMAL(20, 2))
    net_profit = Column(DECIMAL(20, 2))

    # 재무상태표
    total_assets = Column(DECIMAL(20, 2))
    total_liabilities = Column(DECIMAL(20, 2))
    total_equity = Column(DECIMAL(20, 2))

    # 현금흐름표
    operating_cash_flow = Column(DECIMAL(20, 2))
    investing_cash_flow = Column(DECIMAL(20, 2))
    financing_cash_flow = Column(DECIMAL(20, 2))

    # 주요 지표
    eps = Column(DECIMAL(15, 4))
    bps = Column(DECIMAL(15, 4))
    per = Column(DECIMAL(10, 4))
    pbr = Column(DECIMAL(10, 4))
    roe = Column(DECIMAL(10, 6))
    roa = Column(DECIMAL(10, 6))
    debt_ratio = Column(DECIMAL(10, 6))

    # 원본 데이터
    raw_data = Column(JSON)

    created_at = Column(TIMESTAMP, server_default=func.now())


class Disclosure(Base):
    """공시 정보"""
    __tablename__ = "disclosures"

    disclosure_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_code = Column(String(20), nullable=False, index=True)

    # 공시 정보
    report_number = Column(String(50), unique=True, nullable=False)
    report_name = Column(String(500), nullable=False)
    report_type = Column(String(100))

    # 내용
    summary = Column(Text)
    content = Column(Text)

    # 메타데이터
    submit_date = Column(Date, nullable=False, index=True)
    receipt_number = Column(String(50))

    # 중요도 (AI 평가)
    importance_score = Column(DECIMAL(3, 2))

    # 임베딩 ID (Vector DB)
    embedding_id = Column(String(100))

    created_at = Column(TIMESTAMP, server_default=func.now())


class News(Base):
    """뉴스"""
    __tablename__ = "news"

    news_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # 기본 정보
    title = Column(String(500), nullable=False)
    content = Column(Text)
    summary = Column(Text)
    url = Column(String(1000))
    source = Column(String(100))

    # 관련 종목
    related_stocks = Column(ARRAY(String), index=True)

    # 감정 분석 (Phase 3)
    sentiment_score = Column(DECIMAL(3, 2))

    published_at = Column(TIMESTAMP, nullable=False, index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # 임베딩 ID
    embedding_id = Column(String(100))