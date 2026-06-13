from datetime import datetime

import pandas as pd
import pytest

from bbterm.data.providers.base import CostCapExceeded
from bbterm.data.providers.databento_ import DatabentoProvider


class FakeStoreResult:
    def __init__(self, df):
        self._df = df

    def to_df(self):
        return self._df


class FakeDbClient:
    def __init__(self, cost=0.001, df=None):
        self._cost = cost
        self._df = df if df is not None else pd.DataFrame()
        self.cost_calls = []
        self.range_calls = []
        self.metadata = self
        self.timeseries = self

    def get_cost(self, **kwargs):
        self.cost_calls.append(kwargs)
        return self._cost

    def get_range(self, **kwargs):
        self.range_calls.append(kwargs)
        return FakeStoreResult(self._df)


def _df():
    idx = pd.to_datetime([datetime(2026, 1, 5), datetime(2026, 1, 6)])
    return pd.DataFrame(
        {
            "open": [1.0, 2.0],
            "high": [1.5, 2.5],
            "low": [0.5, 1.5],
            "close": [1.2, 2.2],
            "volume": [100, 200],
        },
        index=idx,
    )


def test_get_bars_checks_cost_then_fetches():
    client = FakeDbClient(cost=0.001, df=_df())
    provider = DatabentoProvider(
        api_key="db-x", dataset="EQUS.MINI", cost_cap_usd=1.0, client=client
    )
    bars = provider.get_bars(
        "AAPL", "1d", datetime(2026, 1, 1), datetime(2026, 1, 31)
    )
    assert len(client.cost_calls) == 1
    assert client.cost_calls[0]["schema"] == "ohlcv-1d"
    assert len(bars) == 2
    assert bars[0].close == 1.2
    assert bars[1].volume == 200
    assert bars[0].ts == datetime(2026, 1, 5)


def test_cost_above_cap_raises_without_fetching():
    client = FakeDbClient(cost=5.0, df=_df())
    provider = DatabentoProvider(
        api_key="db-x", dataset="EQUS.MINI", cost_cap_usd=1.0, client=client
    )
    with pytest.raises(CostCapExceeded) as exc:
        provider.get_bars("AAPL", "1d", datetime(2020, 1, 1), datetime(2026, 1, 1))
    assert exc.value.estimated_usd == 5.0
    assert client.range_calls == []


def test_minute_interval_uses_minute_schema():
    client = FakeDbClient(cost=0.001, df=_df())
    provider = DatabentoProvider(
        api_key="db-x", dataset="EQUS.MINI", cost_cap_usd=1.0, client=client
    )
    provider.get_bars("AAPL", "1m", datetime(2026, 1, 5), datetime(2026, 1, 6))
    assert client.cost_calls[0]["schema"] == "ohlcv-1m"
