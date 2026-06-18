from datetime import datetime, timedelta

from bbterm.data.models import Bar, Quote
from bbterm.data.stats import compute_stats, Stats


def _bars(n, start=datetime(2026, 1, 2), price=100.0, step_days=1):
    out = []
    for i in range(n):
        c = price + i
        out.append(Bar("AAPL", "1d", start + timedelta(days=i * step_days),
                       c - 0.5, c + 1.0, c - 1.0, c, 1_000_000 + i))
    return out


def test_full_history_fields():
    bars = _bars(30)
    quote = Quote("AAPL", 200.0, 128.0)
    s = compute_stats(bars, quote)
    assert isinstance(s, Stats)
    assert s.symbol == "AAPL"
    assert s.last == 200.0                       # from quote
    assert s.change == 72.0                       # 200 - 128
    assert s.high_52w == max(b.high for b in bars)
    assert s.low_52w == min(b.low for b in bars)
    assert s.day_high == bars[-1].high
    assert s.day_low == bars[-1].low
    # 1M return uses close 21 sessions back: bars[-1].close vs bars[-22].close
    assert s.ret_1m is not None


def test_last_falls_back_to_last_bar_without_quote():
    bars = _bars(5)
    s = compute_stats(bars, None)
    assert s.last == bars[-1].close
    assert s.change is None
    assert s.pct_change is None


def test_short_history_yields_none_for_1m():
    bars = _bars(10)            # < 22 bars
    s = compute_stats(bars, None)
    assert s.ret_1m is None


def test_ytd_uses_first_bar_of_latest_year():
    prev = _bars(5, start=datetime(2025, 12, 26), price=50.0)   # 2025
    cur = _bars(10, start=datetime(2026, 1, 2), price=100.0)    # 2026
    bars = prev + cur
    s = compute_stats(bars, None)
    expected = (bars[-1].close / cur[0].close - 1) * 100
    assert s.ret_ytd == expected


def test_empty_bars_is_safe():
    s = compute_stats([], None)
    assert s is None
