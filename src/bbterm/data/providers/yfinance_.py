from __future__ import annotations

from datetime import datetime

import yfinance as yf

from bbterm.data.models import Bar, Quote

_YF_INTERVAL = {"1d": "1d", "1m": "1m"}


class YFinanceProvider:
    """Dev/fallback provider. Unofficial Yahoo data — not for commercial use."""

    name = "yfinance"

    def get_bars(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Bar]:
        try:
            df = yf.Ticker(symbol).history(
                start=start, end=end, interval=_YF_INTERVAL[interval]
            )
        except Exception:
            return []
        bars: list[Bar] = []
        for ts, row in df.iterrows():
            naive = ts.to_pydatetime().replace(tzinfo=None)
            bars.append(
                Bar(
                    symbol, interval, naive,
                    float(row["Open"]), float(row["High"]),
                    float(row["Low"]), float(row["Close"]), int(row["Volume"]),
                )
            )
        return bars

    def get_quote(self, symbol: str) -> Quote | None:
        try:
            fast = yf.Ticker(symbol).fast_info
            price, prev = fast.last_price, fast.previous_close
            if price is None or prev is None:
                return None
            return Quote(symbol=symbol, price=float(price), prev_close=float(prev))
        except Exception:
            return None
