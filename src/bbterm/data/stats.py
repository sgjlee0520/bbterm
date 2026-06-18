from __future__ import annotations

from dataclasses import dataclass

from bbterm.data.models import Bar, Quote

_ONE_MONTH_SESSIONS = 21


@dataclass(frozen=True)
class Stats:
    symbol: str
    last: float
    change: float | None
    pct_change: float | None
    high_52w: float
    low_52w: float
    ret_1m: float | None
    ret_ytd: float | None
    avg_volume: float
    day_low: float
    day_high: float


def compute_stats(bars: list[Bar], quote: Quote | None) -> Stats | None:
    if not bars:
        return None
    last_bar = bars[-1]
    last = quote.price if quote else last_bar.close
    change = quote.change if quote else None
    pct_change = quote.pct_change if quote else None

    ret_1m = None
    if len(bars) >= _ONE_MONTH_SESSIONS + 1:
        ref = bars[-(_ONE_MONTH_SESSIONS + 1)].close
        if ref:
            ret_1m = (last_bar.close / ref - 1) * 100

    year = last_bar.ts.year
    ytd_ref = next((b.close for b in bars if b.ts.year == year), None)
    ret_ytd = None
    if ytd_ref:
        ret_ytd = (last_bar.close / ytd_ref - 1) * 100

    return Stats(
        symbol=last_bar.symbol,
        last=last,
        change=change,
        pct_change=pct_change,
        high_52w=max(b.high for b in bars),
        low_52w=min(b.low for b in bars),
        ret_1m=ret_1m,
        ret_ytd=ret_ytd,
        avg_volume=sum(b.volume for b in bars) / len(bars),
        day_low=last_bar.low,
        day_high=last_bar.high,
    )
