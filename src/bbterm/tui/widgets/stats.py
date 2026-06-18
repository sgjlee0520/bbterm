from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from bbterm.data.stats import Stats


def format_volume(value: float) -> str:
    v = float(value)
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if v >= size:
            return f"{v / size:.1f}{unit}"
    return f"{int(v)}"


def _price(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def render_stats_text(s: Stats) -> str:
    rows = [
        ("Last", _price(s.last)),
        ("Change", "n/a" if s.change is None else f"{_price(s.change)} ({_pct(s.pct_change)})"),
        ("52w High", _price(s.high_52w)),
        ("52w Low", _price(s.low_52w)),
        ("1M Return", _pct(s.ret_1m)),
        ("YTD Return", _pct(s.ret_ytd)),
        ("Avg Vol", format_volume(s.avg_volume)),
        ("Day Range", f"{_price(s.day_low)} – {_price(s.day_high)}"),
    ]
    lines = [f"  {s.symbol} — Statistics", ""]
    for label, value in rows:
        lines.append(f"  {label:<12}{value}")
    return "\n".join(lines)


class StatsView(Widget):
    DEFAULT_CSS = """
    StatsView { height: 1fr; }
    StatsView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    StatsView > Static.body { width: 100%; height: 1fr; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        yield Label("STATISTICS", classes="header")
        yield Static("  Select a symbol.", classes="body")

    def show(self, stats: Stats | None) -> None:
        body = self.query_one(".body", Static)
        if stats is None:
            body.update("  No data available.")
            return
        body.update(Text(render_stats_text(stats)))
