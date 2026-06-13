from datetime import datetime, timedelta

from bbterm.data.models import Bar, Quote


def make_bars(symbol="AAPL", interval="1d", start=None, n=5, price=100.0):
    start = start or datetime(2026, 1, 5)
    step = timedelta(days=1) if interval == "1d" else timedelta(minutes=1)
    return [
        Bar(
            symbol, interval, start + i * step,
            price + i, price + i + 1, price + i - 1, price + i + 0.5, 1000 + i,
        )
        for i in range(n)
    ]


class FakeProvider:
    """Satisfies both BarProvider and QuoteProvider; records all calls."""

    name = "fake"

    def __init__(self, bars=None, quote=None):
        self.bars = bars or []
        self.quote = quote
        self.bar_calls: list[tuple] = []
        self.quote_calls: list[str] = []

    def get_bars(self, symbol, interval, start, end):
        self.bar_calls.append((symbol, interval, start, end))
        return [
            b for b in self.bars
            if b.symbol == symbol and b.interval == interval and start <= b.ts <= end
        ]

    def get_quote(self, symbol):
        self.quote_calls.append(symbol)
        return self.quote
