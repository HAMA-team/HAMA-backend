"""
pytest fixtures for testing HAMA backend

Provides:
- test_db: Test database session
- client: FastAPI TestClient
- sample_data: Sample test data
"""
import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 테스트 환경 설정 (실제 API 키는 .env 파일에서 로드)
os.environ["ENV"] = "test"

from src.main import app
from src.models.database import Base, get_db
from src.config.settings import Settings


# Test database URL
TEST_DATABASE_URL = "sqlite:///./hama_test.db"


@pytest.fixture(scope="session")
def settings():
    """테스트용 settings fixture"""
    return Settings(
        DATABASE_URL=TEST_DATABASE_URL,
        ENVIRONMENT="test"
    )


@pytest.fixture(scope="session")
def test_engine():
    """테스트 DB 엔진 생성"""
    connect_args = {}
    if TEST_DATABASE_URL.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    engine = create_engine(TEST_DATABASE_URL, connect_args=connect_args, future=True)

    # 테스트 DB 초기화
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield engine

    # 테스트 완료 후 정리
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_engine):
    """함수별 DB 세션 생성"""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(test_db):
    """FastAPI TestClient fixture"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_stocks():
    """샘플 종목 데이터"""
    return [
        {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "market": "KOSPI",
            "sector": "반도체",
            "industry": "반도체"
        },
        {
            "stock_code": "000660",
            "stock_name": "SK하이닉스",
            "market": "KOSPI",
            "sector": "반도체",
            "industry": "반도체"
        },
        {
            "stock_code": "035420",
            "stock_name": "NAVER",
            "market": "KOSPI",
            "sector": "IT",
            "industry": "인터넷"
        }
    ]


@pytest.fixture
def sample_chat_request():
    """샘플 Chat 요청 데이터"""
    return {
        "message": "삼성전자 분석해줘",
        "automation_level": 2
    }


@pytest.fixture
def sample_trade_request():
    """샘플 매매 요청 데이터"""
    return {
        "message": "삼성전자 1000만원 매수",
        "automation_level": 2
    }


@pytest.fixture
def sample_rebalancing_request():
    """샘플 리밸런싱 요청 데이터"""
    return {
        "message": "포트폴리오 리밸런싱해줘",
        "automation_level": 2
    }
