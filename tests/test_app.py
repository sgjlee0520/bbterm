from datetime import datetime, timedelta

from bbterm.data.models import Quote
from bbterm.data.service import DataService
from bbterm.data.store import Store
from bbterm.tui.app import BloombergApp
from bbterm.tui.widgets.chart import ChartPanel
from fakes import FakeProvider, make_bars


async def test_app_boots_and_renders_with_fake_data():
    bars = make_bars(
        "SPY", "1d", start=datetime.now() - timedelta(days=20), n=15
    )
    fake = FakeProvider(bars=bars, quote=Quote("SPY", 101.0, 100.0))
    service = DataService(Store(":memory:"), fake, fake, fetch_ttl=0.0)
    app = BloombergApp(service=service, watchlist=["SPY"])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(ChartPanel) is not None
        assert len(fake.quote_calls) >= 1
        assert len(fake.bar_calls) >= 1
