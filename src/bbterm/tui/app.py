from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import ContentSwitcher, Footer, Header

from bbterm import __version__
from bbterm.commands import (
    AddSymbol, Help, LoadSymbol, RemoveSymbol, ShowChart, ShowFilings,
    ShowFundamentals, ShowMagic, ShowNews, ShowPoliticians, ShowStats, Unknown,
    parse_command,
)
from bbterm.config import load_config
from bbterm.data import build_service
from bbterm.data.providers.base import CostCapExceeded
from bbterm.data.service import DataService
from bbterm.data.stats import compute_stats
from bbterm.tui.widgets.chart import ChartPanel
from bbterm.tui.widgets.command_bar import CommandBar
from bbterm.tui.widgets.filings import FilingsView
from bbterm.tui.widgets.fundamentals import FundamentalsView
from bbterm.data.magic_formula import rank_magic
from bbterm.tui.widgets.magic import MagicFormulaView
from bbterm.tui.widgets.news import NewsView
from bbterm.tui.widgets.politicians import PoliticiansView
from bbterm.tui.widgets.stats import StatsView
from bbterm.tui.widgets.strip import TickerStrip
from bbterm.tui.widgets.watchlist import Watchlist

PERIODS: dict[str, tuple[str, timedelta, str]] = {
    "1d": ("1 Day", timedelta(days=1), "1m"),
    "5d": ("5 Days", timedelta(days=5), "1m"),
    "1mo": ("1 Month", timedelta(days=30), "1d"),
    "6mo": ("6 Months", timedelta(days=182), "1d"),
    "1y": ("1 Year", timedelta(days=365), "1d"),
    "5y": ("5 Years", timedelta(days=5 * 365), "1d"),
}

_HELP = (
    "Commands: <ticker> load · ADD <sym> · DEL <sym> · GP chart · DES stats · "
    "FA fundamentals · FIL filings (Enter opens) · N news · POL congress · MF magic · ? help   |   Keys: :=command 1-6=period "
    "r=refresh q=quit"
)


class BloombergApp(App):
    TITLE = "bbterm"
    # Disable auto-focus so the CommandBar doesn't grab focus on boot; otherwise
    # single-key hotkeys (c/q/digits) would be typed into it. ":" focuses it.
    AUTO_FOCUS = None
    CSS = """
    Screen { background: $surface; }
    #main { height: 1fr; }
    #switcher { width: 1fr; }
    """

    BINDINGS = [
        Binding("colon", "focus_command", "Command", show=False),
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("1", "period('1d')", "1D"),
        Binding("2", "period('5d')", "5D"),
        Binding("3", "period('1mo')", "1M"),
        Binding("4", "period('6mo')", "6M"),
        Binding("5", "period('1y')", "1Y"),
        Binding("6", "period('5y')", "5Y"),
    ]

    def __init__(
        self,
        service: DataService | None = None,
        watchlist: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.service = service or build_service(load_config())
        self.watchlist_symbols = watchlist or self.service.store.get_watchlist()
        self.current_symbol = self.watchlist_symbols[0]
        self.current_period = "1mo"

    def compose(self) -> ComposeResult:
        yield Header()
        yield CommandBar()
        with Horizontal(id="main"):
            yield Watchlist()
            with ContentSwitcher(initial="chart", id="switcher"):
                yield ChartPanel(id="chart")
                yield StatsView(id="stats")
                yield FundamentalsView(id="fundamentals")
                yield FilingsView(id="filings")
                yield NewsView(id="news")
                yield PoliticiansView(id="politicians")
                yield MagicFormulaView(id="magic")
        yield TickerStrip()
        yield Footer()

    def on_mount(self) -> None:
        self.load_chart()
        self.load_quotes()
        self.set_interval(60, self.load_quotes)

    # ---- focus model -------------------------------------------------------
    def action_focus_command(self) -> None:
        self.query_one(CommandBar).focus()

    def on_command_bar_escape_pressed(
        self, _message: CommandBar.EscapePressed
    ) -> None:
        self._blur_command()

    def _blur_command(self) -> None:
        self.query_one(CommandBar).value = ""
        self.set_focus(None)

    # ---- command dispatch --------------------------------------------------
    def on_input_submitted(self, event) -> None:
        if event.input.id != "command-bar":
            return
        text = event.value.strip()
        if text:                       # empty input is a silent no-op
            self._dispatch(parse_command(text))
        self._blur_command()

    def _dispatch(self, command) -> None:
        if isinstance(command, LoadSymbol):
            self.current_symbol = command.symbol
            self._refresh_active_view()
        elif isinstance(command, AddSymbol):
            self._add_symbol(command.symbol)
        elif isinstance(command, RemoveSymbol):
            self._remove_symbol(command.symbol)
        elif isinstance(command, ShowChart):
            self.query_one("#switcher", ContentSwitcher).current = "chart"
            self.load_chart()
        elif isinstance(command, ShowStats):
            self.query_one("#switcher", ContentSwitcher).current = "stats"
            self.load_stats()
        elif isinstance(command, ShowFundamentals):
            self.query_one("#switcher", ContentSwitcher).current = "fundamentals"
            self.load_fundamentals()
        elif isinstance(command, ShowFilings):
            self.query_one("#switcher", ContentSwitcher).current = "filings"
            self.load_filings()
            self.query_one(FilingsView).query_one("OptionList").focus()
        elif isinstance(command, ShowNews):
            self.query_one("#switcher", ContentSwitcher).current = "news"
            self.load_news()
        elif isinstance(command, ShowPoliticians):
            self.query_one("#switcher", ContentSwitcher).current = "politicians"
            self.load_politicians()
        elif isinstance(command, ShowMagic):
            self.query_one("#switcher", ContentSwitcher).current = "magic"
            self.load_magic()
        elif isinstance(command, Help):
            self.notify(_HELP, title="Help", timeout=8)
        elif isinstance(command, Unknown):
            self.notify(f"Unknown command: {command.text!r}", severity="error")

    def _add_symbol(self, symbol: str) -> None:
        if symbol in self.watchlist_symbols:
            self.notify(f"{symbol} already in watchlist")
            return
        self.watchlist_symbols.append(symbol)
        self.service.store.set_watchlist(self.watchlist_symbols)
        self.notify(f"Added {symbol}")
        self.load_quotes()

    def _remove_symbol(self, symbol: str) -> None:
        if symbol not in self.watchlist_symbols:
            self.notify(f"{symbol} not in watchlist")
            return
        if len(self.watchlist_symbols) == 1:
            self.notify("Cannot remove the last symbol", severity="error")
            return
        self.watchlist_symbols.remove(symbol)
        self.service.store.set_watchlist(self.watchlist_symbols)
        if self.current_symbol == symbol:
            self.current_symbol = self.watchlist_symbols[0]
            self._refresh_active_view()
        self.notify(f"Removed {symbol}")
        self.load_quotes()

    def _refresh_active_view(self) -> None:
        current = self.query_one("#switcher", ContentSwitcher).current
        if current == "stats":
            self.load_stats()
        elif current == "fundamentals":
            self.load_fundamentals()
        elif current == "filings":
            self.load_filings()
        elif current == "news":
            self.load_news()
        elif current == "politicians":
            self.load_politicians()
        elif current == "magic":
            self.load_magic()
        else:
            self.load_chart()

    # ---- existing actions --------------------------------------------------
    def on_watchlist_ticker_selected(
        self, message: Watchlist.TickerSelected
    ) -> None:
        self.current_symbol = message.symbol
        self._refresh_active_view()

    def action_refresh(self) -> None:
        self._refresh_active_view()
        self.load_quotes()

    def action_period(self, period: str) -> None:
        self.current_period = period
        self.load_chart()

    # ---- workers -----------------------------------------------------------
    async def _bars_for(self, interval: str, delta: timedelta):
        end = datetime.now()
        start = end - delta
        try:
            return await self.service.get_bars(
                self.current_symbol, interval, start, end
            )
        except CostCapExceeded as err:
            self.notify(str(err), severity="error", title="Cost cap")
        except Exception as err:
            self.notify(
                f"Fetch failed ({err}); showing cached data",
                severity="warning", title="Stale data",
            )
        return self.service.store.get_bars(self.current_symbol, interval, start, end)

    @work(exclusive=True, group="chart")
    async def load_chart(self) -> None:
        label, delta, interval = PERIODS[self.current_period]
        bars = await self._bars_for(interval, delta)
        quote = await self.service.get_quote(self.current_symbol)
        self.query_one(ChartPanel).show(self.current_symbol, label, bars, quote)

    @work(exclusive=True, group="stats")
    async def load_stats(self) -> None:
        bars = await self._bars_for("1d", timedelta(days=365))
        quote = await self.service.get_quote(self.current_symbol)
        self.query_one(StatsView).show(compute_stats(bars, quote))

    @work(exclusive=True, group="fundamentals")
    async def load_fundamentals(self) -> None:
        try:
            metrics = await self.service.get_fundamentals(self.current_symbol)
        except Exception as err:
            self.notify(f"EDGAR unavailable ({err})", severity="warning")
            metrics = []
        self.query_one(FundamentalsView).show(metrics)

    @work(exclusive=True, group="filings")
    async def load_filings(self) -> None:
        try:
            filings = await self.service.get_filings(self.current_symbol)
        except Exception as err:
            self.notify(f"EDGAR unavailable ({err})", severity="warning")
            filings = []
        self.query_one(FilingsView).show(filings)

    @work(exclusive=True, group="news")
    async def load_news(self) -> None:
        try:
            items = await self.service.get_news(self.current_symbol)
        except Exception as err:
            self.notify(f"News unavailable ({err})", severity="warning")
            items = []
        self.query_one(NewsView).show(items)

    @work(exclusive=True, group="politicians")
    async def load_politicians(self) -> None:
        try:
            trades = await self.service.get_congress_trades(self.current_symbol)
        except Exception as err:
            self.notify(f"Congress data unavailable ({err})", severity="warning")
            trades = []
        self.query_one(PoliticiansView).show(trades, has_key=self.service.has_congress)

    @work(exclusive=True, group="magic")
    async def load_magic(self) -> None:
        try:
            current = await self.service.get_magic(self.current_symbol)
            results = {s: await self.service.get_magic(s) for s in self.watchlist_symbols}
        except Exception as err:
            self.notify(f"Magic Formula unavailable ({err})", severity="warning")
            current, results = None, {}
        computable = [m for m in results.values() if m is not None]
        na = [s for s, m in results.items() if m is None]
        ranked = rank_magic(computable)
        self.query_one(MagicFormulaView).show(self.current_symbol, current, ranked, na)

    @work(exclusive=True, group="quotes")
    async def load_quotes(self) -> None:
        quotes = []
        for symbol in self.watchlist_symbols:
            quote = await self.service.get_quote(symbol)
            if quote:
                quotes.append(quote)
        self.query_one(Watchlist).show(quotes)
        self.query_one(TickerStrip).show(quotes)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="bbterm",
        description="A local, keyboard-driven Bloomberg-style market terminal.",
    )
    parser.add_argument(
        "--version", action="version", version=f"bbterm {__version__}"
    )
    parser.parse_args(argv)
    BloombergApp().run()


if __name__ == "__main__":
    main()
