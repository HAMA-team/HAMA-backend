"""
Week 1: UserProfile Service 테스트
사용자 프로파일 CRUD 및 Redis 캐싱 검증
"""

import pytest
import asyncio
import uuid
from typing import Dict, Any


class TestUserProfileService:
    """UserProfile Service 테스트"""

    @pytest.mark.asyncio
    async def test_create_user_profile(self):
        """사용자 프로파일 생성 테스트"""
        from src.services.user_profile_service import UserProfileService
        from src.models.database import get_db

        print("\n[사용자 프로파일 생성 테스트]")

        service = UserProfileService()
        db = next(get_db())

        # 테스트용 사용자 ID
        test_user_id = f"test-user-{uuid.uuid4()}"

        profile_data = {
            "expertise_level": "intermediate",
            "investment_style": "moderate",
            "risk_tolerance": "medium",
            "preferred_sectors": ["반도체", "배터리"],
            "trading_style": "long_term",
            "technical_level": "intermediate",
            "preferred_depth": "detailed",
            "wants_explanations": True,
            "wants_analogies": False
        }

        print(f"\n사용자 ID: {test_user_id}")
        print(f"프로파일 데이터: {profile_data}")

        # 프로파일 생성
        created_profile = await service.create_user_profile(
            user_id=test_user_id,
            profile_data=profile_data,
            db=db
        )

        # 검증
        assert created_profile["user_id"] == test_user_id
        assert created_profile["expertise_level"] == "intermediate"
        assert "반도체" in created_profile["preferred_sectors"]

        print(f"\n✅ 프로파일 생성 성공: {created_profile['user_id']}")

        # 정리
        await service.delete_user_profile(user_id=test_user_id, db=db)

    @pytest.mark.asyncio
    async def test_get_user_profile(self):
        """사용자 프로파일 조회 테스트"""
        from src.services.user_profile_service import UserProfileService
        from src.models.database import get_db

        print("\n[사용자 프로파일 조회 테스트]")

        service = UserProfileService()
        db = next(get_db())

        # 테스트용 프로파일 생성
        test_user_id = f"test-user-{uuid.uuid4()}"

        profile_data = {
            "expertise_level": "beginner",
            "investment_style": "conservative",
            "risk_tolerance": "low"
        }

        await service.create_user_profile(
            user_id=test_user_id,
            profile_data=profile_data,
            db=db
        )

        print(f"\n사용자 ID: {test_user_id}")

        # 프로파일 조회
        retrieved_profile = await service.get_user_profile(
            user_id=test_user_id,
            db=db
        )

        # 검증
        assert retrieved_profile is not None
        assert retrieved_profile["user_id"] == test_user_id
        assert retrieved_profile["expertise_level"] == "beginner"

        print(f"✅ 프로파일 조회 성공: {retrieved_profile['expertise_level']} 사용자")

        # 정리
        await service.delete_user_profile(user_id=test_user_id, db=db)

    @pytest.mark.asyncio
    async def test_update_user_profile(self):
        """사용자 프로파일 업데이트 테스트"""
        from src.services.user_profile_service import UserProfileService
        from src.models.database import get_db

        print("\n[사용자 프로파일 업데이트 테스트]")

        service = UserProfileService()
        db = next(get_db())

        # 테스트용 프로파일 생성
        test_user_id = f"test-user-{uuid.uuid4()}"

        initial_data = {
            "expertise_level": "beginner",
            "preferred_sectors": ["반도체"]
        }

        await service.create_user_profile(
            user_id=test_user_id,
            profile_data=initial_data,
            db=db
        )

        print(f"\n사용자 ID: {test_user_id}")
        print(f"초기 프로파일: {initial_data}")

        # 프로파일 업데이트
        update_data = {
            "expertise_level": "intermediate",
            "preferred_sectors": ["반도체", "배터리"]
        }

        print(f"업데이트 데이터: {update_data}")

        updated_profile = await service.update_user_profile(
            user_id=test_user_id,
            updates=update_data,
            db=db
        )

        # 검증
        assert updated_profile["expertise_level"] == "intermediate"
        assert "배터리" in updated_profile["preferred_sectors"]

        print(f"✅ 프로파일 업데이트 성공:")
        print(f"   expertise_level: beginner → intermediate")
        print(f"   preferred_sectors: ['반도체'] → ['반도체', '배터리']")

        # 정리
        await service.delete_user_profile(user_id=test_user_id, db=db)

    @pytest.mark.asyncio
    async def test_user_profile_cache(self):
        """
        Redis 캐싱 테스트

        1차 조회: DB → Redis 캐시 저장
        2차 조회: Redis 캐시에서 조회 (빠름)
        """
        from src.services.user_profile_service import UserProfileService
        from src.models.database import get_db
        import time

        print("\n[Redis 캐싱 테스트]")

        service = UserProfileService()
        db = next(get_db())

        # 테스트용 프로파일 생성
        test_user_id = f"test-user-{uuid.uuid4()}"

        profile_data = {
            "expertise_level": "expert",
            "investment_style": "aggressive"
        }

        await service.create_user_profile(
            user_id=test_user_id,
            profile_data=profile_data,
            db=db
        )

        print(f"\n사용자 ID: {test_user_id}")

        # 1차 조회 (DB)
        print("\n1차 조회 (DB에서)...")
        start1 = time.time()
        profile1 = await service.get_user_profile(user_id=test_user_id, db=db)
        time1 = time.time() - start1

        print(f"   소요 시간: {time1*1000:.2f}ms")

        # 2차 조회 (캐시)
        print("\n2차 조회 (캐시에서)...")
        start2 = time.time()
        profile2 = await service.get_user_profile(user_id=test_user_id, db=db)
        time2 = time.time() - start2

        print(f"   소요 시간: {time2*1000:.2f}ms")

        # 검증: 동일한 데이터
        assert profile1 == profile2

        # 캐시가 더 빠름 (일반적으로)
        if time2 < time1:
            print(f"\n✅ 캐시 히트! {time1/time2:.2f}배 빠름")
        else:
            print(f"\n⚠️  캐시 성능 개선 필요 또는 네트워크 지연")

        # 정리
        await service.delete_user_profile(user_id=test_user_id, db=db)

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_update(self):
        """
        프로파일 업데이트 시 캐시 무효화 테스트

        업데이트 후 조회 시 최신 데이터를 반환해야 함
        """
        from src.services.user_profile_service import UserProfileService
        from src.models.database import get_db

        print("\n[캐시 무효화 테스트]")

        service = UserProfileService()
        db = next(get_db())

        # 테스트용 프로파일 생성
        test_user_id = f"test-user-{uuid.uuid4()}"

        initial_data = {
            "expertise_level": "beginner"
        }

        await service.create_user_profile(
            user_id=test_user_id,
            profile_data=initial_data,
            db=db
        )

        print(f"\n사용자 ID: {test_user_id}")

        # 1차 조회 (캐시 저장)
        print("\n1. 초기 조회...")
        profile1 = await service.get_user_profile(user_id=test_user_id, db=db)
        print(f"   expertise_level: {profile1['expertise_level']}")

        # 업데이트
        print("\n2. 프로파일 업데이트...")
        await service.update_user_profile(
            user_id=test_user_id,
            updates={"expertise_level": "expert"},
            db=db
        )

        # 2차 조회 (최신 데이터여야 함)
        print("\n3. 업데이트 후 조회...")
        profile2 = await service.get_user_profile(user_id=test_user_id, db=db)
        print(f"   expertise_level: {profile2['expertise_level']}")

        # 검증: 업데이트된 값이 반영되어야 함
        assert profile2["expertise_level"] == "expert"

        print("\n✅ 캐시 무효화 정상 작동 (업데이트 즉시 반영)")

        # 정리
        await service.delete_user_profile(user_id=test_user_id, db=db)


if __name__ == "__main__":
    """테스트 직접 실행"""
    async def main():
        tester = TestUserProfileService()

        print("="*60)
        print("Week 1: UserProfile Service 테스트 시작")
        print("="*60)

        try:
            # 1. 프로파일 생성 테스트
            await tester.test_create_user_profile()

            # 2. 프로파일 조회 테스트
            await tester.test_get_user_profile()

            # 3. 프로파일 업데이트 테스트
            await tester.test_update_user_profile()

            # 4. Redis 캐싱 테스트
            await tester.test_user_profile_cache()

            # 5. 캐시 무효화 테스트
            await tester.test_cache_invalidation_on_update()

            print("\n" + "="*60)
            print("✅ UserProfile Service 테스트 모두 성공!")
            print("="*60)
        except Exception as e:
            print(f"\n❌ 테스트 실패: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(main())
