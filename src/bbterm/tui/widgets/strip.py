from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label

from bbterm.data.models import Quote


class TickerStrip(Widget):
    DEFAULT_CSS = """
    TickerStrip { height: 1; background: $boost; dock: bottom; }
    TickerStrip Label { width: 100%; }
    """

    def compose(self) -> ComposeResult:
        yield Label("", id="strip-label")

    def show(self, quotes: list[Quote]) -> None:
        text = Text()
        for i, q in enumerate(quotes):
            if i > 0:
                text.append("  |  ", style="dim")
            color = "green" if q.is_up else "red"
            sign = "+" if q.is_up else ""
            text.append(f"{q.symbol} ", style="bold white")
            text.append(f"{q.price:.2f} ", style=f"bold {color}")
            text.append(f"{sign}{q.pct_change:.2f}%", style=color)
        self.query_one("#strip-label", Label).update(text)
