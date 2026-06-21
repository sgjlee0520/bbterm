from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta

from bbterm.data.congress import filter_to_roster, parse_congress_trades
from bbterm.data.fundamentals import extract_fundamentals, parse_filings
from bbterm.data.models import (
    Bar, CongressTrade, Filing, FundamentalMetric, NewsItem, Quote,
)
from bbterm.data.news import parse_news
from bbterm.data.providers.base import BarProvider, QuoteProvider
from bbterm.data.store import Store

FETCH_TTL_SECONDS = 300.0
EDGAR_TTL_SECONDS = 86400.0
NEWS_TTL_SECONDS = 900.0
CONGRESS_TTL_SECONDS = 86400.0


def _step(interval: str) -> timedelta:
    return timedelta(days=1) if interval == "1d" else timedelta(minutes=1)


class DataService:
    def __init__(
        self,
        store: Store,
        bar_provider: BarProvider,
        quote_provider: QuoteProvider,
        fetch_ttl: float = FETCH_TTL_SECONDS,
        edgar_provider=None,
        news_provider=None,
        congress_provider=None,
    ) -> None:
        self.store = store
        self._bars = bar_provider
        self._quotes = quote_provider
        self._ttl = fetch_ttl
        self._edgar = edgar_provider
        self._news = news_provider
        self._congress = congress_provider
        self._last_fetch: dict[tuple[str, str], float] = {}

    async def get_bars(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Bar]:
        coverage = self.store.coverage(symbol, interval)
        gaps: list[tuple[datetime, datetime]] = []
        if coverage is None:
            gaps.append((start, end))
        elif not self._recently_fetched(symbol, interval):
            lo, hi = coverage
            if start < lo:
                gaps.append((start, lo - _step(interval)))
            if end > hi:
                gaps.append((hi + _step(interval), end))
        # Daily bars are timestamped at midnight while query bounds carry a
        # time-of-day, so a gap can collapse to an inverted/sub-step range the
        # provider rejects. Drop any gap that isn't a forward span.
        gaps = [(s, e) for s, e in gaps if s < e]
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

    # ---- EDGAR fundamentals / filings -------------------------------------
    def _edgar_fresh(self, cached) -> bool:
        if cached is None:
            return False
        fetched_at, _ = cached
        return (datetime.now() - fetched_at).total_seconds() < EDGAR_TTL_SECONDS

    async def get_fundamentals(self, symbol: str) -> list[FundamentalMetric]:
        cached = self.store.get_edgar_facts(symbol)
        if not self._edgar_fresh(cached):
            try:
                facts = await asyncio.to_thread(self._edgar.get_facts, symbol)
                self.store.set_edgar_facts(symbol, json.dumps(facts))
                cached = self.store.get_edgar_facts(symbol)
            except Exception:
                if cached is None:
                    raise
        _, payload = cached
        return extract_fundamentals(json.loads(payload))

    async def get_filings(self, symbol: str) -> list[Filing]:
        cached = self.store.get_edgar_filings(symbol)
        if not self._edgar_fresh(cached):
            try:
                subs = await asyncio.to_thread(self._edgar.get_submissions, symbol)
                self.store.set_edgar_filings(symbol, json.dumps(subs))
                cached = self.store.get_edgar_filings(symbol)
            except Exception:
                if cached is None:
                    raise
        _, payload = cached
        return parse_filings(json.loads(payload))

    # ---- news -------------------------------------------------------------
    def _news_fresh(self, cached) -> bool:
        if cached is None:
            return False
        fetched_at, _ = cached
        return (datetime.now() - fetched_at).total_seconds() < NEWS_TTL_SECONDS

    async def get_news(self, symbol: str) -> list[NewsItem]:
        cached = self.store.get_news(symbol)
        if not self._news_fresh(cached):
            try:
                raw = await asyncio.to_thread(self._news.get_news, symbol)
                self.store.set_news(symbol, raw.decode("utf-8", "replace"))
                cached = self.store.get_news(symbol)
            except Exception:
                pass
        if cached is None:
            return []
        _, payload = cached
        return parse_news(payload)

    # ---- congressional trades ---------------------------------------------
    @property
    def has_congress(self) -> bool:
        return self._congress is not None

    def _congress_fresh(self, cached) -> bool:
        if cached is None:
            return False
        fetched_at, _ = cached
        return (datetime.now() - fetched_at).total_seconds() < CONGRESS_TTL_SECONDS

    async def get_congress_trades(self, symbol: str) -> list[CongressTrade]:
        if self._congress is None:
            return []
        cached = self.store.get_congress(symbol)
        if not self._congress_fresh(cached):
            try:
                raw = await asyncio.to_thread(self._congress.get_congress_trades, symbol)
                self.store.set_congress(symbol, json.dumps(raw))
                cached = self.store.get_congress(symbol)
            except Exception:
                pass
        if cached is None:
            return []
        _, payload = cached
        return filter_to_roster(parse_congress_trades(json.loads(payload)))
