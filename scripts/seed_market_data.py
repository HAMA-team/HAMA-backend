#!/usr/bin/env python
"""
시장 데이터를 사전 적재하는 CLI 스크립트.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트 경로를 import 경로에 추가
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.services import seed_market_data  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preload stock listings and historical prices into the database.")
    parser.add_argument("--market", default="KOSPI", help="Target market (KOSPI, KOSDAQ, KONEX, ALL)")
    parser.add_argument("--days", type=int, default=60, help="Number of past trading days to store")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for number of symbols")
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()
    result = await seed_market_data(
        market=args.market,
        days=args.days,
        limit=args.limit,
    )

    print("✅ 시드 완료:")
    for key, value in result.items():
        print(f"  - {key}: {value}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
