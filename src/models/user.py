"""
User-related database models
"""
from sqlalchemy import Column, String, Integer, TIMESTAMP, CheckConstraint, DECIMAL, ARRAY, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from src.models.database import Base


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


class UserProfile(Base):
    """사용자 프로필 (투자 성향)"""
    __tablename__ = "user_profiles"

    profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True)

    # 투자 성향
    risk_tolerance = Column(String(20), nullable=False)  # aggressive, active, neutral, conservative, safe
    investment_goal = Column(String(50), nullable=False)  # short_term, mid_long_term, dividend, other
    investment_horizon = Column(String(20), nullable=False)  # under_1y, 1_3y, 3_5y, over_5y

    # 자동화 레벨
    automation_level = Column(Integer, nullable=False, default=2)  # 1: Pilot, 2: Copilot, 3: Advisor

    # 투자 제약
    initial_capital = Column(DECIMAL(15, 2))
    monthly_contribution = Column(DECIMAL(15, 2))
    max_single_stock_ratio = Column(DECIMAL(5, 4), default=0.20)
    max_sector_ratio = Column(DECIMAL(5, 4), default=0.40)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("automation_level BETWEEN 1 AND 3", name="check_automation_level"),
        CheckConstraint(
            "risk_tolerance IN ('aggressive', 'active', 'neutral', 'conservative', 'safe')",
            name="check_risk_tolerance"
        ),
    )


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