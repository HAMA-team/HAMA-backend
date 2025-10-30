"""
Repository layer exposing database access helpers.
"""

from .stock_repository import stock_repository, StockRepository
from .stock_price_repository import stock_price_repository, StockPriceRepository
from .stock_indicator_repository import (
    stock_indicator_repository,
    StockIndicatorRepository,
)
from .macro_indicator_repository import (
    macro_indicator_repository,
    MacroIndicatorRepository,
)
from .news_repository import news_repository, NewsRepository
from .disclosure_repository import disclosure_repository, DisclosureRepository

__all__ = [
    "stock_repository",
    "StockRepository",
    "stock_price_repository",
    "StockPriceRepository",
    "stock_indicator_repository",
    "StockIndicatorRepository",
    "macro_indicator_repository",
    "MacroIndicatorRepository",
    "news_repository",
    "NewsRepository",
    "disclosure_repository",
    "DisclosureRepository",
]
