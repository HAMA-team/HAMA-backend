"""
사용자별 HITL 설정을 저장하는 테이블 정의.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, JSON, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.models.database import Base


class UserSettings(Base):
    """사용자별 자동화(HITL) 설정"""

    __tablename__ = "user_settings"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hitl_config = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(
        TIMESTAMP,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def as_hitl_config(self):
        """Pydantic HITLConfig 인스턴스로 변환"""
        from src.schemas.hitl_config import HITLConfig

        return HITLConfig.model_validate(self.hitl_config)

