from textual.app import App, ComposeResult
from textual.widgets import Header, Footer
from textual.containers import Horizontal, Vertical
from textual.binding import Binding

from terminal.data import DEFAULT_WATCHLIST, PERIODS, get_quote
from terminal.widgets.watchlist import Watchlist
from terminal.widgets.chart import ChartPanel
from terminal.widgets.strip import TickerStrip


class BloombergApp(App):
    TITLE = "Bloomberg Terminal"
    CSS = """
    Screen {
        background: $surface;
    }
    Header {
        background: $primary;
    }
    #main {
        height: 1fr;
    }
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

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield Watchlist(DEFAULT_WATCHLIST)
            yield ChartPanel()
        yield TickerStrip()
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_strip()
        self.set_interval(60, self._refresh_strip)
        self.set_interval(300, self._refresh_watchlist)

    def on_watchlist_ticker_selected(self, message: Watchlist.TickerSelected) -> None:
        self.query_one(ChartPanel).ticker = message.ticker

    def action_refresh(self) -> None:
        self.query_one(Watchlist).refresh_quotes()
        self.query_one(ChartPanel).refresh_chart()
        self._refresh_strip()

    def action_period(self, period: str) -> None:
        self.query_one(ChartPanel).period = period

    def _refresh_strip(self) -> None:
        quotes = []
        for ticker in DEFAULT_WATCHLIST:
            q = get_quote(ticker)
            if q:
                quotes.append(q)
        self.query_one(TickerStrip).update(quotes)

    def _refresh_watchlist(self) -> None:
        self.query_one(Watchlist).refresh_quotes()
