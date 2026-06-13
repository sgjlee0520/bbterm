from __future__ import annotations

from datetime import datetime

import databento as db

from bbterm.data.models import Bar
from bbterm.data.providers.base import CostCapExceeded

_SCHEMA = {"1d": "ohlcv-1d", "1m": "ohlcv-1m"}


class DatabentoProvider:
    name = "databento"

    def __init__(
        self,
        api_key: str,
        dataset: str,
        cost_cap_usd: float,
        client: db.Historical | None = None,
    ) -> None:
        self._client = client or db.Historical(api_key)
        self._dataset = dataset
        self._cap = cost_cap_usd

    def get_bars(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Bar]:
        schema = _SCHEMA[interval]
        cost = float(
            self._client.metadata.get_cost(
                dataset=self._dataset, symbols=[symbol], schema=schema,
                start=start, end=end,
            )
        )
        if cost > self._cap:
            raise CostCapExceeded(cost, self._cap)
        result = self._client.timeseries.get_range(
            dataset=self._dataset, symbols=[symbol], schema=schema,
            start=start, end=end,
        )
        df = result.to_df()
        bars: list[Bar] = []
        for ts, row in df.iterrows():
            naive = ts.to_pydatetime().replace(tzinfo=None)
            bars.append(
                Bar(
                    symbol, interval, naive,
                    float(row["open"]), float(row["high"]),
                    float(row["low"]), float(row["close"]), int(row["volume"]),
                )
            )
        return bars
