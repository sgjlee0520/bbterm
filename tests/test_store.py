from datetime import datetime
import pytest
from bbterm.data.models import Bar
from bbterm.data.store import Store, DEFAULT_WATCHLIST


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


def _bar(day: int, close: float = 10.0) -> Bar:
    return Bar("AAPL", "1d", datetime(2026, 1, day), 9.0, 11.0, 8.0, close, 100)


def test_upsert_and_range_query(store):
    store.upsert_bars([_bar(5), _bar(6), _bar(7)])
    got = store.get_bars("AAPL", "1d", datetime(2026, 1, 5), datetime(2026, 1, 6))
    assert [b.ts.day for b in got] == [5, 6]
    assert got[0] == _bar(5)


def test_upsert_is_idempotent_and_replaces(store):
    store.upsert_bars([_bar(5, close=10.0)])
    store.upsert_bars([_bar(5, close=99.0)])
    got = store.get_bars("AAPL", "1d", datetime(2026, 1, 1), datetime(2026, 1, 31))
    assert len(got) == 1
    assert got[0].close == 99.0


def test_coverage(store):
    assert store.coverage("AAPL", "1d") is None
    store.upsert_bars([_bar(5), _bar(9)])
    assert store.coverage("AAPL", "1d") == (datetime(2026, 1, 5), datetime(2026, 1, 9))


def test_intervals_are_separate(store):
    store.upsert_bars([_bar(5)])
    assert store.get_bars("AAPL", "1m", datetime(2026, 1, 1), datetime(2026, 1, 31)) == []


def test_watchlist_seeds_defaults_then_persists(store):
    assert store.get_watchlist() == DEFAULT_WATCHLIST
    store.set_watchlist(["TSLA", "SPY"])
    assert store.get_watchlist() == ["TSLA", "SPY"]
