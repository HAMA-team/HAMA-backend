"""
사용자 프로파일 서비스

user_profiles 테이블 스키마는 SQLAlchemy 모델과 동일하게 관리된다.
"""

import logging
import uuid
from typing import Any, Dict, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.user_profile import UserProfile

logger = logging.getLogger(__name__)


class UserProfileService:
    """사용자 프로파일 조회/저장 로직"""

    def _normalize_user_id(self, user_id: Union[str, uuid.UUID]) -> uuid.UUID:
        if isinstance(user_id, uuid.UUID):
            return user_id

        if isinstance(user_id, str):
            try:
                return uuid.UUID(user_id)
            except ValueError as exc:
                if not user_id.strip():
                    raise ValueError("user_id string is empty") from exc
                normalized = uuid.uuid5(uuid.NAMESPACE_URL, f"user-profile:{user_id}")
                logger.info(
                    "⚠️ [UserProfile] UUID 형식이 아닌 식별자를 UUID5로 변환: %s -> %s",
                    user_id,
                    normalized,
                )
                return normalized

        raise TypeError("user_id must be a UUID or string")

    def get_user_profile(self, user_id: Union[str, uuid.UUID], db: Session) -> Dict[str, Any]:
        """사용자 프로파일 조회 (DB 조회 후 없으면 기본값 생성)"""
        user_uuid = self._normalize_user_id(user_id)
        logger.info("🔍 [UserProfile] DB에서 조회: %s", user_uuid)
        profile = db.execute(select(UserProfile).filter_by(user_id=user_uuid)).scalars().first()

        if not profile:
            logger.info("🆕 [UserProfile] 기본 프로파일 생성: %s", user_uuid)
            profile = UserProfile(
                user_id=user_uuid,
                expertise_level="intermediate",
                investment_style="moderate",
                risk_tolerance="medium",
                avg_trades_per_day=1.0,
                preferred_sectors=[],
                trading_style="long_term",
                portfolio_concentration=0.5,
                technical_level="intermediate",
                preferred_depth="detailed",
                wants_explanations=True,
                wants_analogies=False,
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)

        profile_dict = profile.to_dict()
        return profile_dict

    def update_user_profile(
        self, user_id: Union[str, uuid.UUID], updates: Dict[str, Any], db: Session
    ) -> Dict[str, Any]:
        """
        사용자 프로파일 업데이트 및 캐시 최신화
        """
        user_uuid = self._normalize_user_id(user_id)
        logger.info("📝 [UserProfile] 업데이트: %s", user_uuid)

        profile = db.execute(select(UserProfile).filter_by(user_id=user_uuid)).scalars().first()
        if not profile:
            raise ValueError(f"User profile not found: {user_uuid}")

        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        db.commit()
        db.refresh(profile)

        profile_dict = profile.to_dict()
        logger.info("✅ [UserProfile] 업데이트 완료: %s", user_uuid)

        return profile_dict

    def invalidate_cache(self, user_id: Union[str, uuid.UUID]) -> None:
        """캐싱 제거 이후에도 API 호환성을 위한 no-op 메서드."""
        logger.info("ℹ️ [UserProfile] invalidate_cache 호출 (캐싱 기능 제거됨)")


user_profile_service = UserProfileService()
