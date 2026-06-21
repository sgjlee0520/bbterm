from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from bbterm.data.models import MagicMetrics
from bbterm.tui.widgets.fundamentals import human_money


def _pct(x: float | None) -> str:
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def render_magic_text(
    current_symbol: str,
    current: MagicMetrics | None,
    ranked: list[tuple[int, MagicMetrics]],
    na_symbols: list[str],
) -> str:
    lines = [f"  Magic Formula — {current_symbol}", ""]
    if current is None or current.earnings_yield is None or current.roc is None:
        lines.append(f"  {current_symbol}: not computable (ETF / financial / missing data)")
    else:
        lines.append(
            f"  {current_symbol} — Earnings Yield {_pct(current.earnings_yield)} · "
            f"ROC {_pct(current.roc)} · EV {human_money(current.ev)}"
        )
    lines += ["", "  Watchlist ranking (best = cheap + high quality)",
              f"    {'#':<4}{'Symbol':<8}{'EarnYld':<10}{'ROC':<10}"]
    for rank, m in ranked:
        lines.append(f"    {rank:<4}{m.symbol:<8}{_pct(m.earnings_yield):<10}{_pct(m.roc):<10}")
    if na_symbols:
        lines += ["", "  Not computable: " + ", ".join(na_symbols)]
    lines += ["", "  Approximate (EBIT ≈ operating income, delayed price); not advice."]
    return "\n".join(lines)


class MagicFormulaView(Widget):
    DEFAULT_CSS = """
    MagicFormulaView { height: 1fr; }
    MagicFormulaView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    MagicFormulaView > Static.body { width: 100%; height: 1fr; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        yield Label("MAGIC FORMULA", classes="header")
        yield Static("  Select a symbol.", classes="body")

    def show(
        self,
        current_symbol: str,
        current: MagicMetrics | None,
        ranked: list[tuple[int, MagicMetrics]],
        na_symbols: list[str],
    ) -> None:
        self.query_one(".body", Static).update(
            Text(render_magic_text(current_symbol, current, ranked, na_symbols))
        )
