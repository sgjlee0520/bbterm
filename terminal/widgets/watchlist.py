from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, ListView, ListItem
from textual.reactive import reactive
from textual.message import Message
from rich.text import Text
from terminal.data import Quote


class WatchlistItem(ListItem):
    def __init__(self, quote: Quote) -> None:
        super().__init__()
        self.quote = quote

    def compose(self) -> ComposeResult:
        yield Label(self._render_quote(self.quote))

    def _render_quote(self, q: Quote) -> Text:
        t = Text()
        t.append(f"{q.ticker:<8}", style="bold white")
        color = "green" if q.is_up else "red"
        t.append(f"{q.price:>10.2f}", style=f"bold {color}")
        sign = "+" if q.is_up else ""
        t.append(f"\n  {sign}{q.pct_change:.2f}%", style=color)
        return t

    def update_quote(self, quote: Quote) -> None:
        self.quote = quote
        self.query_one(Label).update(self._render_quote(quote))


class Watchlist(Widget):
    class TickerSelected(Message):
        def __init__(self, ticker: str) -> None:
            super().__init__()
            self.ticker = ticker

    DEFAULT_CSS = """
    Watchlist {
        width: 20;
        border-right: solid $primary;
    }
    Watchlist > Label.header {
        background: $primary;
        color: $text;
        width: 100%;
        padding: 0 1;
        text-style: bold;
    }
    Watchlist ListView {
        background: $surface;
    }
    Watchlist ListItem {
        padding: 0 1;
        height: 3;
    }
    Watchlist ListItem:hover {
        background: $boost;
    }
    Watchlist ListItem.--highlight {
        background: $accent 30%;
    }
    """

    def __init__(self, tickers: list[str]) -> None:
        super().__init__()
        self.tickers = tickers
        self._items: dict[str, WatchlistItem] = {}

    def compose(self) -> ComposeResult:
        yield Label("WATCHLIST", classes="header")
        yield ListView()

    def on_mount(self) -> None:
        self.load_quotes()

    def load_quotes(self) -> None:
        from terminal.data import get_quote
        lv = self.query_one(ListView)
        lv.clear()
        self._items.clear()
        for ticker in self.tickers:
            q = get_quote(ticker)
            if q:
                item = WatchlistItem(q)
                self._items[ticker] = item
                lv.append(item)

    def refresh_quotes(self) -> None:
        from terminal.data import get_quote
        for ticker, item in self._items.items():
            q = get_quote(ticker)
            if q:
                item.update_quote(q)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, WatchlistItem):
            self.post_message(self.TickerSelected(event.item.quote.ticker))
