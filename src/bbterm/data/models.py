from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Bar:
    symbol: str
    interval: str  # "1d" or "1m"
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    prev_close: float
    name: str = ""

    @property
    def change(self) -> float:
        return self.price - self.prev_close

    @property
    def pct_change(self) -> float:
        if not self.prev_close:
            return 0.0
        return self.change / self.prev_close * 100

    @property
    def is_up(self) -> bool:
        return self.change >= 0

    @property
    def change_str(self) -> str:
        sign = "+" if self.change >= 0 else ""
        return f"{sign}{self.change:.2f} ({sign}{self.pct_change:.2f}%)"


@dataclass(frozen=True)
class FundamentalMetric:
    label: str
    value: float
    unit: str
    period_end: date
    fy: int
    fp: str
    yoy_pct: float | None


@dataclass(frozen=True)
class Filing:
    form: str
    filed_date: date
    period: str
    accession: str
    url: str


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    published: datetime | None
    url: str


@dataclass(frozen=True)
class CongressTrade:
    politician: str
    chamber: str          # "house" | "senate"
    side: str             # "BUY" | "SELL"
    amount_low: float
    amount_high: float
    date: date


@dataclass(frozen=True)
class MagicMetrics:
    symbol: str
    earnings_yield: float | None   # EBIT / EV
    roc: float | None              # EBIT / tangible capital
    ev: float | None               # enterprise value (USD)
