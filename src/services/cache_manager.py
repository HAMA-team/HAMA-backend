"""단일 프로세스 인메모리 캐시 서비스"""

import time
from typing import Any, Optional


class CacheManager:
    """
    프로세스 내부 딕셔너리를 사용한 간단한 캐시 매니저.
    TTL 이 만료된 엔트리는 접근 시 자동 정리한다.
    """

    def __init__(self):
        self._memory_cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        """캐시에서 데이터 조회 (캐싱 비활성화됨)"""
        # 캐싱 비활성화: 항상 None 반환하여 API 직접 호출
        return None

    def set(
        self, key: str, value: Any, ttl: int = 300
    ) -> bool:  # ttl in seconds
        """캐시에 데이터 저장 (캐싱 비활성화됨)"""
        # 캐싱 비활성화: 저장하지 않음
        return True

    def delete(self, key: str) -> bool:
        """캐시에서 데이터 삭제"""
        return self._delete_from_memory(key)

    def exists(self, key: str) -> bool:
        """키가 존재하는지 확인"""
        if key not in self._memory_cache:
            return False
        _, expire_time = self._memory_cache[key]
        if time.time() > expire_time:
            del self._memory_cache[key]
            return False
        return True

    # 인메모리 메서드
    def _get_from_memory(self, key: str) -> Optional[Any]:
        """인메모리 캐시에서 데이터 조회"""
        if key not in self._memory_cache:
            return None

        value, expire_time = self._memory_cache[key]

        # 만료 확인
        if time.time() > expire_time:
            del self._memory_cache[key]
            return None

        return value

    def _set_to_memory(self, key: str, value: Any, ttl: int) -> bool:
        """인메모리 캐시에 데이터 저장"""
        try:
            expire_time = time.time() + ttl
            self._memory_cache[key] = (value, expire_time)
            return True
        except Exception as e:
            print(f"Memory cache set 에러: {e}")
            return False

    def _delete_from_memory(self, key: str) -> bool:
        """인메모리 캐시에서 데이터 삭제"""
        try:
            if key in self._memory_cache:
                del self._memory_cache[key]
            return True
        except Exception as e:
            print(f"Memory cache delete 에러: {e}")
            return False

    def clear_all(self):
        """모든 캐시 삭제 (개발/테스트용)"""
        self._memory_cache.clear()

    def get_stats(self) -> dict:
        """캐시 통계"""
        return {
            "backend": "memory",
            "memory_cache_size": len(self._memory_cache),
        }


# 싱글톤 인스턴스
cache_manager = CacheManager()
