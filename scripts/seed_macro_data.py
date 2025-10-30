#!/usr/bin/env python
"""거시 경제 지표를 DB에 적재하는 CLI"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env", override=False)

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.services import seed_macro_data  # noqa: E402


async def async_main() -> None:
    result = await seed_macro_data()
    print("✅ Macro indicators refreshed")
    for key, value in result.items():
        print(f"  - {key}: {value}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
