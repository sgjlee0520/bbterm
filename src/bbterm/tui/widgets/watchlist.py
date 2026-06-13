from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView

from bbterm.data.models import Quote


def _render_quote(q: Quote) -> Text:
    text = Text()
    text.append(f"{q.symbol:<8}", style="bold white")
    color = "green" if q.is_up else "red"
    text.append(f"{q.price:>10.2f}", style=f"bold {color}")
    sign = "+" if q.is_up else ""
    text.append(f"\n  {sign}{q.pct_change:.2f}%", style=color)
    return text


class WatchlistItem(ListItem):
    def __init__(self, quote: Quote) -> None:
        super().__init__()
        self.quote = quote

    def compose(self) -> ComposeResult:
        yield Label(_render_quote(self.quote))

    def update_quote(self, quote: Quote) -> None:
        self.quote = quote
        self.query_one(Label).update(_render_quote(quote))


class Watchlist(Widget):
    class TickerSelected(Message):
        def __init__(self, symbol: str) -> None:
            super().__init__()
            self.symbol = symbol

    DEFAULT_CSS = """
    Watchlist { width: 20; border-right: solid $primary; }
    Watchlist > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    Watchlist ListView { background: $surface; }
    Watchlist ListItem { padding: 0 1; height: 3; }
    Watchlist ListItem.--highlight { background: $accent 30%; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._items: dict[str, WatchlistItem] = {}

    def compose(self) -> ComposeResult:
        yield Label("WATCHLIST", classes="header")
        yield ListView()

    def show(self, quotes: list[Quote]) -> None:
        symbols = [q.symbol for q in quotes]
        if symbols != list(self._items.keys()):
            list_view = self.query_one(ListView)
            list_view.clear()
            self._items.clear()
            for q in quotes:
                item = WatchlistItem(q)
                self._items[q.symbol] = item
                list_view.append(item)
        else:
            for q in quotes:
                self._items[q.symbol].update_quote(q)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, WatchlistItem):
            self.post_message(self.TickerSelected(event.item.quote.symbol))
