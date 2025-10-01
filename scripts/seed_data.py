#!/usr/bin/env python3
"""
샘플 데이터 삽입 스크립트

테스트 및 데모용 샘플 데이터를 데이터베이스에 삽입합니다.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal

# src 디렉터리를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from src.models.database import engine, SessionLocal
from src.models.stock import Stock, StockPrice


def seed_stocks(db: Session):
    """주요 종목 데이터 삽입"""
    print("📊 Seeding stock data...")

    stocks = [
        Stock(
            stock_code="005930",
            stock_name="삼성전자",
            stock_name_en="Samsung Electronics",
            market="KOSPI",
            sector="반도체",
            industry="전자부품 제조",
            status="active"
        ),
        Stock(
            stock_code="000660",
            stock_name="SK하이닉스",
            stock_name_en="SK hynix",
            market="KOSPI",
            sector="반도체",
            industry="반도체 제조",
            status="active"
        ),
        Stock(
            stock_code="035420",
            stock_name="NAVER",
            stock_name_en="NAVER",
            market="KOSPI",
            sector="IT서비스",
            industry="인터넷 포털",
            status="active"
        ),
        Stock(
            stock_code="005380",
            stock_name="현대차",
            stock_name_en="Hyundai Motor",
            market="KOSPI",
            sector="자동차",
            industry="자동차 제조",
            status="active"
        ),
        Stock(
            stock_code="000270",
            stock_name="기아",
            stock_name_en="Kia",
            market="KOSPI",
            sector="자동차",
            industry="자동차 제조",
            status="active"
        ),
    ]

    for stock in stocks:
        db.add(stock)
        print(f"  ✓ {stock.stock_name} ({stock.stock_code})")

    db.commit()
    print(f"✅ Inserted {len(stocks)} stocks\n")


def seed_stock_prices(db: Session):
    """주가 데이터 삽입 (최근 30일)"""
    print("💹 Seeding stock price data...")

    # 샘플 주가 데이터
    price_data = {
        "005930": {"base": 76000, "volatility": 0.02},  # 삼성전자
        "000660": {"base": 145000, "volatility": 0.03},  # SK하이닉스
        "035420": {"base": 220000, "volatility": 0.025},  # NAVER
        "005380": {"base": 240000, "volatility": 0.02},  # 현대차
        "000270": {"base": 105000, "volatility": 0.025},  # 기아
    }

    today = datetime.now().date()
    count = 0

    for stock_code, data in price_data.items():
        base_price = data["base"]
        volatility = data["volatility"]

        for i in range(30, 0, -1):
            date = today - timedelta(days=i)

            # 간단한 랜덤 워크 시뮬레이션
            import random
            change = random.uniform(-volatility, volatility)
            price = base_price * (1 + change)

            stock_price = StockPrice(
                stock_code=stock_code,
                date=date,
                open_price=Decimal(str(round(price * 0.99, 2))),
                high_price=Decimal(str(round(price * 1.02, 2))),
                low_price=Decimal(str(round(price * 0.98, 2))),
                close_price=Decimal(str(round(price, 2))),
                volume=random.randint(5000000, 15000000),
                trading_value=Decimal(str(round(price * random.randint(5000000, 15000000), 2))),
                adjusted_close=Decimal(str(round(price, 2))),
                change_amount=Decimal(str(round(price * change, 2))),
                change_rate=Decimal(str(round(change, 6)))
            )
            db.add(stock_price)
            count += 1

    db.commit()
    print(f"✅ Inserted {count} price records\n")


def main():
    """메인 함수"""
    print("=" * 60)
    print("HAMA Backend - Seed Sample Data")
    print("=" * 60)
    print()

    db = SessionLocal()

    try:
        # 종목 데이터 삽입
        seed_stocks(db)

        # 주가 데이터 삽입
        seed_stock_prices(db)

        print("=" * 60)
        print("✨ Sample data seeded successfully!")
        print("=" * 60)
        print()
        print("You can now:")
        print("  • Query stocks: SELECT * FROM stocks;")
        print("  • Query prices: SELECT * FROM stock_prices LIMIT 10;")
        print("  • Start the API: python -m src.main")

    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
