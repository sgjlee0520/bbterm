from __future__ import annotations

import plotext as plt
from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from bbterm.data.models import Bar, Quote


class ChartPanel(Widget):
    DEFAULT_CSS = """
    ChartPanel { height: 1fr; }
    ChartPanel > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    ChartPanel > Static.plot { width: 100%; height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Label("", id="chart-header", classes="header")
        yield Static("", id="chart-plot", classes="plot")

    def show(
        self,
        symbol: str,
        period_label: str,
        bars: list[Bar],
        quote: Quote | None,
    ) -> None:
        header = self.query_one("#chart-header", Label)
        plot = self.query_one("#chart-plot", Static)

        if quote:
            color = "green" if quote.is_up else "red"
            text = Text()
            text.append(f"  {symbol}  ", style="bold white on black")
            text.append(f"  {quote.price:.2f}  ", style=f"bold {color}")
            text.append(f"  {quote.change_str}  ", style=color)
            header.update(text)
        else:
            header.update(f"  {symbol}")

        if not bars:
            plot.update("  No data available for this symbol/period.")
            return
        plot.update(self._build_plot(symbol, period_label, bars, quote))

    def _build_plot(
        self,
        symbol: str,
        period_label: str,
        bars: list[Bar],
        quote: Quote | None,
    ) -> str:
        width = max(self.size.width - 2, 40)
        height = max(self.size.height - 3, 10)

        closes = [b.close for b in bars]
        labels = [str(b.ts.date()) for b in bars]

        plt.clear_figure()
        plt.theme("dark")
        plt.plotsize(width, height)
        color = "green" if (quote and quote.is_up) else "red"
        plt.plot(closes, color=color, label=symbol)

        tick_count = min(6, len(labels))
        step = max(1, len(labels) // tick_count)
        ticks = list(range(0, len(labels), step))
        plt.xticks(ticks, [labels[i] for i in ticks])
        plt.title(f"{symbol} — {period_label}")
        return plt.build()
