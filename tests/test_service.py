from datetime import datetime

from bbterm.data.models import Quote
from bbterm.data.service import DataService
from bbterm.data.store import Store
from fakes import FakeProvider, make_bars

START = datetime(2026, 1, 5)
END = datetime(2026, 1, 9)


def make_service(bars=None, quote=None, ttl=0.0):
    store = Store(":memory:")
    fake = FakeProvider(bars=bars or [], quote=quote)
    return DataService(store, fake, fake, fetch_ttl=ttl), fake


async def test_empty_store_fetches_full_range_and_caches():
    svc, fake = make_service(bars=make_bars(start=START, n=5))
    got = await svc.get_bars("AAPL", "1d", START, END)
    assert len(got) == 5
    assert fake.bar_calls == [("AAPL", "1d", START, END)]
    assert svc.store.coverage("AAPL", "1d") == (START, END)


async def test_covered_range_makes_no_provider_call():
    svc, fake = make_service(bars=make_bars(start=START, n=5))
    await svc.get_bars("AAPL", "1d", START, END)
    fake.bar_calls.clear()
    got = await svc.get_bars("AAPL", "1d", START, datetime(2026, 1, 7))
    assert len(got) == 3
    assert fake.bar_calls == []


async def test_forward_gap_fetches_only_the_gap():
    svc, fake = make_service(bars=make_bars(start=START, n=10))
    await svc.get_bars("AAPL", "1d", START, END)  # caches Jan 5-9
    fake.bar_calls.clear()
    later = datetime(2026, 1, 12)
    await svc.get_bars("AAPL", "1d", START, later)
    assert len(fake.bar_calls) == 1
    _, _, gap_start, gap_end = fake.bar_calls[0]
    assert gap_start == datetime(2026, 1, 10)
    assert gap_end == later


async def test_backward_gap_fetches_only_the_gap():
    svc, fake = make_service(bars=make_bars(start=datetime(2026, 1, 1), n=10))
    await svc.get_bars("AAPL", "1d", START, END)  # caches Jan 5-9
    fake.bar_calls.clear()
    earlier = datetime(2026, 1, 2)
    await svc.get_bars("AAPL", "1d", earlier, END)
    assert len(fake.bar_calls) == 1
    _, _, gap_start, gap_end = fake.bar_calls[0]
    assert gap_start == earlier
    assert gap_end == datetime(2026, 1, 4)


async def test_fetch_ttl_suppresses_repeated_forward_fetch():
    svc, fake = make_service(bars=make_bars(start=START, n=5), ttl=300.0)
    await svc.get_bars("AAPL", "1d", START, END)
    fake.bar_calls.clear()
    await svc.get_bars("AAPL", "1d", START, datetime(2026, 1, 12))
    assert fake.bar_calls == []  # within TTL: don't re-ask for newer data


async def test_get_quote_passthrough():
    svc, fake = make_service(quote=Quote("AAPL", 110.0, 100.0))
    q = await svc.get_quote("AAPL")
    assert q.price == 110.0
    assert fake.quote_calls == ["AAPL"]
