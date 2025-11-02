"""
UserSettings 저장/조회용 Repository.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from src.models.user_settings import UserSettings
from src.schemas.hitl_config import HITLConfig


class UserSettingsRepository:
    """사용자별 HITL 설정을 관리한다."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_user_settings(self, user_id: uuid.UUID) -> Optional[UserSettings]:
        """사용자 설정을 조회한다."""
        return (
            self.session.query(UserSettings)
            .filter(UserSettings.user_id == user_id)
            .one_or_none()
        )

    def upsert_hitl_config(self, user_id: uuid.UUID, config: HITLConfig) -> UserSettings:
        """
        HITL 설정을 저장하거나 업데이트한다.
        """
        settings = self.get_user_settings(user_id)

        if settings is None:
            settings = UserSettings(user_id=user_id, hitl_config=config.model_dump())
            self.session.add(settings)
        else:
            settings.hitl_config = config.model_dump()

        self.session.commit()
        self.session.refresh(settings)
        return settings

