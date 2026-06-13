from __future__ import annotations

from datetime import datetime, timedelta

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from bbterm.config import load_config
from bbterm.data import build_service
from bbterm.data.providers.base import CostCapExceeded
from bbterm.data.service import DataService
from bbterm.tui.widgets.chart import ChartPanel
from bbterm.tui.widgets.strip import TickerStrip
from bbterm.tui.widgets.watchlist import Watchlist

PERIODS: dict[str, tuple[str, timedelta, str]] = {
    "1d": ("1 Day", timedelta(days=1), "1m"),
    "5d": ("5 Days", timedelta(days=5), "1m"),
    "1mo": ("1 Month", timedelta(days=30), "1d"),
    "6mo": ("6 Months", timedelta(days=182), "1d"),
    "1y": ("1 Year", timedelta(days=365), "1d"),
    "5y": ("5 Years", timedelta(days=5 * 365), "1d"),
}


class BloombergApp(App):
    TITLE = "bbterm"
    CSS = """
    Screen { background: $surface; }
    #main { height: 1fr; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("1", "period('1d')", "1D"),
        Binding("2", "period('5d')", "5D"),
        Binding("3", "period('1mo')", "1M"),
        Binding("4", "period('6mo')", "6M"),
        Binding("5", "period('1y')", "1Y"),
        Binding("6", "period('5y')", "5Y"),
    ]

    def __init__(
        self,
        service: DataService | None = None,
        watchlist: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.service = service or build_service(load_config())
        self.watchlist_symbols = watchlist or self.service.store.get_watchlist()
        self.current_symbol = self.watchlist_symbols[0]
        self.current_period = "1mo"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield Watchlist()
            yield ChartPanel()
        yield TickerStrip()
        yield Footer()

    def on_mount(self) -> None:
        self.load_chart()
        self.load_quotes()
        self.set_interval(60, self.load_quotes)

    def on_watchlist_ticker_selected(
        self, message: Watchlist.TickerSelected
    ) -> None:
        self.current_symbol = message.symbol
        self.load_chart()

    def action_refresh(self) -> None:
        self.load_chart()
        self.load_quotes()

    def action_period(self, period: str) -> None:
        self.current_period = period
        self.load_chart()

    @work(exclusive=True, group="chart")
    async def load_chart(self) -> None:
        label, delta, interval = PERIODS[self.current_period]
        end = datetime.now()
        start = end - delta
        try:
            bars = await self.service.get_bars(
                self.current_symbol, interval, start, end
            )
        except CostCapExceeded as err:
            self.notify(str(err), severity="error", title="Cost cap")
            bars = self.service.store.get_bars(
                self.current_symbol, interval, start, end
            )
        except Exception as err:
            self.notify(
                f"Fetch failed ({err}); showing cached data",
                severity="warning", title="Stale data",
            )
            bars = self.service.store.get_bars(
                self.current_symbol, interval, start, end
            )
        quote = await self.service.get_quote(self.current_symbol)
        self.query_one(ChartPanel).show(self.current_symbol, label, bars, quote)

    @work(exclusive=True, group="quotes")
    async def load_quotes(self) -> None:
        quotes = []
        for symbol in self.watchlist_symbols:
            quote = await self.service.get_quote(symbol)
            if quote:
                quotes.append(quote)
        self.query_one(Watchlist).show(quotes)
        self.query_one(TickerStrip).show(quotes)


def main() -> None:
    BloombergApp().run()


if __name__ == "__main__":
    main()
