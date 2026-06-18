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

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.mode = "candle"  # or "line"
        self._last: tuple | None = None  # (symbol, label, bars, quote)
        self._size_wh: tuple[int, int] | None = None  # test override

    def compose(self) -> ComposeResult:
        yield Label("", id="chart-header", classes="header")
        yield Static("", id="chart-plot", classes="plot")

    def show(
        self, symbol: str, period_label: str, bars: list[Bar], quote: Quote | None
    ) -> None:
        self._last = (symbol, period_label, bars, quote)
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

    def toggle_mode(self) -> None:
        self.mode = "line" if self.mode == "candle" else "candle"
        if self._last is not None:
            self.show(*self._last)

    def _dims(self) -> tuple[int, int]:
        if self._size_wh is not None:
            return self._size_wh
        return self.size.width, self.size.height

    def _build_plot(
        self, symbol: str, period_label: str, bars: list[Bar], quote: Quote | None
    ) -> str:
        width_raw, height_raw = self._dims()
        width = max(width_raw - 2, 40)
        height = max(height_raw - 3, 10)
        color = "green" if (quote and quote.is_up) else "red"
        dates = [b.ts.strftime("%Y-%m-%d") for b in bars]

        plt.clear_figure()
        plt.theme("dark")

        if self.mode == "line":
            plt.plotsize(width, height)
            plt.plot([b.close for b in bars], color=color, label=symbol)
            self._apply_xticks(dates)
            plt.title(f"{symbol} — {period_label} (line)")
            return plt.build()

        # candle + volume sub-panel
        vol_h = max(height // 4, 4)
        candle_h = max(height - vol_h, 8)
        plt.subplots(2, 1)
        plt.subplot(1, 1)
        plt.plotsize(width, candle_h)
        plt.date_form("Y-m-d")
        plt.candlestick(
            dates,
            {
                "Open": [b.open for b in bars],
                "High": [b.high for b in bars],
                "Low": [b.low for b in bars],
                "Close": [b.close for b in bars],
            },
        )
        plt.title(f"{symbol} — {period_label}")
        plt.subplot(2, 1)
        plt.plotsize(width, vol_h)
        plt.bar(dates, [b.volume for b in bars], color=color)
        plt.title("Volume")
        return plt.build()

    def _apply_xticks(self, dates: list[str]) -> None:
        tick_count = min(6, len(dates))
        if tick_count == 0:
            return
        step = max(1, len(dates) // tick_count)
        ticks = list(range(0, len(dates), step))
        plt.xticks(ticks, [dates[i] for i in ticks])
