"""캐싱 서비스 (Redis + In-Memory Fallback)"""

import json
import time
from typing import Any, Optional
from datetime import timedelta
import redis
from src.config.settings import settings


class CacheManager:
    """
    캐싱 매니저

    - Redis가 사용 가능하면 Redis 사용
    - Redis가 없으면 인메모리 딕셔너리 사용 (Fallback)
    """

    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._memory_cache: dict[str, tuple[Any, float]] = {}
        self._initialize_redis()

    def _initialize_redis(self):
        """Redis 연결 초기화"""
        try:
            self._redis_client = redis.from_url(
                settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2
            )
            # 연결 테스트
            self._redis_client.ping()
            print("✅ Redis 연결 성공")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            print(f"⚠️ Redis 연결 실패, 인메모리 캐싱 사용: {e}")
            self._redis_client = None

    def _is_redis_available(self) -> bool:
        """Redis가 사용 가능한지 확인"""
        return self._redis_client is not None

    def get(self, key: str) -> Optional[Any]:
        """캐시에서 데이터 조회"""
        if self._is_redis_available():
            return self._get_from_redis(key)
        else:
            return self._get_from_memory(key)

    def set(
        self, key: str, value: Any, ttl: int = 300
    ) -> bool:  # ttl in seconds
        """캐시에 데이터 저장"""
        if self._is_redis_available():
            return self._set_to_redis(key, value, ttl)
        else:
            return self._set_to_memory(key, value, ttl)

    def delete(self, key: str) -> bool:
        """캐시에서 데이터 삭제"""
        if self._is_redis_available():
            return self._delete_from_redis(key)
        else:
            return self._delete_from_memory(key)

    def exists(self, key: str) -> bool:
        """키가 존재하는지 확인"""
        if self._is_redis_available():
            return bool(self._redis_client.exists(key))
        else:
            if key not in self._memory_cache:
                return False
            _, expire_time = self._memory_cache[key]
            if time.time() > expire_time:
                del self._memory_cache[key]
                return False
            return True

    # Redis 메서드
    def _get_from_redis(self, key: str) -> Optional[Any]:
        """Redis에서 데이터 조회"""
        try:
            value = self._redis_client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            print(f"Redis get 에러: {e}")
            return None

    def _set_to_redis(self, key: str, value: Any, ttl: int) -> bool:
        """Redis에 데이터 저장"""
        try:
            serialized = json.dumps(value, default=str)
            self._redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            print(f"Redis set 에러: {e}")
            return False

    def _delete_from_redis(self, key: str) -> bool:
        """Redis에서 데이터 삭제"""
        try:
            self._redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Redis delete 에러: {e}")
            return False

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
        if self._is_redis_available():
            self._redis_client.flushdb()
        self._memory_cache.clear()

    def get_stats(self) -> dict:
        """캐시 통계"""
        stats = {
            "backend": "redis" if self._is_redis_available() else "memory",
            "memory_cache_size": len(self._memory_cache),
        }

        if self._is_redis_available():
            try:
                info = self._redis_client.info()
                stats["redis_keys"] = info.get("db0", {}).get("keys", 0)
                stats["redis_memory"] = info.get("used_memory_human", "N/A")
            except:
                pass

        return stats


# 싱글톤 인스턴스
cache_manager = CacheManager()
