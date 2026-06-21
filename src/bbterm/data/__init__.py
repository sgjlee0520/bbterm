from __future__ import annotations

import sys

from bbterm.config import Config
from bbterm.data.providers.edgar import EdgarProvider
from bbterm.data.providers.lambdafin_ import CongressProvider
from bbterm.data.providers.news import NewsProvider
from bbterm.data.providers.yfinance_ import YFinanceProvider
from bbterm.data.service import DataService
from bbterm.data.store import Store


def build_service(config: Config) -> DataService:
    store = Store(config.db_path)
    yf_provider = YFinanceProvider()
    edgar = EdgarProvider()
    news = NewsProvider()
    congress = (
        CongressProvider(api_key=config.lambda_api_key)
        if config.lambda_api_key else None
    )
    if config.databento_api_key:
        try:
            from bbterm.data.providers.databento_ import DatabentoProvider
        except ImportError:
            print(
                "DATABENTO_API_KEY is set but the 'databento' package is not "
                "installed. Run: pip install 'bbterm[databento]'. "
                "Falling back to yfinance.",
                file=sys.stderr,
            )
        else:
            bars = DatabentoProvider(
                api_key=config.databento_api_key,
                dataset=config.databento_dataset,
                cost_cap_usd=config.cost_cap_usd,
            )
            return DataService(store, bars, yf_provider, edgar_provider=edgar, news_provider=news, congress_provider=congress)
    return DataService(store, yf_provider, yf_provider, edgar_provider=edgar, news_provider=news, congress_provider=congress)
