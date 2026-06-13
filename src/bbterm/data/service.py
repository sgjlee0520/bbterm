from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta

from bbterm.data.models import Bar, Quote
from bbterm.data.providers.base import BarProvider, QuoteProvider
from bbterm.data.store import Store

FETCH_TTL_SECONDS = 300.0


def _step(interval: str) -> timedelta:
    return timedelta(days=1) if interval == "1d" else timedelta(minutes=1)


class DataService:
    def __init__(
        self,
        store: Store,
        bar_provider: BarProvider,
        quote_provider: QuoteProvider,
        fetch_ttl: float = FETCH_TTL_SECONDS,
    ) -> None:
        self.store = store
        self._bars = bar_provider
        self._quotes = quote_provider
        self._ttl = fetch_ttl
        self._last_fetch: dict[tuple[str, str], float] = {}

    async def get_bars(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Bar]:
        coverage = self.store.coverage(symbol, interval)
        gaps: list[tuple[datetime, datetime]] = []
        if coverage is None:
            gaps.append((start, end))
        else:
            lo, hi = coverage
            if start < lo:
                gaps.append((start, lo - _step(interval)))
            if end > hi and not self._recently_fetched(symbol, interval):
                gaps.append((hi + _step(interval), end))
        for gap_start, gap_end in gaps:
            fetched = await asyncio.to_thread(
                self._bars.get_bars, symbol, interval, gap_start, gap_end
            )
            self.store.upsert_bars(fetched)
            self._last_fetch[(symbol, interval)] = time.monotonic()
        return self.store.get_bars(symbol, interval, start, end)

    async def get_quote(self, symbol: str) -> Quote | None:
        return await asyncio.to_thread(self._quotes.get_quote, symbol)

    def _recently_fetched(self, symbol: str, interval: str) -> bool:
        if self._ttl <= 0:
            return False
        last = self._last_fetch.get((symbol, interval))
        return last is not None and (time.monotonic() - last) < self._ttl
