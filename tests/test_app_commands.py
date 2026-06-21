from datetime import datetime, timedelta

from textual.widgets import ContentSwitcher

from bbterm.data.models import Quote
from bbterm.data.service import DataService
from bbterm.data.store import Store
from bbterm.tui.app import BloombergApp
from bbterm.tui.widgets.command_bar import CommandBar
from fakes import FakeProvider, make_bars


class FakeEdgar:
    name = "edgar"

    def get_facts(self, symbol):
        return {"cik": 1, "facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            {"end": "2023-12-31", "val": 100, "fy": 2023, "fp": "FY"},
        ]}}}}}

    def get_submissions(self, symbol):
        return {"cik": 1, "filings": {"recent": {
            "accessionNumber": ["0000000001-24-000001"],
            "filingDate": ["2024-01-15"], "reportDate": ["2023-12-31"],
            "form": ["10-K"], "primaryDocument": ["x.htm"],
        }}}


class FakeNews:
    name = "news"

    def get_news(self, symbol):
        return (
            b'<?xml version="1.0"?><rss version="2.0"><channel>'
            b"<item><title>Hi - X</title><link>http://x</link>"
            b"<pubDate>Wed, 18 Jun 2025 14:30:00 GMT</pubDate>"
            b'<source url="http://x">X</source></item></channel></rss>'
        )


def _app():
    bars = make_bars("SPY", "1d", start=datetime.now() - timedelta(days=400), n=300)
    fake = FakeProvider(bars=bars, quote=Quote("SPY", 101.0, 100.0))
    service = DataService(Store(":memory:"), fake, fake, fetch_ttl=0.0,
                          edgar_provider=FakeEdgar(), news_provider=FakeNews())
    return BloombergApp(service=service, watchlist=["SPY"]), service


async def _submit(pilot, app, text):
    app.query_one(CommandBar).value = text
    await app.query_one(CommandBar).action_submit()
    await pilot.pause()


async def test_add_and_remove_symbol_persists():
    app, service = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "ADD TSLA")
        assert "TSLA" in app.watchlist_symbols
        assert "TSLA" in service.store.get_watchlist()
        await _submit(pilot, app, "DEL TSLA")
        assert "TSLA" not in app.watchlist_symbols
        assert "TSLA" not in service.store.get_watchlist()


async def test_des_then_gp_switches_views():
    app, _ = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "DES")
        assert app.query_one(ContentSwitcher).current == "stats"
        await _submit(pilot, app, "GP")
        assert app.query_one(ContentSwitcher).current == "chart"


async def test_bare_ticker_loads_symbol():
    app, _ = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "AMZN")
        assert app.current_symbol == "AMZN"


async def test_cannot_remove_last_symbol():
    app, service = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "DEL SPY")
        assert app.watchlist_symbols == ["SPY"]


async def test_fa_switches_to_fundamentals_view():
    app, _ = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "FA")
        assert app.query_one(ContentSwitcher).current == "fundamentals"


async def test_fil_switches_to_filings_view():
    app, _ = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "FIL")
        assert app.query_one(ContentSwitcher).current == "filings"


async def test_n_switches_to_news_view():
    app, _ = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "N")
        assert app.query_one(ContentSwitcher).current == "news"
