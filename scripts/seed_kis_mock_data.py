#!/usr/bin/env python3
"""
KIS API Mock 데이터 생성 스크립트

생성 데이터:
- 실시간 호가 (10단계)
- 실시간 현재가
- 주문 시뮬레이션 데이터
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
import random

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from src.models.database import engine
from src.models.stock import StockQuote, RealtimePrice, Stock


def generate_quote_data(stock_code: str, base_price: float) -> dict:
    """호가 데이터 생성 (10단계)"""
    # 호가 단위 결정 (가격대별로 다름)
    if base_price < 1000:
        tick = 1
    elif base_price < 5000:
        tick = 5
    elif base_price < 10000:
        tick = 10
    elif base_price < 50000:
        tick = 50
    elif base_price < 100000:
        tick = 100
    else:
        tick = 500

    quote_data = {
        "stock_code": stock_code,
        "quote_time": datetime.now(),
        "total_ask_volume": 0,
        "total_bid_volume": 0,
    }

    # 매도 호가 생성 (현재가보다 높음)
    for i in range(1, 11):
        price = base_price + (tick * i)
        volume = random.randint(100, 10000)

        quote_data[f"ask_price_{i}"] = Decimal(str(price))
        quote_data[f"ask_volume_{i}"] = volume
        quote_data["total_ask_volume"] += volume

    # 매수 호가 생성 (현재가보다 낮음)
    for i in range(1, 11):
        price = base_price - (tick * i)
        volume = random.randint(100, 10000)

        quote_data[f"bid_price_{i}"] = Decimal(str(price))
        quote_data[f"bid_volume_{i}"] = volume
        quote_data["total_bid_volume"] += volume

    return quote_data


def generate_realtime_price(stock: Stock, base_price: float) -> dict:
    """실시간 현재가 데이터 생성"""
    # 등락률 생성 (-5% ~ +5%)
    change_rate = random.uniform(-0.05, 0.05)
    prev_close = base_price
    current_price = base_price * (1 + change_rate)

    # 장중 가격 변동
    open_price = prev_close * (1 + random.uniform(-0.02, 0.02))
    high_price = max(current_price, open_price) * (1 + random.uniform(0, 0.03))
    low_price = min(current_price, open_price) * (1 - random.uniform(0, 0.03))

    # 변동 부호 결정
    if change_rate > 0:
        change_sign = "2"  # 상승
    elif change_rate < 0:
        change_sign = "5"  # 하락
    else:
        change_sign = "3"  # 보합

    # 거래량 생성
    volume = random.randint(1000000, 50000000)
    trading_value = int(current_price * volume)

    # 시가총액 계산 (상장주식수 * 현재가)
    market_cap = int(stock.listing_shares * current_price) if stock.listing_shares else None

    realtime_data = {
        "stock_code": stock.stock_code,
        "timestamp": datetime.now(),
        "current_price": Decimal(str(round(current_price, 2))),
        "open_price": Decimal(str(round(open_price, 2))),
        "high_price": Decimal(str(round(high_price, 2))),
        "low_price": Decimal(str(round(low_price, 2))),
        "prev_close": Decimal(str(round(prev_close, 2))),
        "change_amount": Decimal(str(round(current_price - prev_close, 2))),
        "change_rate": Decimal(str(round(change_rate, 6))),
        "change_sign": change_sign,
        "volume": volume,
        "trading_value": trading_value,
        "volume_turnover_ratio": Decimal(str(round(random.uniform(0.5, 5.0), 6))),
        "market_cap": market_cap,
        "week52_high": Decimal(str(round(current_price * 1.3, 2))),
        "week52_low": Decimal(str(round(current_price * 0.7, 2))),
        "per": Decimal(str(round(random.uniform(5.0, 30.0), 4))),
        "pbr": Decimal(str(round(random.uniform(0.5, 3.0), 4))),
        "best_ask_price": Decimal(str(round(current_price + 50, 2))),
        "best_bid_price": Decimal(str(round(current_price - 50, 2))),
    }

    return realtime_data


def seed_kis_mock_data():
    """KIS API Mock 데이터 삽입"""
    print("=" * 60)
    print("KIS API Mock 데이터 생성")
    print("=" * 60 + "\n")

    with Session(engine) as session:
        # 기존 종목 조회
        stocks = session.query(Stock).all()

        if not stocks:
            print("❌ 종목 데이터가 없습니다. 먼저 seed_data.py를 실행하세요.")
            return

        print(f"✓ {len(stocks)}개 종목 발견\n")

        quote_count = 0
        price_count = 0

        for stock in stocks:
            # 기본 가격 설정 (종목별로 다르게)
            base_prices = {
                "005930": 76000,  # 삼성전자
                "000660": 123000,  # SK하이닉스
                "035420": 195000,  # NAVER
                "005380": 242000,  # 현대차
                "000270": 90000,   # 기아
            }

            base_price = base_prices.get(stock.stock_code, 50000)

            # 호가 데이터 생성
            quote_data = generate_quote_data(stock.stock_code, base_price)
            quote = StockQuote(**quote_data)
            session.add(quote)
            quote_count += 1

            # 실시간 현재가 데이터 생성
            realtime_data = generate_realtime_price(stock, base_price)
            realtime = RealtimePrice(**realtime_data)
            session.add(realtime)
            price_count += 1

            print(f"  ✓ {stock.stock_name} ({stock.stock_code})")
            print(f"     - 호가: 매도 {quote_data['total_ask_volume']:,}주 / 매수 {quote_data['total_bid_volume']:,}주")
            print(f"     - 현재가: {realtime_data['current_price']:,}원 ({realtime_data['change_rate']:+.2%})")

        # 커밋
        session.commit()

        print(f"\n" + "=" * 60)
        print(f"✅ Mock 데이터 생성 완료!")
        print(f"=" * 60)
        print(f"  - 호가 데이터: {quote_count}건")
        print(f"  - 실시간 가격: {price_count}건")
        print()


def update_stock_kis_fields():
    """stocks 테이블의 KIS API 필드 업데이트"""
    print("\nstocks 테이블 KIS API 필드 업데이트 중...")

    with Session(engine) as session:
        stocks = session.query(Stock).all()

        for stock in stocks:
            # 52주 최고/최저가 생성 (임의값)
            base_price = 50000
            if stock.stock_code == "005930":
                base_price = 76000
            elif stock.stock_code == "000660":
                base_price = 123000
            elif stock.stock_code == "035420":
                base_price = 195000
            elif stock.stock_code == "005380":
                base_price = 242000
            elif stock.stock_code == "000270":
                base_price = 90000

            stock.week52_high = Decimal(str(int(base_price * 1.3)))
            stock.week52_low = Decimal(str(int(base_price * 0.7)))
            stock.dividend_yield = Decimal(str(round(random.uniform(0.01, 0.03), 4)))
            stock.market_cap = int(stock.listing_shares * base_price) if stock.listing_shares else None
            stock.is_managed = "N"

        session.commit()
        print(f"  ✓ {len(stocks)}개 종목 업데이트 완료\n")


def main():
    """메인 실행 함수"""
    try:
        # 1. stocks 테이블 KIS 필드 업데이트
        update_stock_kis_fields()

        # 2. 호가 및 실시간 가격 데이터 생성
        seed_kis_mock_data()

        print("다음 단계:")
        print("  1. python scripts/seed_extended_data.py  # 10개 종목, 90일 데이터 생성")
        print("  2. python -m pytest tests/  # 테스트 실행")
        print()

    except Exception as e:
        print(f"\n❌ 데이터 생성 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
