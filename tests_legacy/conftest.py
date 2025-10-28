"""
pytest fixtures for testing HAMA backend

Provides:
- settings: Test settings
- Redis 초기화 (자동)
"""
import os
import sys
from pathlib import Path
import pytest

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 테스트 환경 설정 (실제 API 키는 .env 파일에서 로드)
os.environ["ENV"] = "test"

from src.config.settings import Settings


@pytest.fixture(scope="session")
def test_settings():
    """테스트용 settings fixture"""
    return Settings(ENV="test")


# Redis 연결은 자동으로 src/services/cache_manager.py에서 처리됨
# 추가 fixture는 필요할 때 작성
