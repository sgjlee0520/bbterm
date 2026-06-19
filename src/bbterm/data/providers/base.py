from __future__ import annotations

from datetime import datetime
from typing import Protocol

from bbterm.data.models import Bar, Quote


class CostCapExceeded(Exception):
    def __init__(self, estimated_usd: float, cap_usd: float) -> None:
        self.estimated_usd = estimated_usd
        self.cap_usd = cap_usd
        super().__init__(
            f"estimated cost ${estimated_usd:.4f} exceeds cap ${cap_usd:.2f}"
        )


class BarProvider(Protocol):
    name: str

    def get_bars(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Bar]: ...


class QuoteProvider(Protocol):
    name: str

    def get_quote(self, symbol: str) -> Quote | None: ...


class FundamentalsProvider(Protocol):
    name: str

    def get_facts(self, symbol: str) -> dict: ...


class FilingsProvider(Protocol):
    name: str

    def get_submissions(self, symbol: str) -> dict: ...
