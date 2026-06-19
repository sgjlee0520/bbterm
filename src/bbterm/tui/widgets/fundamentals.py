from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from bbterm.data.models import FundamentalMetric


def human_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    v = abs(float(value))
    for unit, size in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if v >= size:
            return f"{sign}${v / size:.2f}{unit}"
    return f"{sign}${v:.2f}"


def human_count(value: float) -> str:
    v = float(value)
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if v >= size:
            return f"{v / size:.2f}{unit}"
    return f"{int(v)}"


def _value_str(m: FundamentalMetric) -> str:
    if m.unit == "shares":
        return f"{human_count(m.value)} sh"
    return human_money(m.value)


def _yoy_str(yoy: float | None) -> str:
    if yoy is None:
        return "n/a"
    sign = "+" if yoy >= 0 else ""
    return f"{sign}{yoy:.2f}%"


def render_fundamentals_text(metrics: list[FundamentalMetric]) -> str:
    if not metrics:
        return "  No fundamentals available."
    lines = ["  Fundamentals (latest annual)", ""]
    for m in metrics:
        period = f"FY{m.fy}"
        lines.append(
            f"  {m.label:<22}{_value_str(m):>14}  {period:<8}{_yoy_str(m.yoy_pct):>9}"
        )
    return "\n".join(lines)


class FundamentalsView(Widget):
    DEFAULT_CSS = """
    FundamentalsView { height: 1fr; }
    FundamentalsView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    FundamentalsView > Static.body { width: 100%; height: 1fr; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        yield Label("FUNDAMENTALS", classes="header")
        yield Static("  Select a symbol.", classes="body")

    def show(self, metrics: list[FundamentalMetric]) -> None:
        self.query_one(".body", Static).update(
            Text(render_fundamentals_text(metrics))
        )
