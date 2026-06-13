from datetime import datetime
from types import SimpleNamespace

import pandas as pd

import bbterm.data.providers.yfinance_ as yfp
from bbterm.data.providers.yfinance_ import YFinanceProvider


class StubTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_info = SimpleNamespace(last_price=110.0, previous_close=100.0)

    def history(self, start=None, end=None, interval=None):
        idx = pd.to_datetime([datetime(2026, 1, 5), datetime(2026, 1, 6)])
        return pd.DataFrame(
            {
                "Open": [1.0, 2.0],
                "High": [1.5, 2.5],
                "Low": [0.5, 1.5],
                "Close": [1.2, 2.2],
                "Volume": [100, 200],
            },
            index=idx,
        )


def test_get_bars_maps_dataframe(monkeypatch):
    monkeypatch.setattr(yfp.yf, "Ticker", StubTicker)
    bars = YFinanceProvider().get_bars(
        "AAPL", "1d", datetime(2026, 1, 1), datetime(2026, 1, 31)
    )
    assert len(bars) == 2
    assert bars[0].symbol == "AAPL"
    assert bars[0].interval == "1d"
    assert bars[0].close == 1.2
    assert bars[1].volume == 200
    assert bars[0].ts == datetime(2026, 1, 5)


def test_get_quote_maps_fast_info(monkeypatch):
    monkeypatch.setattr(yfp.yf, "Ticker", StubTicker)
    q = YFinanceProvider().get_quote("AAPL")
    assert q.price == 110.0
    assert q.prev_close == 100.0


def test_errors_degrade_to_empty(monkeypatch):
    def boom(symbol):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(yfp.yf, "Ticker", boom)
    p = YFinanceProvider()
    assert p.get_bars("AAPL", "1d", datetime(2026, 1, 1), datetime(2026, 1, 2)) == []
    assert p.get_quote("AAPL") is None
