#!/usr/bin/env python
"""pykrx 기반 종목/시세를 DB에 적재하는 CLI"""

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env", override=False)

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.services import seed_market_data  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preload market listings and price history into the database.")
    parser.add_argument("--market", default="KOSPI", help="Target market (KOSPI, KOSDAQ, KONEX, ALL)")
    parser.add_argument("--days", type=int, default=60, help="Number of past trading days to fetch")
    parser.add_argument("--limit", type=int, default=None, help="Optional symbol limit (for testing)")
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()
    result = await seed_market_data(market=args.market, days=args.days, limit=args.limit)
    print("✅ Market data seeded")
    for key, value in result.items():
        print(f"  - {key}: {value}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
