"""CacheManager 테스트"""

import asyncio
import time
from src.services.cache_manager import CacheManager


async def test_cache_set_and_get():
    """캐시 저장 및 조회 테스트"""
    cache = CacheManager()

    # 데이터 저장
    await cache.set("test_key", "test_value", ttl=10)

    # 데이터 조회
    value = await cache.get("test_key")
    assert value == "test_value"

    print("✅ 캐시 저장/조회 테스트 통과")


async def test_cache_expiration():
    """캐시 만료 테스트"""
    cache = CacheManager()

    # TTL 2초로 저장
    await cache.set("expire_key", "expire_value", ttl=2)

    # 즉시 조회 - 존재해야 함
    value = await cache.get("expire_key")
    assert value == "expire_value"

    # 3초 대기
    print("⏳ 3초 대기 중...")
    await asyncio.sleep(3)

    # 다시 조회 - 만료되어 None이어야 함
    value = await cache.get("expire_key")
    assert value is None

    print("✅ 캐시 만료 테스트 통과")


async def test_cache_delete():
    """캐시 삭제 테스트"""
    cache = CacheManager()

    # 데이터 저장
    await cache.set("delete_key", "delete_value", ttl=10)

    # 존재 확인
    exists = await cache.exists("delete_key")
    assert exists is True

    # 삭제
    await cache.delete("delete_key")

    # 다시 확인 - 없어야 함
    exists = await cache.exists("delete_key")
    assert exists is False

    print("✅ 캐시 삭제 테스트 통과")


async def test_cache_complex_data():
    """복잡한 데이터 타입 테스트"""
    cache = CacheManager()

    # 딕셔너리 저장
    data = {
        "name": "삼성전자",
        "code": "005930",
        "price": 89000,
        "prices": [88000, 88500, 89000],
    }

    await cache.set("complex_key", data, ttl=10)

    # 조회
    result = await cache.get("complex_key")
    assert result == data
    assert result["name"] == "삼성전자"
    assert result["prices"][2] == 89000

    print("✅ 복잡한 데이터 타입 테스트 통과")


async def test_cache_stats():
    """캐시 통계 테스트"""
    cache = CacheManager()

    # 몇 개 데이터 저장
    await cache.set("stat1", "value1", ttl=10)
    await cache.set("stat2", "value2", ttl=10)
    await cache.set("stat3", "value3", ttl=10)

    # 통계 확인
    stats = cache.get_stats()
    print(f"✅ 캐시 백엔드: {stats['backend']}")
    print(f"✅ 메모리 캐시 크기: {stats['memory_cache_size']}")

    if stats["backend"] == "redis":
        print(f"✅ Redis 키 수: {stats.get('redis_keys', 0)}")
        print(f"✅ Redis 메모리: {stats.get('redis_memory', 'N/A')}")


async def main():
    print("\n🔍 CacheManager 테스트 시작\n")

    await test_cache_set_and_get()
    print("1️⃣ 캐시 저장/조회 완료\n")

    await test_cache_expiration()
    print("2️⃣ 캐시 만료 완료\n")

    await test_cache_delete()
    print("3️⃣ 캐시 삭제 완료\n")

    await test_cache_complex_data()
    print("4️⃣ 복잡한 데이터 타입 완료\n")

    await test_cache_stats()
    print("5️⃣ 캐시 통계 완료\n")

    print("✅ 모든 CacheManager 테스트 통과!")


if __name__ == "__main__":
    asyncio.run(main())
