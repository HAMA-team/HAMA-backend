#!/usr/bin/env python
"""
지정한 시장의 종목들에 대해 과거 주가 데이터를 선적재합니다.

기본 설정은 KOSPI/KOSDAQ 모든 종목의 최근 1년분(365일)을 pykrx로부터
조회하여 PostgreSQL `stock_prices` 테이블과 Redis 캐시에 저장합니다.
"""

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed historical OHLCV data for Korean markets."
    )
    parser.add_argument(
        "--market",
        default="KOSPI,KOSDAQ",
        help="대상 시장 (콤마 구분, 예: KOSPI,KOSDAQ,KONEX)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="조회 일수 (기본 365일 ≒ 최근 1년)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="(옵션) 테스트 용도로 상위 N개 종목만 처리",
    )
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()

    root_dir = Path(__file__).resolve().parents[1]
    load_dotenv(root_dir / ".env", override=False)

    if str(root_dir) not in __import__("sys").path:
        __import__("sys").path.append(str(root_dir))

    # 지연 로딩 (위에서 sys.path 조정 이후 import)
    from src.services.stock_data_service import (
        update_recent_prices_for_market,
        stock_data_service,
    )

    markets = [m.strip().upper() for m in args.market.split(",") if m.strip()]
    if not markets:
        raise ValueError("최소 하나 이상의 시장을 지정해야 합니다.")

    print(
        f"🚀 Price seeding start | markets={markets}, days={args.days}, limit={args.limit}"
    )

    for market in markets:
        print(f"\n=== {market} ===")
        listing = await stock_data_service.get_stock_listing(market)
        if listing is None or listing.empty:
            print(f"⚠️ {market}: 종목 리스트를 불러오지 못했습니다. 건너뜁니다.")
            continue

        summary = await update_recent_prices_for_market(
            market=market,
            days=args.days,
            limit=args.limit,
        )

        processed = summary.get("processed", 0)
        success = summary.get("success", 0)
        failed = summary.get("failed", [])
        print(
            f"✅ 완료: 처리 {processed}건, 성공 {success}건, 실패 {len(failed)}건"
        )
        if failed:
            sample = failed[:10]
            print(f"   실패 샘플({len(sample)}): {sample}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
