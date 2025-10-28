"""
HAMA 테스트를 위한 공통 Fixture 및 설정

Fixtures:
- dart_fixtures: DART API 응답 Fixture
- fdr_fixtures: FinanceDataReader 응답 Fixture
- portfolio_fixtures: 포트폴리오 샘플 데이터
- clean_db: 각 테스트 전 DB 초기화
- mock_llm: 테스트용 Mock LLM

사용법:
    def test_something(fdr_fixtures):
        samsung_price = fdr_fixtures["stock_price_samsung_1y"]
        ...
"""
import json
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 테스트 환경 설정 - 실제 LLM 사용하도록 ENV를 "integration"으로 설정
# "test"가 아닌 값을 설정하면 _is_test_mode()가 False를 반환하여 실제 Supervisor 동작
os.environ["ENV"] = "integration"

# LLM Provider 설정 - Anthropic 크레딧 부족 시 OpenAI 사용
# ANTHROPIC_API_KEY가 있어도 LLM_MODE를 통해 OpenAI 강제
os.environ["LLM_MODE"] = "openai"

from src.config.settings import Settings
from src.models.database import Base, SessionLocal, engine

# ==================== Fixture 로드 함수 ====================

def load_fixture(fixture_name: str) -> Dict[str, Any]:
    """
    Fixture JSON 파일을 로드합니다.

    Args:
        fixture_name: 파일명 (예: "dart_responses", "fdr_responses")

    Returns:
        파싱된 JSON 데이터
    """
    fixtures_dir = Path(__file__).parent / "fixtures"
    fixture_path = fixtures_dir / f"{fixture_name}.json"

    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture 파일을 찾을 수 없습니다: {fixture_path}")

    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ==================== Pytest Fixtures ====================

@pytest.fixture(scope="session")
def test_settings():
    """테스트용 Settings"""
    return Settings(ENV="integration")


@pytest.fixture(scope="session")
def dart_fixtures():
    """DART API Fixture - 전체 테스트 세션 동안 공유"""
    return load_fixture("dart_responses")


@pytest.fixture(scope="session")
def fdr_fixtures():
    """FinanceDataReader Fixture - 전체 테스트 세션 동안 공유"""
    return load_fixture("fdr_responses")


@pytest.fixture(scope="session")
def portfolio_fixtures():
    """포트폴리오 샘플 데이터 - 전체 테스트 세션 동안 공유"""
    return load_fixture("portfolio_snapshots")


@pytest.fixture(scope="function")
def clean_db():
    """
    각 테스트 함수 실행 전 DB 초기화

    사용법:
        def test_something(clean_db):
            # DB가 깨끗한 상태로 시작
            ...
    """
    # 테스트 전: 모든 테이블 삭제 후 재생성
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    yield

    # 테스트 후: 정리 (선택적)
    # Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(clean_db):
    """
    DB 세션 Fixture (각 테스트마다 새 세션)

    사용법:
        def test_something(db_session):
            user = User(...)
            db_session.add(user)
            db_session.commit()
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ==================== Mock LLM Fixtures ====================

@pytest.fixture
def mock_llm_routing_research():
    """
    Research Agent로 라우팅하는 Mock LLM

    "삼성전자 분석해줘" → research_agent 선택
    """
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value=AIMessage(
        content="",
        tool_calls=[{
            "name": "research_agent",
            "args": {"query": "삼성전자 분석"},
            "id": "call_001"
        }]
    ))
    return mock


@pytest.fixture
def mock_llm_routing_trading():
    """
    Trading Agent로 라우팅하는 Mock LLM

    "삼성전자 10주 매수" → trading_agent 선택
    """
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value=AIMessage(
        content="",
        tool_calls=[{
            "name": "trading_agent",
            "args": {"action": "buy", "stock_code": "005930", "quantity": 10},
            "id": "call_002"
        }]
    ))
    return mock


@pytest.fixture
def mock_llm_routing_general():
    """
    General Agent로 라우팅하는 Mock LLM

    "PER이 뭐야?" → general_agent 선택
    """
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value=AIMessage(
        content="",
        tool_calls=[{
            "name": "general_agent",
            "args": {"query": "PER 설명"},
            "id": "call_003"
        }]
    ))
    return mock


@pytest.fixture
def mock_llm_routing_multi_agents():
    """
    여러 에이전트 병렬 호출하는 Mock LLM

    "삼성전자 분석하고 리스크도 평가해줘" → research + risk
    """
    mock = MagicMock()
    mock.ainvoke = AsyncMock(return_value=AIMessage(
        content="",
        tool_calls=[
            {
                "name": "research_agent",
                "args": {"query": "삼성전자 분석"},
                "id": "call_004"
            },
            {
                "name": "risk_agent",
                "args": {"portfolio_id": "test"},
                "id": "call_005"
            }
        ]
    ))
    return mock


# ==================== Helper Functions ====================

def create_test_portfolio(
    db_session,
    portfolio_id: str = None,
    user_id: str = None,
    holdings: list = None
):
    """
    테스트용 포트폴리오를 DB에 생성합니다.

    Args:
        db_session: DB 세션
        portfolio_id: 포트폴리오 ID (없으면 자동 생성)
        user_id: 사용자 ID (없으면 자동 생성)
        holdings: 보유 종목 리스트

    Returns:
        생성된 Portfolio 객체
    """
    from src.models import portfolio as portfolio_models

    portfolio_id = portfolio_id or str(uuid.uuid4())
    user_id = user_id or str(uuid.uuid4())

    portfolio = portfolio_models.Portfolio(
        portfolio_id=uuid.UUID(portfolio_id),
        user_id=uuid.UUID(user_id),
        portfolio_name="테스트 포트폴리오",
        strategy_type="balanced",
        total_value=Decimal("10000000"),
        cash_balance=Decimal("2000000"),
        invested_amount=Decimal("8000000"),
    )

    db_session.add(portfolio)
    db_session.commit()

    # Holdings 추가
    if holdings:
        for holding in holdings:
            position = portfolio_models.Position(
                position_id=uuid.uuid4(),
                portfolio_id=uuid.UUID(portfolio_id),
                stock_code=holding["stock_code"],
                stock_name=holding.get("stock_name", ""),
                quantity=holding["quantity"],
                avg_price=Decimal(str(holding["avg_price"])),
                current_price=Decimal(str(holding.get("current_price", holding["avg_price"]))),
                market_value=Decimal(str(holding.get("market_value", 0))),
                weight=Decimal(str(holding.get("weight", 0))),
            )
            db_session.add(position)
        db_session.commit()

    return portfolio


def create_test_chat_session(
    db_session,
    conversation_id: str = None,
    user_id: str = None,
    automation_level: int = 2
):
    """
    테스트용 채팅 세션을 DB에 생성합니다.

    Args:
        db_session: DB 세션
        conversation_id: 대화 ID
        user_id: 사용자 ID
        automation_level: 자동화 레벨 (1-3)

    Returns:
        생성된 ChatSession 객체
    """
    from src.models.chat import ChatSession

    conversation_id = conversation_id or str(uuid.uuid4())
    user_id = user_id or str(uuid.uuid4())

    session = ChatSession(
        conversation_id=uuid.UUID(conversation_id),
        user_id=uuid.UUID(user_id),
        automation_level=automation_level,
        session_metadata={"test": True},
    )

    db_session.add(session)
    db_session.commit()

    return session


# ==================== Pytest 설정 ====================

@pytest.fixture(autouse=True)
def reset_environment():
    """각 테스트 전후 환경 변수 초기화"""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)


def pytest_configure(config):
    """Pytest 설정 초기화"""
    # 커스텀 마커 등록
    config.addinivalue_line(
        "markers", "integration: 통합 테스트 (실제 API 호출)"
    )
    config.addinivalue_line(
        "markers", "e2e: E2E 테스트 (전체 플로우)"
    )
    config.addinivalue_line(
        "markers", "slow: 느린 테스트 (10초 이상)"
    )
