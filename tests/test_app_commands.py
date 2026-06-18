from datetime import datetime, timedelta

from textual.widgets import ContentSwitcher

from bbterm.data.models import Quote
from bbterm.data.service import DataService
from bbterm.data.store import Store
from bbterm.tui.app import BloombergApp
from bbterm.tui.widgets.chart import ChartPanel
from bbterm.tui.widgets.command_bar import CommandBar
from fakes import FakeProvider, make_bars


def _app():
    bars = make_bars("SPY", "1d", start=datetime.now() - timedelta(days=400), n=300)
    fake = FakeProvider(bars=bars, quote=Quote("SPY", 101.0, 100.0))
    service = DataService(Store(":memory:"), fake, fake, fetch_ttl=0.0)
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


async def test_toggle_chart_mode_binding():
    app, _ = _app()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(ChartPanel).mode == "candle"
        await pilot.press("c")
        assert app.query_one(ChartPanel).mode == "line"


async def test_cannot_remove_last_symbol():
    app, service = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "DEL SPY")
        assert app.watchlist_symbols == ["SPY"]
