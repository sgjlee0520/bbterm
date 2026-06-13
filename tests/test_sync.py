from datetime import datetime, timedelta

from bbterm.data.service import DataService
from bbterm.data.store import Store
from bbterm.sync import sync_watchlist
from fakes import FakeProvider, make_bars


async def test_sync_fetches_daily_bars_for_every_watchlist_symbol():
    store = Store(":memory:")
    store.set_watchlist(["AAPL", "MSFT"])
    start = datetime.now() - timedelta(days=10)
    bars = make_bars("AAPL", "1d", start=start, n=5) + make_bars(
        "MSFT", "1d", start=start, n=5
    )
    fake = FakeProvider(bars=bars)
    service = DataService(store, fake, fake, fetch_ttl=0.0)

    counts = await sync_watchlist(service, days=365)

    assert set(counts) == {"AAPL", "MSFT"}
    assert counts["AAPL"] == 5
    assert {c[0] for c in fake.bar_calls} == {"AAPL", "MSFT"}
