import plotext as plt
from textual.widget import Widget
from textual.reactive import reactive
from textual.app import ComposeResult
from textual.widgets import Label, Static
from rich.text import Text
from terminal.data import get_history, get_quote, PERIODS


class ChartPanel(Widget):
    ticker: reactive[str] = reactive("SPY")
    period: reactive[str] = reactive("1mo")

    DEFAULT_CSS = """
    ChartPanel {
        height: 1fr;
    }
    ChartPanel > Label.header {
        background: $primary;
        color: $text;
        width: 100%;
        padding: 0 1;
        text-style: bold;
    }
    ChartPanel > Static.plot {
        width: 100%;
        height: 1fr;
    }
    ChartPanel > Label.period-bar {
        width: 100%;
        padding: 0 1;
        background: $boost;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("", id="chart-header", classes="header")
        yield Static("", id="chart-plot", classes="plot")
        yield Label(self._period_bar(), id="period-bar", classes="period-bar")

    def on_mount(self) -> None:
        self.refresh_chart()

    def watch_ticker(self, ticker: str) -> None:
        self.refresh_chart()

    def watch_period(self, period: str) -> None:
        self.refresh_chart()

    def refresh_chart(self) -> None:
        q = get_quote(self.ticker)
        df = get_history(self.ticker, self.period)

        header = self.query_one("#chart-header", Label)
        plot = self.query_one("#chart-plot", Static)

        if q:
            color = "green" if q.is_up else "red"
            t = Text()
            t.append(f"  {self.ticker}  ", style="bold white on black")
            t.append(f"  {q.price:.2f}  ", style=f"bold {color}")
            t.append(f"  {q.change_str}  ", style=color)
            t.append(f"  {q.name}", style="dim white")
            header.update(t)
        else:
            header.update(f"  {self.ticker}  (no data)")

        if df is not None:
            rendered = self._render_chart(df, q)
            plot.update(rendered)
        else:
            plot.update("  No data available for this ticker/period.")

        self.query_one("#period-bar", Label).update(self._period_bar())

    def _render_chart(self, df, quote) -> str:
        size = self.size
        w = max(size.width - 2, 40)
        h = max(size.height - 4, 10)

        closes = df["Close"].tolist()
        dates = [str(d.date()) for d in df.index]

        plt.clear_figure()
        plt.theme("dark")
        plt.plotsize(w, h)

        color = "green" if (quote and quote.is_up) else "red"
        plt.plot(closes, color=color, label=self.ticker)

        tick_count = min(6, len(dates))
        step = max(1, len(dates) // tick_count)
        xticks = list(range(0, len(dates), step))
        xlabels = [dates[i] for i in xticks]
        plt.xticks(xticks, xlabels)

        period_label = next(
            (label for key, (p, label) in PERIODS.items() if p == self.period),
            self.period,
        )
        plt.title(f"{self.ticker} — {period_label}")
        plt.ylabel("Price (USD)")

        return plt.build()

    def _period_bar(self) -> Text:
        t = Text()
        t.append("  Periods: ", style="dim")
        for key, (p, label) in PERIODS.items():
            if p == self.period:
                t.append(f" [{key}]{label} ", style="bold white on $primary")
            else:
                t.append(f" [{key}]{label} ", style="dim")
        return t
