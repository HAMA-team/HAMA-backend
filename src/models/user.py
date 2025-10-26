"""
User-related database models
"""
from sqlalchemy import Column, String, Integer, TIMESTAMP, DECIMAL, ARRAY, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from src.models.database import Base
from src.models.user_profile import UserProfile  # noqa: F401  # re-export for backward compatibility


class User(Base):
    """사용자 기본 정보"""
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(20))
    status = Column(String(20), default="active", index=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    last_login_at = Column(TIMESTAMP)


class UserPreference(Base):
    """사용자 선호도"""
    __tablename__ = "user_preferences"

    preference_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True)

    # 선호/회피 섹터
    preferred_sectors = Column(ARRAY(String))
    avoided_sectors = Column(ARRAY(String))

    # 선호/회피 종목
    preferred_stocks = Column(ARRAY(String))
    avoided_stocks = Column(ARRAY(String))

    # 알림 설정
    notification_settings = Column(JSON, default={"email": True, "push": False, "sms": False})

    # 모니터링 설정
    monitoring_frequency = Column(String(20), default="daily")
    price_alert_threshold = Column(DECIMAL(5, 4), default=0.10)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
