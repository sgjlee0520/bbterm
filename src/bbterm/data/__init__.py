from __future__ import annotations

from bbterm.config import Config
from bbterm.data.providers.yfinance_ import YFinanceProvider
from bbterm.data.service import DataService
from bbterm.data.store import Store


def build_service(config: Config) -> DataService:
    store = Store(config.db_path)
    yf_provider = YFinanceProvider()
    return DataService(store, yf_provider, yf_provider)
