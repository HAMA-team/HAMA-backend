"""
사용자 프로파일 서비스

사용자 프로파일 조회, 생성, 업데이트 및 캐싱 관리
"""
import json
import logging
from typing import Optional
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.user_profile import UserProfile
from src.services.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class UserProfileService:
    """사용자 프로파일 서비스"""

    CACHE_TTL = 3600  # 1시간

    async def get_user_profile(
        self, user_id: str | uuid.UUID, db: AsyncSession
    ) -> dict:
        """
        사용자 프로파일 조회 (캐시 우선)

        Args:
            user_id: 사용자 ID
            db: DB 세션

        Returns:
            사용자 프로파일 딕셔너리
        """
        # UUID 변환
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        cache_key = f"profile:{user_id}"

        # 1. 캐시 확인
        cached = await cache_manager.get(cache_key)
        if cached:
            logger.info(f"✅ [UserProfile] 캐시에서 조회: {user_id}")
            return json.loads(cached)

        # 2. DB 조회
        logger.info(f"🔍 [UserProfile] DB에서 조회: {user_id}")
        result = await db.execute(select(UserProfile).filter_by(user_id=user_id))
        profile = result.scalars().first()

        if not profile:
            # 3. 기본 프로파일 생성
            logger.info(f"🆕 [UserProfile] 기본 프로파일 생성: {user_id}")
            profile = UserProfile(
                user_id=user_id,
                expertise_level="intermediate",
                investment_style="moderate",
                risk_tolerance="medium",
                technical_level="intermediate",
                preferred_depth="detailed",
                wants_explanations=True,
                wants_analogies=False,
            )
            db.add(profile)
            await db.commit()
            await db.refresh(profile)

        profile_dict = profile.to_dict()

        # 4. 캐싱
        await cache_manager.set(cache_key, json.dumps(profile_dict), ttl=self.CACHE_TTL)

        return profile_dict

    async def update_user_profile(
        self, user_id: str | uuid.UUID, updates: dict, db: AsyncSession
    ) -> dict:
        """
        사용자 프로파일 업데이트

        Args:
            user_id: 사용자 ID
            updates: 업데이트할 필드 딕셔너리
            db: DB 세션

        Returns:
            업데이트된 프로파일
        """
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        logger.info(f"📝 [UserProfile] 업데이트: {user_id}")

        # DB 업데이트
        result = await db.execute(select(UserProfile).filter_by(user_id=user_id))
        profile = result.scalars().first()

        if not profile:
            raise ValueError(f"User profile not found: {user_id}")

        # 필드 업데이트
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        await db.commit()
        await db.refresh(profile)

        profile_dict = profile.to_dict()

        # 캐시 무효화
        cache_key = f"profile:{user_id}"
        await cache_manager.delete(cache_key)

        # 새 데이터 캐싱
        await cache_manager.set(cache_key, json.dumps(profile_dict), ttl=self.CACHE_TTL)

        logger.info(f"✅ [UserProfile] 업데이트 완료: {user_id}")

        return profile_dict

    async def invalidate_cache(self, user_id: str | uuid.UUID):
        """
        프로파일 캐시 무효화

        Args:
            user_id: 사용자 ID
        """
        if isinstance(user_id, str):
            user_id = uuid.UUID(user_id)

        cache_key = f"profile:{user_id}"
        await cache_manager.delete(cache_key)
        logger.info(f"🗑️ [UserProfile] 캐시 무효화: {user_id}")


# 싱글톤 인스턴스
user_profile_service = UserProfileService()
