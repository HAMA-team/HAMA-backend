"""실시간 주가 데이터 캐싱 서비스"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import FinanceDataReader as fdr

from src.services.cache_manager import cache_manager
from src.services.kis_service import kis_service, KISAPIError
from src.config.settings import settings

logger = logging.getLogger(__name__)


class RealtimeCacheService:
    """
    실시간 주가 데이터 캐싱 서비스

    - 코스피/코스닥 전체 종목 리스트 관리
    - KIS API를 통한 실시간 주가 수집
    - 인메모리 캐시에 구조화된 형태로 저장
    - 배치 처리로 Rate Limit 관리
    """

    # 캐시 키 프리픽스
    KEY_PREFIX_PRICE = "realtime:price"
    KEY_PREFIX_INDEX = "realtime:index"
    KEY_STOCK_LIST = "realtime:stock_list"

    # 지수 코드 매핑
    INDEX_CODES = {
        "kospi": "0001",  # KOSPI 지수
        "kosdaq": "1001",  # KOSDAQ 지수
        "kospi200": "2001",  # KOSPI 200
    }

    def __init__(self):
        """서비스 초기화"""
        self.cache = cache_manager
        self._stock_list_cache: Optional[List[str]] = None

    async def get_all_stock_codes(self, market: str = "ALL") -> List[str]:
        """
        코스피/코스닥 전체 종목 코드 리스트 조회

        Args:
            market: "KOSPI", "KOSDAQ", "ALL" (기본: ALL)

        Returns:
            종목 코드 리스트 (예: ["005930", "000660", ...])
        """
        # 캐시 확인 (1시간 TTL)
        cache_key = f"{self.KEY_STOCK_LIST}:{market}"
        cached = self.cache.get(cache_key)

        if cached:
            logger.debug(f"✅ 종목 리스트 캐시 히트: {market}")
            return cached

        # FinanceDataReader로 종목 리스트 가져오기
        logger.info(f"📋 종목 리스트 조회 중: {market}")

        try:
            stock_codes = []

            if market in ["KOSPI", "ALL"]:
                kospi_df = await asyncio.to_thread(fdr.StockListing, "KOSPI")
                if kospi_df is not None and len(kospi_df) > 0:
                    stock_codes.extend(kospi_df["Code"].tolist())
                    logger.info(f"  - KOSPI: {len(kospi_df)}개")

            if market in ["KOSDAQ", "ALL"]:
                kosdaq_df = await asyncio.to_thread(fdr.StockListing, "KOSDAQ")
                if kosdaq_df is not None and len(kosdaq_df) > 0:
                    stock_codes.extend(kosdaq_df["Code"].tolist())
                    logger.info(f"  - KOSDAQ: {len(kosdaq_df)}개")

            # 중복 제거
            stock_codes = list(set(stock_codes))

            # 캐싱 (1시간)
            self.cache.set(cache_key, stock_codes, ttl=3600)

            logger.info(f"✅ 종목 리스트 조회 완료: {market} - 총 {len(stock_codes)}개")
            return stock_codes

        except Exception as e:
            logger.error(f"❌ 종목 리스트 조회 실패: {market} - {e}")
            return []

    async def cache_stock_price(self, stock_code: str) -> bool:
        """
        개별 종목의 현재가를 캐싱

        Args:
            stock_code: 종목 코드 (예: "005930")

        Returns:
            성공 여부
        """
        try:
            # KIS API로 현재가 조회
            price_data = await kis_service.get_stock_price(stock_code)

            if not price_data:
                logger.warning(f"⚠️ 주가 데이터 없음: {stock_code}")
                return False

            # 캐시에 저장할 데이터 구조
            cache_data = {
                "stock_code": stock_code,
                "stock_name": price_data.get("stock_name", ""),
                "price": price_data.get("current_price", 0),
                "change": price_data.get("change_price", 0),
                "change_rate": price_data.get("change_rate", 0.0),
                "volume": price_data.get("volume", 0),
                "timestamp": datetime.now().isoformat(),
            }

            # 캐싱 (TTL 120초 - 워커 실패 대비)
            cache_key = f"{self.KEY_PREFIX_PRICE}:{stock_code}"
            success = self.cache.set(cache_key, cache_data, ttl=120)

            if success:
                logger.debug(f"✅ 캐싱 완료: {stock_code} = {cache_data['price']:,}원")
            else:
                logger.warning(f"⚠️ 캐싱 실패: {stock_code}")

            return success

        except KISAPIError as e:
            logger.error(f"❌ KIS API 에러: {stock_code} - {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 캐싱 에러: {stock_code} - {e}")
            return False

    async def cache_stock_batch(
        self, stock_codes: List[str], batch_size: int = 50
    ) -> Dict[str, int]:
        """
        여러 종목을 배치로 캐싱 (Rate Limit 관리)

        Args:
            stock_codes: 종목 코드 리스트
            batch_size: 배치 크기 (KIS API Rate Limit 고려)

        Returns:
            {"success": 성공 개수, "failed": 실패 개수}
        """
        total = len(stock_codes)
        success_count = 0
        failed_count = 0

        logger.info(f"📦 배치 캐싱 시작: {total}개 종목 (배치 크기: {batch_size})")

        # 배치로 분할
        for i in range(0, total, batch_size):
            batch = stock_codes[i : i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            logger.info(
                f"  📦 배치 {batch_num}/{total_batches}: {len(batch)}개 처리 중..."
            )

            # 배치 내 종목 처리
            for stock_code in batch:
                success = await self.cache_stock_price(stock_code)
                if success:
                    success_count += 1
                else:
                    failed_count += 1

                # Rate Limit 준수 (KIS API: 초당 1회)
                await asyncio.sleep(1.1)

            # 배치 간 추가 대기 (안전 여유)
            if i + batch_size < total:
                logger.debug(f"  ⏸️ 다음 배치 전 2초 대기...")
                await asyncio.sleep(2)

        logger.info(
            f"✅ 배치 캐싱 완료: 성공 {success_count}개, 실패 {failed_count}개"
        )
        return {"success": success_count, "failed": failed_count}

    async def cache_market_index(self, index_name: str) -> bool:
        """
        시장 지수를 캐싱

        Args:
            index_name: 지수 이름 ("kospi", "kosdaq", "kospi200")

        Returns:
            성공 여부
        """
        if index_name not in self.INDEX_CODES:
            logger.error(f"❌ 지원하지 않는 지수: {index_name}")
            return False

        # TODO: KIS API에 지수 조회 메서드 추가 후 구현
        # 현재는 FinanceDataReader 사용 (실시간성은 떨어짐)
        logger.warning(f"⚠️ 지수 캐싱 미구현: {index_name} (Phase 2)")
        return False

    async def get_cached_price(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        캐시된 주가 데이터 조회

        Args:
            stock_code: 종목 코드

        Returns:
            주가 데이터 딕셔너리 (없으면 None)
        """
        cache_key = f"{self.KEY_PREFIX_PRICE}:{stock_code}"
        cached = self.cache.get(cache_key)

        if cached:
            logger.debug(f"✅ 캐시 히트: {stock_code}")
            return cached

        logger.debug(f"⚠️ 캐시 미스: {stock_code}")
        return None

    async def update_all_market_data(self) -> Dict[str, Any]:
        """
        전체 시장 데이터 업데이트 (Celery Task에서 호출)

        Returns:
            업데이트 결과 통계
        """
        logger.info("🔄 실시간 시장 데이터 업데이트 시작")

        start_time = datetime.now()

        # 1. 종목 리스트 조회
        stock_codes = await self.get_all_stock_codes(market="ALL")

        if not stock_codes:
            logger.error("❌ 종목 리스트가 비어있음")
            return {"status": "failed", "reason": "empty_stock_list"}

        # 2. 배치 캐싱 (Rate Limit 관리)
        result = await self.cache_stock_batch(stock_codes, batch_size=50)

        # 3. 지수 캐싱 (TODO)
        # await self.cache_market_index("kospi")
        # await self.cache_market_index("kosdaq")

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info(
            f"✅ 실시간 시장 데이터 업데이트 완료 "
            f"(소요 시간: {duration:.1f}초, 성공: {result['success']}개)"
        )

        return {
            "status": "completed",
            "total_stocks": len(stock_codes),
            "success": result["success"],
            "failed": result["failed"],
            "duration_seconds": duration,
            "timestamp": end_time.isoformat(),
        }

    def is_market_open(self) -> bool:
        """
        장중 시간인지 확인 (평일 09:00-15:30 KST)

        Returns:
            장중이면 True, 아니면 False
        """
        now = datetime.now()

        # 주말 체크
        if now.weekday() >= 5:  # 5=토요일, 6=일요일
            logger.debug("⏸️ 주말: 시장 휴무")
            return False

        # 시간 체크 (09:00 ~ 15:30)
        market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

        if market_open <= now <= market_close:
            logger.debug("✅ 장중 시간")
            return True
        else:
            logger.debug("⏸️ 장외 시간")
            return False


# 싱글톤 인스턴스
realtime_cache_service = RealtimeCacheService()
