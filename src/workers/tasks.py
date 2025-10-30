"""
Celery Tasks

실시간 주가 데이터 수집을 위한 주기적 태스크
"""

import asyncio
import logging
from datetime import datetime

from src.workers.celery_app import app
from src.services.realtime_cache_service import realtime_cache_service
from src.services.stock_data_service import update_recent_prices_for_market
from src.services.macro_data_service import macro_data_service

logger = logging.getLogger(__name__)


@app.task(
    bind=True,
    name="src.workers.tasks.update_realtime_market_data",
    max_retries=3,
    default_retry_delay=60,  # 실패 시 60초 후 재시도
)
def update_realtime_market_data(self):
    """
    실시간 시장 데이터 업데이트 (주기적 실행)

    - Celery Beat에서 60초마다 자동 호출
    - 장중 시간대만 실행 (평일 09:00-15:30)
    - 실패 시 최대 3회 재시도
    """
    logger.info("=" * 80)
    logger.info(f"🔄 [Task] 실시간 시장 데이터 업데이트 시작 - {datetime.now()}")
    logger.info("=" * 80)

    try:
        # 1. 장중 시간 체크
        if not realtime_cache_service.is_market_open():
            logger.info("⏸️ [Task] 장외 시간 - 업데이트 스킵")
            return {
                "status": "skipped",
                "reason": "market_closed",
                "timestamp": datetime.now().isoformat(),
            }

        # 2. 비동기 함수 실행 (asyncio 이벤트 루프)
        result = asyncio.run(realtime_cache_service.update_all_market_data())

        logger.info("=" * 80)
        logger.info(
            f"✅ [Task] 실시간 시장 데이터 업데이트 완료 - "
            f"성공: {result.get('success', 0)}개, "
            f"실패: {result.get('failed', 0)}개, "
            f"소요: {result.get('duration_seconds', 0):.1f}초"
        )
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ [Task] 실시간 시장 데이터 업데이트 실패: {e}")
        logger.error("=" * 80)

        # 재시도 (최대 3회)
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error("❌ [Task] 최대 재시도 횟수 초과")
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }


@app.task(
    name="src.workers.tasks.update_stock_batch",
    max_retries=2,
)
def update_stock_batch(stock_codes: list):
    """
    특정 종목 배치 업데이트 (수동 호출용)

    Args:
        stock_codes: 종목 코드 리스트 (예: ["005930", "000660"])

    Returns:
        업데이트 결과
    """
    logger.info(f"📦 [Task] 배치 업데이트 시작: {len(stock_codes)}개 종목")

    try:
        result = asyncio.run(
            realtime_cache_service.cache_stock_batch(stock_codes, batch_size=50)
        )

        logger.info(
            f"✅ [Task] 배치 업데이트 완료: "
            f"성공 {result['success']}개, 실패 {result['failed']}개"
        )

        return {
            "status": "completed",
            "total": len(stock_codes),
            "success": result["success"],
            "failed": result["failed"],
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ [Task] 배치 업데이트 실패: {e}")
        raise


@app.task(name="src.workers.tasks.cache_single_stock")
def cache_single_stock(stock_code: str):
    """
    단일 종목 캐싱 (수동 호출용)

    Args:
        stock_code: 종목 코드 (예: "005930")

    Returns:
        캐싱 결과
    """
    logger.info(f"💾 [Task] 단일 종목 캐싱: {stock_code}")

    try:
        success = asyncio.run(realtime_cache_service.cache_stock_price(stock_code))

        if success:
            logger.info(f"✅ [Task] 캐싱 완료: {stock_code}")
            return {
                "status": "success",
                "stock_code": stock_code,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            logger.warning(f"⚠️ [Task] 캐싱 실패: {stock_code}")
            return {
                "status": "failed",
                "stock_code": stock_code,
                "timestamp": datetime.now().isoformat(),
            }

    except Exception as e:
        logger.error(f"❌ [Task] 캐싱 에러: {stock_code} - {e}")
        raise


@app.task(
    name="src.workers.tasks.refresh_price_history_daily",
    max_retries=2,
)
def refresh_price_history_daily(market: str = "ALL", days: int = 5, limit: int | None = None):
    """장 마감 후 최근 주가/지표를 갱신"""

    result = asyncio.run(update_recent_prices_for_market(market=market, days=days, limit=limit))
    logger.info(
        "✅ [Task] 주가 히스토리 갱신: market=%s processed=%s success=%s failed=%s",
        result.get("market"),
        result.get("processed"),
        result.get("success"),
        len(result.get("failed", [])),
    )
    return result


@app.task(name="src.workers.tasks.refresh_macro_indicators", max_retries=2)
def refresh_macro_indicators():
    """BOK 거시 지표 갱신"""

    result = asyncio.run(macro_data_service.refresh_all())
    logger.info("✅ [Task] 거시 지표 갱신: %s", result)
    return result
