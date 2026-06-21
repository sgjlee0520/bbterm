from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from bbterm.data.congress import summarize
from bbterm.data.models import CongressTrade


def _net_str(net: float) -> str:
    sign = "+" if net >= 0 else "-"
    v = abs(net)
    if v >= 1e6:
        return f"{sign}${v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{sign}${v / 1e3:.0f}K"
    return f"{sign}${v:.0f}"


def render_politicians_text(trades: list[CongressTrade], has_key: bool = True) -> str:
    if not has_key:
        return "  Set LAMBDA_API_KEY (a free Lambda Finance key) to enable politician trades."
    if not trades:
        return "  No congressional trades for this symbol."
    summaries = {s.politician: s for s in summarize(trades)}
    grouped: dict[str, list[CongressTrade]] = {}
    for t in trades:
        grouped.setdefault(t.politician, []).append(t)
    lines = ["  Congressional trades (amounts are disclosed ranges; net is approximate)", ""]
    for name, ts in grouped.items():
        s = summaries[name]
        lines.append(
            f"  {name} ({ts[0].chamber}) — {s.n_buys} buys · {s.n_sells} sells · "
            f"net ≈ {_net_str(s.net_estimate)} (est.)"
        )
        for t in ts:
            lines.append(
                f"      {t.side:<5}${t.amount_low:,.0f} - ${t.amount_high:,.0f}   "
                f"{t.date.isoformat()}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


class PoliticiansView(Widget):
    DEFAULT_CSS = """
    PoliticiansView { height: 1fr; }
    PoliticiansView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    PoliticiansView > Static.body { width: 100%; height: 1fr; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        yield Label("CONGRESS", classes="header")
        yield Static("  Select a symbol.", classes="body")

    def show(self, trades: list[CongressTrade], has_key: bool = True) -> None:
        self.query_one(".body", Static).update(
            Text(render_politicians_text(trades, has_key))
        )
