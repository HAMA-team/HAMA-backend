"""
Stock-related database models
"""
from sqlalchemy import Column, String, Integer, TIMESTAMP, Date, DECIMAL, BigInteger, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
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

    # KIS API 호환 필드 추가
    market_cap = Column(BigInteger)  # 시가총액
    week52_high = Column(DECIMAL(15, 2))  # 52주 최고가
    week52_low = Column(DECIMAL(15, 2))  # 52주 최저가
    dividend_yield = Column(DECIMAL(5, 4))  # 배당수익률
    is_managed = Column(String(1), default="N")  # 관리종목 여부 (Y/N)

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


class StockQuote(Base):
    """실시간 호가 정보 (KIS API 호환)"""
    __tablename__ = "stock_quotes"

    quote_id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)

    # 호가 시간
    quote_time = Column(TIMESTAMP, nullable=False, index=True)

    # 매도 호가 (10단계)
    ask_price_1 = Column(DECIMAL(15, 2))
    ask_price_2 = Column(DECIMAL(15, 2))
    ask_price_3 = Column(DECIMAL(15, 2))
    ask_price_4 = Column(DECIMAL(15, 2))
    ask_price_5 = Column(DECIMAL(15, 2))
    ask_price_6 = Column(DECIMAL(15, 2))
    ask_price_7 = Column(DECIMAL(15, 2))
    ask_price_8 = Column(DECIMAL(15, 2))
    ask_price_9 = Column(DECIMAL(15, 2))
    ask_price_10 = Column(DECIMAL(15, 2))

    # 매도 잔량 (10단계)
    ask_volume_1 = Column(BigInteger)
    ask_volume_2 = Column(BigInteger)
    ask_volume_3 = Column(BigInteger)
    ask_volume_4 = Column(BigInteger)
    ask_volume_5 = Column(BigInteger)
    ask_volume_6 = Column(BigInteger)
    ask_volume_7 = Column(BigInteger)
    ask_volume_8 = Column(BigInteger)
    ask_volume_9 = Column(BigInteger)
    ask_volume_10 = Column(BigInteger)

    # 매수 호가 (10단계)
    bid_price_1 = Column(DECIMAL(15, 2))
    bid_price_2 = Column(DECIMAL(15, 2))
    bid_price_3 = Column(DECIMAL(15, 2))
    bid_price_4 = Column(DECIMAL(15, 2))
    bid_price_5 = Column(DECIMAL(15, 2))
    bid_price_6 = Column(DECIMAL(15, 2))
    bid_price_7 = Column(DECIMAL(15, 2))
    bid_price_8 = Column(DECIMAL(15, 2))
    bid_price_9 = Column(DECIMAL(15, 2))
    bid_price_10 = Column(DECIMAL(15, 2))

    # 매수 잔량 (10단계)
    bid_volume_1 = Column(BigInteger)
    bid_volume_2 = Column(BigInteger)
    bid_volume_3 = Column(BigInteger)
    bid_volume_4 = Column(BigInteger)
    bid_volume_5 = Column(BigInteger)
    bid_volume_6 = Column(BigInteger)
    bid_volume_7 = Column(BigInteger)
    bid_volume_8 = Column(BigInteger)
    bid_volume_9 = Column(BigInteger)
    bid_volume_10 = Column(BigInteger)

    # 총 매도/매수 잔량
    total_ask_volume = Column(BigInteger)
    total_bid_volume = Column(BigInteger)

    created_at = Column(TIMESTAMP, server_default=func.now())


class RealtimePrice(Base):
    """실시간 현재가 정보 (KIS API 호환)"""
    __tablename__ = "realtime_prices"

    price_id = Column(BigInteger, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)

    # 시간 정보
    timestamp = Column(TIMESTAMP, nullable=False, index=True)

    # 가격 정보
    current_price = Column(DECIMAL(15, 2), nullable=False)
    open_price = Column(DECIMAL(15, 2))
    high_price = Column(DECIMAL(15, 2))
    low_price = Column(DECIMAL(15, 2))
    prev_close = Column(DECIMAL(15, 2))

    # 변동 정보
    change_amount = Column(DECIMAL(15, 2))
    change_rate = Column(DECIMAL(10, 6))
    change_sign = Column(String(1))  # 1:상한, 2:상승, 3:보합, 4:하한, 5:하락

    # 거래 정보
    volume = Column(BigInteger)
    trading_value = Column(BigInteger)
    volume_turnover_ratio = Column(DECIMAL(10, 6))

    # 시가총액
    market_cap = Column(BigInteger)

    # 52주 최고/최저
    week52_high = Column(DECIMAL(15, 2))
    week52_low = Column(DECIMAL(15, 2))

    # PER, PBR 등 (실시간 계산)
    per = Column(DECIMAL(10, 4))
    pbr = Column(DECIMAL(10, 4))

    # 호가 관련
    best_ask_price = Column(DECIMAL(15, 2))
    best_bid_price = Column(DECIMAL(15, 2))

    created_at = Column(TIMESTAMP, server_default=func.now())


class StockIndicator(Base):
    """일별 기술적 지표 스냅샷"""
    __tablename__ = "stock_indicators"

    indicator_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_code = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    # 이동평균
    ma5 = Column(DECIMAL(15, 4))
    ma20 = Column(DECIMAL(15, 4))
    ma60 = Column(DECIMAL(15, 4))
    ma120 = Column(DECIMAL(15, 4))

    # RSI
    rsi14 = Column(DECIMAL(10, 4))

    # MACD
    macd = Column(DECIMAL(15, 4))
    macd_signal = Column(DECIMAL(15, 4))
    macd_histogram = Column(DECIMAL(15, 4))

    # Bollinger Bands
    bollinger_upper = Column(DECIMAL(15, 4))
    bollinger_middle = Column(DECIMAL(15, 4))
    bollinger_lower = Column(DECIMAL(15, 4))

    # 거래량 분석
    current_volume = Column(BigInteger)
    average_volume = Column(BigInteger)
    volume_ratio = Column(DECIMAL(10, 4))
    is_high_volume = Column(String(1), default="N")

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
