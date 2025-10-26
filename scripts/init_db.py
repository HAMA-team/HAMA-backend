#!/usr/bin/env python3
"""
데이터베이스 테이블 생성 스크립트

모든 SQLAlchemy 모델을 기반으로 테이블을 생성합니다.
"""
import sys
from pathlib import Path

# src 디렉터리를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import Base, engine, init_db
from src.models.user import User, UserPreference
from src.models.user_profile import UserProfile
from src.models.stock import Stock, StockPrice, FinancialStatement, Disclosure, News
from src.models.portfolio import Portfolio, Position, Transaction, PortfolioSnapshot
from src.models.agent import (
    ResearchReport, TradingSignal, RiskAssessment,
    ApprovalRequest, UserDecision, AgentLog, Alert
)


def main():
    """테이블 생성 메인 함수"""
    print("=" * 60)
    print("HAMA Backend - Database Initialization")
    print("=" * 60)
    print()

    print("📦 Loaded models:")
    models = [
        "User", "UserProfile", "UserPreference",
        "Stock", "StockPrice", "FinancialStatement", "Disclosure", "News",
        "Portfolio", "Position", "Transaction", "PortfolioSnapshot",
        "ResearchReport", "TradingSignal", "RiskAssessment",
        "ApprovalRequest", "UserDecision", "AgentLog", "Alert"
    ]
    for model in models:
        print(f"  ✓ {model}")
    print()

    print("🔨 Creating tables...")
    try:
        init_db()
        print("✅ All tables created successfully!")
        print()

        # 생성된 테이블 확인
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        print(f"📋 Created {len(tables)} tables:")
        for table in sorted(tables):
            print(f"  ✓ {table}")

        print()
        print("=" * 60)
        print("✨ Database initialization complete!")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
