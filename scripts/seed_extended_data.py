#!/usr/bin/env python3
"""
Mock 데이터 보강 스크립트

확장 내용:
- 종목: 5개 → 10개
- 주가 데이터: 30일 → 90일
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, date
from decimal import Decimal
import random

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from src.models.database import engine
from src.models.stock import Stock, StockPrice


# 추가할 5개 종목
ADDITIONAL_STOCKS = [
    {
        "stock_code": "373220",
        "stock_name": "LG에너지솔루션",
        "market": "KOSPI",
        "sector": "2차전지",
        "industry": "전기장비",
        "listing_date": date(2022, 1, 27),
        "listing_shares": 230000000,
        "par_value": Decimal("500"),
    },
    {
        "stock_code": "207940",
        "stock_name": "삼성바이오로직스",
        "market": "KOSPI",
        "sector": "바이오",
        "industry": "의약품",
        "listing_date": date(2016, 11, 10),
        "listing_shares": 60000000,
        "par_value": Decimal("500"),
    },
    {
        "stock_code": "005490",
        "stock_name": "POSCO홀딩스",
        "market": "KOSPI",
        "sector": "철강",
        "industry": "철강",
        "listing_date": date(1988, 12, 29),
        "listing_shares": 88000000,
        "par_value": Decimal("5000"),
    },
    {
        "stock_code": "051910",
        "stock_name": "LG화학",
        "market": "KOSPI",
        "sector": "화학",
        "industry": "화학",
        "listing_date": date(2001, 4, 3),
        "listing_shares": 70000000,
        "par_value": Decimal("5000"),
    },
    {
        "stock_code": "003550",
        "stock_name": "LG",
        "market": "KOSPI",
        "sector": "전기전자",
        "industry": "통신장비",
        "listing_date": date(1976, 6, 29),
        "listing_shares": 230000000,
        "par_value": Decimal("500"),
    },
]


def add_new_stocks(session: Session):
    """새로운 종목 추가"""
    print("1. 새 종목 추가 중...")

    added_count = 0

    for stock_data in ADDITIONAL_STOCKS:
        # 이미 존재하는지 확인
        existing = session.query(Stock).filter_by(stock_code=stock_data["stock_code"]).first()

        if existing:
            print(f"  ✓ {stock_data['stock_name']} 이미 존재 (스킵)")
            continue

        # KIS API 필드 추가 (임의 데이터)
        stock_data["market_cap"] = stock_data["listing_shares"] * random.randint(50000, 500000)
        stock_data["week52_high"] = Decimal(str(random.randint(300000, 800000)))
        stock_data["week52_low"] = Decimal(str(random.randint(200000, 400000)))
        stock_data["dividend_yield"] = Decimal(str(round(random.uniform(0.01, 0.03), 4)))
        stock_data["is_managed"] = "N"
        stock_data["status"] = "active"

        stock = Stock(**stock_data)
        session.add(stock)
        added_count += 1

        print(f"  ✓ {stock_data['stock_name']} ({stock_data['stock_code']}) 추가")

    session.commit()
    print(f"  → {added_count}개 종목 추가 완료\n")


def generate_price_data(stock_code: str, days: int = 90) -> list:
    """주가 데이터 생성 (랜덤 워크)"""
    # 기본 가격 설정
    base_prices = {
        "005930": 76000,   # 삼성전자
        "000660": 123000,  # SK하이닉스
        "035420": 195000,  # NAVER
        "005380": 242000,  # 현대차
        "000270": 90000,   # 기아
        "373220": 450000,  # LG에너지솔루션
        "207940": 780000,  # 삼성바이오로직스
        "005490": 390000,  # POSCO홀딩스
        "051910": 480000,  # LG화학
        "003550": 85000,   # LG
    }

    base_price = base_prices.get(stock_code, 100000)

    price_data = []
    current_price = base_price
    start_date = datetime.now() - timedelta(days=days)

    for i in range(days):
        trade_date = (start_date + timedelta(days=i)).date()

        # 주말 건너뛰기
        if trade_date.weekday() >= 5:
            continue

        # 일일 변동률 (-3% ~ +3%)
        daily_change = random.uniform(-0.03, 0.03)
        open_price = current_price * (1 + random.uniform(-0.01, 0.01))
        close_price = current_price * (1 + daily_change)
        high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.02))
        low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.02))

        # 거래량 (랜덤)
        volume = random.randint(1000000, 20000000)
        trading_value = volume * close_price

        # 조정 가격 (단순화: 종가와 동일)
        adjusted_close = close_price

        # 변동
        change_amount = close_price - current_price
        change_rate = daily_change

        price_record = {
            "stock_code": stock_code,
            "date": trade_date,
            "open_price": Decimal(str(round(open_price, 2))),
            "high_price": Decimal(str(round(high_price, 2))),
            "low_price": Decimal(str(round(low_price, 2))),
            "close_price": Decimal(str(round(close_price, 2))),
            "volume": volume,
            "trading_value": Decimal(str(round(trading_value, 2))),
            "adjusted_close": Decimal(str(round(adjusted_close, 2))),
            "change_amount": Decimal(str(round(change_amount, 2))),
            "change_rate": Decimal(str(round(change_rate, 6))),
        }

        price_data.append(price_record)

        # 다음 날 기준 가격 업데이트
        current_price = close_price

    return price_data


def extend_price_data(session: Session):
    """주가 데이터 확장 (90일)"""
    print("2. 주가 데이터 확장 중 (90일)...")

    stocks = session.query(Stock).all()

    total_added = 0

    for stock in stocks:
        # 기존 데이터 삭제 (재생성)
        session.query(StockPrice).filter_by(stock_code=stock.stock_code).delete()

        # 90일 데이터 생성
        price_records = generate_price_data(stock.stock_code, days=90)

        for record in price_records:
            price = StockPrice(**record)
            session.add(price)

        total_added += len(price_records)

        print(f"  ✓ {stock.stock_name}: {len(price_records)}일 데이터 생성")

    session.commit()
    print(f"  → 총 {total_added}건 주가 데이터 생성 완료\n")


def verify_data(session: Session):
    """데이터 검증"""
    print("3. 데이터 검증 중...")

    stock_count = session.query(Stock).count()
    price_count = session.query(StockPrice).count()

    print(f"  ✓ 종목: {stock_count}개")
    print(f"  ✓ 주가 데이터: {price_count}건")

    # 종목별 데이터 확인
    stocks = session.query(Stock).all()
    for stock in stocks:
        price_days = session.query(StockPrice).filter_by(stock_code=stock.stock_code).count()
        print(f"    - {stock.stock_name} ({stock.stock_code}): {price_days}일")

    print()


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("Mock 데이터 보강 (10개 종목, 90일)")
    print("=" * 60 + "\n")

    try:
        with Session(engine) as session:
            # 1. 새 종목 추가
            add_new_stocks(session)

            # 2. 주가 데이터 확장 (90일)
            extend_price_data(session)

            # 3. 검증
            verify_data(session)

        print("=" * 60)
        print("✅ Mock 데이터 보강 완료!")
        print("=" * 60)
        print("\n다음 단계:")
        print("  1. python scripts/demo_scenarios.py  # 데모 시나리오 실행")
        print("  2. python -m pytest tests/  # 테스트 실행")
        print()

    except Exception as e:
        print(f"\n❌ 데이터 생성 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
