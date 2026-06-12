from textual.widget import Widget
from textual.app import ComposeResult
from textual.widgets import Label
from rich.text import Text
from terminal.data import Quote


class TickerStrip(Widget):
    DEFAULT_CSS = """
    TickerStrip {
        height: 1;
        background: $boost;
        dock: bottom;
    }
    TickerStrip Label {
        width: 100%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("", id="strip-label")

    def update(self, quotes: list[Quote]) -> None:
        t = Text()
        for i, q in enumerate(quotes):
            if i > 0:
                t.append("  |  ", style="dim")
            color = "green" if q.is_up else "red"
            sign = "+" if q.is_up else ""
            t.append(f"{q.ticker} ", style="bold white")
            t.append(f"{q.price:.2f} ", style=f"bold {color}")
            t.append(f"{sign}{q.pct_change:.2f}%", style=color)
        self.query_one("#strip-label", Label).update(t)
