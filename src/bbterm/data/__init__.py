from __future__ import annotations

from bbterm.config import Config
from bbterm.data.providers.databento_ import DatabentoProvider
from bbterm.data.providers.edgar import EdgarProvider
from bbterm.data.providers.yfinance_ import YFinanceProvider
from bbterm.data.service import DataService
from bbterm.data.store import Store


def build_service(config: Config) -> DataService:
    store = Store(config.db_path)
    yf_provider = YFinanceProvider()
    edgar = EdgarProvider()
    if config.databento_api_key:
        bars = DatabentoProvider(
            api_key=config.databento_api_key,
            dataset=config.databento_dataset,
            cost_cap_usd=config.cost_cap_usd,
        )
        return DataService(store, bars, yf_provider, edgar_provider=edgar)
    return DataService(store, yf_provider, yf_provider, edgar_provider=edgar)
