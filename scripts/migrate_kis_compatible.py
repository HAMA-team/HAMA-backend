#!/usr/bin/env python3
"""
KIS API 호환 데이터 모델 마이그레이션 스크립트

새로 추가된 테이블:
- stock_quotes (실시간 호가)
- realtime_prices (실시간 현재가)
- orders (주문 관리)

기존 테이블 확장:
- stocks 테이블에 KIS API 필드 추가
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.models.database import engine, Base
from src.models.stock import Stock, StockPrice, FinancialStatement, Disclosure, News, StockQuote, RealtimePrice
from src.models.portfolio import Portfolio, Position, Order, Transaction, PortfolioSnapshot
from src.models.agent import (
    ResearchReport, TradingSignal, RiskAssessment,
    ApprovalRequest, UserDecision, AgentLog, Alert
)
from src.models.user import User, UserProfile, UserPreference


def check_column_exists(table_name: str, column_name: str) -> bool:
    """컬럼이 이미 존재하는지 확인"""
    with engine.connect() as conn:
        result = conn.execute(text(f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='{table_name}' AND column_name='{column_name}'
        """))
        return result.fetchone() is not None


def check_table_exists(table_name: str) -> bool:
    """테이블이 이미 존재하는지 확인"""
    with engine.connect() as conn:
        result = conn.execute(text(f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name='{table_name}'
        """))
        return result.fetchone() is not None


def add_column_if_not_exists(table_name: str, column_def: str):
    """컬럼이 없으면 추가"""
    column_name = column_def.split()[0]

    if check_column_exists(table_name, column_name):
        print(f"   ✓ 컬럼 '{column_name}' 이미 존재 (스킵)")
        return

    with engine.connect() as conn:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_def}"))
        conn.commit()
        print(f"   ✓ 컬럼 '{column_name}' 추가 완료")


def migrate_stocks_table():
    """stocks 테이블에 KIS API 호환 필드 추가"""
    print("\n1. stocks 테이블 마이그레이션...")

    if not check_table_exists("stocks"):
        print("   ✗ stocks 테이블이 존재하지 않습니다. 먼저 init_db.py를 실행하세요.")
        return False

    # KIS API 호환 필드 추가
    columns_to_add = [
        "market_cap BIGINT",
        "week52_high DECIMAL(15, 2)",
        "week52_low DECIMAL(15, 2)",
        "dividend_yield DECIMAL(5, 4)",
        "is_managed VARCHAR(1) DEFAULT 'N'"
    ]

    for column_def in columns_to_add:
        add_column_if_not_exists("stocks", column_def)

    print("   ✓ stocks 테이블 마이그레이션 완료\n")
    return True


def create_new_tables():
    """새로운 테이블 생성"""
    print("2. 새 테이블 생성...")

    tables_to_create = {
        "stock_quotes": StockQuote,
        "realtime_prices": RealtimePrice,
        "orders": Order
    }

    created_count = 0
    skipped_count = 0

    for table_name, model in tables_to_create.items():
        if check_table_exists(table_name):
            print(f"   ✓ 테이블 '{table_name}' 이미 존재 (스킵)")
            skipped_count += 1
        else:
            model.__table__.create(engine)
            print(f"   ✓ 테이블 '{table_name}' 생성 완료")
            created_count += 1

    print(f"\n   총 {created_count}개 테이블 생성, {skipped_count}개 스킵\n")
    return True


def verify_migration():
    """마이그레이션 검증"""
    print("3. 마이그레이션 검증...")

    # stocks 테이블 컬럼 확인
    stocks_columns = ["market_cap", "week52_high", "week52_low", "dividend_yield", "is_managed"]
    print("   stocks 테이블 컬럼 확인:")
    for col in stocks_columns:
        exists = check_column_exists("stocks", col)
        status = "✓" if exists else "✗"
        print(f"     {status} {col}")

    # 새 테이블 확인
    new_tables = ["stock_quotes", "realtime_prices", "orders"]
    print("\n   새 테이블 확인:")
    for table in new_tables:
        exists = check_table_exists(table)
        status = "✓" if exists else "✗"
        print(f"     {status} {table}")

    print()


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("KIS API 호환 데이터 모델 마이그레이션")
    print("=" * 60)

    try:
        # 1. stocks 테이블 확장
        if not migrate_stocks_table():
            print("\n❌ 마이그레이션 실패: stocks 테이블 수정 오류")
            return

        # 2. 새 테이블 생성
        if not create_new_tables():
            print("\n❌ 마이그레이션 실패: 새 테이블 생성 오류")
            return

        # 3. 검증
        verify_migration()

        print("=" * 60)
        print("✅ 마이그레이션 완료!")
        print("=" * 60)
        print("\n다음 단계:")
        print("  1. python scripts/seed_kis_mock_data.py  # Mock 데이터 생성")
        print("  2. python -m pytest tests/  # 테스트 실행")
        print()

    except Exception as e:
        print(f"\n❌ 마이그레이션 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
