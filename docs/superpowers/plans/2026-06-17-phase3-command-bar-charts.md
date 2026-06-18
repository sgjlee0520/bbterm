# Phase 3 Implementation Plan — Command Bar, Candles, Stats, Watchlist Editing

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hybrid command bar, candlestick+volume charts (line toggle), a bar-derived stats (DES) panel, persisted watchlist editing, and a compiled LaTeX user guide to bbterm.

**Architecture:** Two pure modules (`commands.parse_command`, `data/stats.compute_stats`) hold all logic and are unit-tested with zero UI. The TUI wires a `CommandBar` (an `Input`) and a `ContentSwitcher` (ChartPanel ⇄ StatsView) into the existing app; app-level hotkeys fire only when the command bar is unfocused. No new data sources — stats and candles use cached OHLCV.

**Tech Stack:** Python 3.11+ (running 3.14), Textual 8.x, plotext 5.3, DuckDB, pytest. LaTeX via `pdflatex` (TeX Live 2025, verified present).

**Conventions:** run from `/Users/slee/bloomberg`; use `.venv/bin/python -m pytest` and `.venv/bin/...`. No network or credits are needed for any task in this plan (all tests use the fake provider; stats/candles read cached or synthetic bars).

**Verified API facts (don't re-discover):**
- `plt.candlestick(dates, data)` where `dates` is a list of strings (set `plt.date_form("Y-m-d")`) and `data` is `{"Open":[...],"High":[...],"Low":[...],"Close":[...]}`.
- Volume sub-panel: `plt.subplots(2,1)`, `plt.subplot(1,1)` for candles, `plt.subplot(2,1)` for `plt.bar(dates, volumes)`, then one `plt.build()`.
- `from textual.widgets import ContentSwitcher`. Switch with `switcher.current = "chart" | "stats"`.
- Textual key name for `:` is `"colon"`. A focused `Input` swallows printable keys, so app `BINDINGS` (q/c/digits) don't fire while the bar is focused — this is what makes the focus model work.

---

### Task 1: Command parser (`commands.py`)

**Files:**
- Create: `src/bbterm/commands.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_commands.py
import pytest
from bbterm.commands import (
    parse_command, LoadSymbol, AddSymbol, RemoveSymbol,
    ShowChart, ShowStats, Help, Unknown,
)


@pytest.mark.parametrize("text,expected", [
    ("AAPL", LoadSymbol("AAPL")),
    ("  aapl  ", LoadSymbol("AAPL")),
    ("BRK.B", LoadSymbol("BRK.B")),
    ("BTC-USD", LoadSymbol("BTC-USD")),
    ("ADD TSLA", AddSymbol("TSLA")),
    ("add tsla", AddSymbol("TSLA")),
    ("DEL SPY", RemoveSymbol("SPY")),
    ("REMOVE SPY", RemoveSymbol("SPY")),
    ("GP", ShowChart()),
    ("DES", ShowStats()),
    ("?", Help()),
    ("HELP", Help()),
])
def test_parse_known_forms(text, expected):
    assert parse_command(text) == expected


@pytest.mark.parametrize("text", [
    "", "   ",
    "ADD",            # verb missing required arg
    "DEL",
    "this is not a command",
    "@#$",
    "TOOLONGSYM",     # >6 chars, not a verb
])
def test_parse_unknown_or_empty(text):
    result = parse_command(text)
    assert isinstance(result, Unknown)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_commands.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bbterm.commands'`

- [ ] **Step 3: Write the implementation**

```python
# src/bbterm/commands.py
from __future__ import annotations

import re
from dataclasses import dataclass

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,6}([.\-][A-Z0-9]{1,4})?$")


@dataclass(frozen=True)
class LoadSymbol:
    symbol: str


@dataclass(frozen=True)
class AddSymbol:
    symbol: str


@dataclass(frozen=True)
class RemoveSymbol:
    symbol: str


@dataclass(frozen=True)
class ShowChart:
    pass


@dataclass(frozen=True)
class ShowStats:
    pass


@dataclass(frozen=True)
class Help:
    pass


@dataclass(frozen=True)
class Unknown:
    text: str


def _is_symbol(token: str) -> bool:
    return bool(_SYMBOL_RE.match(token))


def parse_command(text: str):
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return Unknown(text)
    parts = cleaned.split(" ")
    verb = parts[0].upper()
    arg = parts[1].upper() if len(parts) > 1 else None

    if verb in ("ADD",):
        return AddSymbol(arg) if arg and _is_symbol(arg) else Unknown(text)
    if verb in ("DEL", "REMOVE"):
        return RemoveSymbol(arg) if arg and _is_symbol(arg) else Unknown(text)
    if verb == "GP":
        return ShowChart()
    if verb == "DES":
        return ShowStats()
    if verb in ("?", "HELP"):
        return Help()
    if arg is None and _is_symbol(verb):
        return LoadSymbol(verb)
    return Unknown(text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_commands.py -v`
Expected: all parametrized cases pass.

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/commands.py tests/test_commands.py
git commit -m "feat: hybrid command parser (parse_command)"
```

---

### Task 2: Stats computation (`data/stats.py`)

**Files:**
- Create: `src/bbterm/data/stats.py`
- Test: `tests/test_stats.py`

Returns are anchored on `bars[-1].close` (not the live quote) so historical math
is consistent; `last`/`change` use the quote when present. 1M = 21 trading
sessions back; YTD = first bar whose year equals the latest bar's year.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_stats.py
from datetime import datetime, timedelta

from bbterm.data.models import Bar, Quote
from bbterm.data.stats import compute_stats, Stats


def _bars(n, start=datetime(2026, 1, 2), price=100.0, step_days=1):
    out = []
    for i in range(n):
        c = price + i
        out.append(Bar("AAPL", "1d", start + timedelta(days=i * step_days),
                       c - 0.5, c + 1.0, c - 1.0, c, 1_000_000 + i))
    return out


def test_full_history_fields():
    bars = _bars(30)
    quote = Quote("AAPL", 200.0, 128.0)
    s = compute_stats(bars, quote)
    assert isinstance(s, Stats)
    assert s.symbol == "AAPL"
    assert s.last == 200.0                       # from quote
    assert s.change == 72.0                       # 200 - 128
    assert s.high_52w == max(b.high for b in bars)
    assert s.low_52w == min(b.low for b in bars)
    assert s.day_high == bars[-1].high
    assert s.day_low == bars[-1].low
    # 1M return uses close 21 sessions back: bars[-1].close vs bars[-22].close
    assert s.ret_1m is not None


def test_last_falls_back_to_last_bar_without_quote():
    bars = _bars(5)
    s = compute_stats(bars, None)
    assert s.last == bars[-1].close
    assert s.change is None
    assert s.pct_change is None


def test_short_history_yields_none_for_1m():
    bars = _bars(10)            # < 22 bars
    s = compute_stats(bars, None)
    assert s.ret_1m is None


def test_ytd_uses_first_bar_of_latest_year():
    prev = _bars(5, start=datetime(2025, 12, 26), price=50.0)   # 2025
    cur = _bars(10, start=datetime(2026, 1, 2), price=100.0)    # 2026
    bars = prev + cur
    s = compute_stats(bars, None)
    expected = (bars[-1].close / cur[0].close - 1) * 100
    assert s.ret_ytd == expected


def test_empty_bars_is_safe():
    s = compute_stats([], None)
    assert s is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bbterm.data.stats'`

- [ ] **Step 3: Write the implementation**

```python
# src/bbterm/data/stats.py
from __future__ import annotations

from dataclasses import dataclass

from bbterm.data.models import Bar, Quote

_ONE_MONTH_SESSIONS = 21


@dataclass(frozen=True)
class Stats:
    symbol: str
    last: float
    change: float | None
    pct_change: float | None
    high_52w: float
    low_52w: float
    ret_1m: float | None
    ret_ytd: float | None
    avg_volume: float
    day_low: float
    day_high: float


def compute_stats(bars: list[Bar], quote: Quote | None) -> Stats | None:
    if not bars:
        return None
    last_bar = bars[-1]
    last = quote.price if quote else last_bar.close
    change = quote.change if quote else None
    pct_change = quote.pct_change if quote else None

    ret_1m = None
    if len(bars) >= _ONE_MONTH_SESSIONS + 1:
        ref = bars[-(_ONE_MONTH_SESSIONS + 1)].close
        if ref:
            ret_1m = (last_bar.close / ref - 1) * 100

    year = last_bar.ts.year
    ytd_ref = next((b.close for b in bars if b.ts.year == year), None)
    ret_ytd = None
    if ytd_ref:
        ret_ytd = (last_bar.close / ytd_ref - 1) * 100

    return Stats(
        symbol=last_bar.symbol,
        last=last,
        change=change,
        pct_change=pct_change,
        high_52w=max(b.high for b in bars),
        low_52w=min(b.low for b in bars),
        ret_1m=ret_1m,
        ret_ytd=ret_ytd,
        avg_volume=sum(b.volume for b in bars) / len(bars),
        day_low=last_bar.low,
        day_high=last_bar.high,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_stats.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/stats.py tests/test_stats.py
git commit -m "feat: compute_stats — bar-derived statistics for DES panel"
```

---

### Task 3: Candlestick + volume chart with line toggle (`chart.py`)

**Files:**
- Modify: `src/bbterm/tui/widgets/chart.py`
- Test: `tests/test_chart_render.py`

The widget gains a `mode` ("candle" default, "line") and caches the last shown
data so a toggle re-renders without refetching. `show()` stores args; `_render`
dispatches on mode; `toggle_mode()` flips and re-renders from cache.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_chart_render.py
from datetime import datetime, timedelta

from bbterm.data.models import Bar, Quote
from bbterm.tui.widgets.chart import ChartPanel


def _bars(n=10):
    base = datetime(2026, 1, 2)
    return [
        Bar("AAPL", "1d", base + timedelta(days=i),
            100 + i, 101 + i, 99 + i, 100.5 + i, 1_000_000 + i)
        for i in range(n)
    ]


def test_default_mode_is_candle():
    assert ChartPanel().mode == "candle"


def test_build_candle_output_nonempty():
    panel = ChartPanel()
    panel._size_wh = (80, 24)  # avoid depending on a mounted layout
    out = panel._build_plot("AAPL", "1 Month", _bars(), Quote("AAPL", 110, 100))
    assert isinstance(out, str) and out.strip() != ""


def test_build_line_output_nonempty():
    panel = ChartPanel()
    panel.mode = "line"
    panel._size_wh = (80, 24)
    out = panel._build_plot("AAPL", "1 Month", _bars(), None)
    assert isinstance(out, str) and out.strip() != ""


def test_toggle_mode_flips():
    panel = ChartPanel()
    assert panel.mode == "candle"
    panel.toggle_mode()
    assert panel.mode == "line"
    panel.toggle_mode()
    assert panel.mode == "candle"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_chart_render.py -v`
Expected: FAIL — `AttributeError: 'ChartPanel' object has no attribute 'mode'` (and `_build_plot` signature/`_size_wh` differences).

- [ ] **Step 3: Replace `src/bbterm/tui/widgets/chart.py` with**

```python
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
        plt.date_form("Y-m-d")

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_chart_render.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run the full suite (existing app/chart tests must still pass)**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (the existing `tests/test_app.py` uses `show(...)`, unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/tui/widgets/chart.py tests/test_chart_render.py
git commit -m "feat: candlestick+volume chart with line-mode toggle and render caching"
```

---

### Task 4: Command bar widget (`command_bar.py`)

**Files:**
- Create: `src/bbterm/tui/widgets/command_bar.py`

The command bar is a thin `Input` subclass. It emits the built-in
`Input.Submitted` (carrying `.value`); the app handles it (Task 6). `Escape`
posts a `Blurred` message so the app can return focus to the main panel.

- [ ] **Step 1: Write the widget**

```python
# src/bbterm/tui/widgets/command_bar.py
from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import Input


class CommandBar(Input):
    """Single-line command input. Submits via Input.Submitted (.value)."""

    DEFAULT_CSS = """
    CommandBar { dock: top; height: 1; border: none; background: $boost; }
    CommandBar:focus { background: $accent 20%; }
    """

    class Blurred(Message):
        """Posted when the user presses Escape to leave the command bar."""

    def __init__(self) -> None:
        super().__init__(placeholder="  : command (type a ticker, ADD, DEL, GP, DES, ?)", id="command-bar")

    def _on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.post_message(self.Blurred())
```

- [ ] **Step 2: Verify it imports**

Run: `.venv/bin/python -c "from bbterm.tui.widgets.command_bar import CommandBar; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/bbterm/tui/widgets/command_bar.py
git commit -m "feat: CommandBar input widget with Escape-to-blur"
```

---

### Task 5: Stats view widget (`stats.py`)

**Files:**
- Create: `src/bbterm/tui/widgets/stats.py`
- Test: `tests/test_stats_view.py`

`StatsView` renders a `Stats` into a labeled table. Formatting (volume
humanizing, `n/a` for `None`) lives here, not in the pure `Stats`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stats_view.py
from bbterm.data.stats import Stats
from bbterm.tui.widgets.stats import format_volume, render_stats_text


def test_format_volume_humanizes():
    assert format_volume(58_300_000) == "58.3M"
    assert format_volume(1_500) == "1.5K"
    assert format_volume(950) == "950"


def test_render_handles_none_fields():
    s = Stats("AAPL", 291.52, None, None, 342.1, 201.45,
              None, None, 58_300_000, 289.0, 296.4)
    text = render_stats_text(s)
    assert "AAPL" in text
    assert "n/a" in text          # change/ret_1m/ret_ytd are None
    assert "342.10" in text       # 52w high formatted
    assert "58.3M" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_stats_view.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bbterm.tui.widgets.stats'`

- [ ] **Step 3: Write the implementation**

```python
# src/bbterm/tui/widgets/stats.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_stats_view.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/tui/widgets/stats.py tests/test_stats_view.py
git commit -m "feat: StatsView widget with volume humanizing and n/a handling"
```

---

### Task 6: Wire command bar, ContentSwitcher, focus, dispatch into the app

**Files:**
- Modify: `src/bbterm/tui/app.py`

- [ ] **Step 1: Replace `src/bbterm/tui/app.py` with**

```python
from __future__ import annotations

from datetime import datetime, timedelta

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import ContentSwitcher, Footer, Header

from bbterm.commands import (
    AddSymbol, Help, LoadSymbol, RemoveSymbol, ShowChart, ShowStats, Unknown,
    parse_command,
)
from bbterm.config import load_config
from bbterm.data import build_service
from bbterm.data.providers.base import CostCapExceeded
from bbterm.data.service import DataService
from bbterm.data.stats import compute_stats
from bbterm.tui.widgets.chart import ChartPanel
from bbterm.tui.widgets.command_bar import CommandBar
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
    "Commands: <ticker> load · ADD <sym> · DEL <sym> · "
    "GP chart · DES stats · ? help   |   Keys: :=command 1-6=period "
    "c=line/candle r=refresh q=quit"
)


class BloombergApp(App):
    TITLE = "bbterm"
    CSS = """
    Screen { background: $surface; }
    #main { height: 1fr; }
    #switcher { width: 1fr; }
    """

    BINDINGS = [
        Binding("colon", "focus_command", "Command", show=False),
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "toggle_chart", "Line/Candle"),
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
        yield TickerStrip()
        yield Footer()

    def on_mount(self) -> None:
        # Do not let the CommandBar grab initial focus, or single-key hotkeys
        # (c/q/digits) would be typed into it. With focus cleared, app BINDINGS
        # handle keys and ":" focuses the bar on demand.
        self.set_focus(None)
        self.load_chart()
        self.load_quotes()
        self.set_interval(60, self.load_quotes)

    # ---- focus model -------------------------------------------------------
    def action_focus_command(self) -> None:
        self.query_one(CommandBar).focus()

    def on_command_bar_blurred(self, _message: CommandBar.Blurred) -> None:
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
        if self.query_one("#switcher", ContentSwitcher).current == "stats":
            self.load_stats()
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

    def action_toggle_chart(self) -> None:
        self.query_one(ChartPanel).toggle_mode()

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

    @work(exclusive=True, group="quotes")
    async def load_quotes(self) -> None:
        quotes = []
        for symbol in self.watchlist_symbols:
            quote = await self.service.get_quote(symbol)
            if quote:
                quotes.append(quote)
        self.query_one(Watchlist).show(quotes)
        self.query_one(TickerStrip).show(quotes)


def main() -> None:
    BloombergApp().run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all existing tests pass. (`tests/test_app.py` still boots the app; the
ChartPanel now lives inside a ContentSwitcher but `query_one(ChartPanel)` still
resolves it.)

- [ ] **Step 3: Commit**

```bash
git add src/bbterm/tui/app.py
git commit -m "feat: wire command bar, ContentSwitcher (chart/stats), focus model, dispatch"
```

---

### Task 7: App-level command/focus smoke tests

**Files:**
- Create: `tests/test_app_commands.py`

Driving real key/command flows headlessly with the fake provider.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_app_commands.py
from datetime import datetime, timedelta

from textual.widgets import ContentSwitcher

from bbterm.data.models import Quote
from bbterm.data.service import DataService
from bbterm.data.store import Store
from bbterm.tui.app import BloombergApp
from bbterm.tui.widgets.chart import ChartPanel
from bbterm.tui.widgets.command_bar import CommandBar
from fakes import FakeProvider, make_bars


def _app():
    bars = make_bars("SPY", "1d", start=datetime.now() - timedelta(days=400), n=300)
    fake = FakeProvider(bars=bars, quote=Quote("SPY", 101.0, 100.0))
    service = DataService(Store(":memory:"), fake, fake, fetch_ttl=0.0)
    return BloombergApp(service=service, watchlist=["SPY"]), service


async def _submit(pilot, app, text):
    app.query_one(CommandBar).value = text
    await app.query_one(CommandBar).action_submit()
    await pilot.pause()


async def test_add_and_remove_symbol_persists():
    app, service = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "ADD TSLA")
        assert "TSLA" in app.watchlist_symbols
        assert "TSLA" in service.store.get_watchlist()
        await _submit(pilot, app, "DEL TSLA")
        assert "TSLA" not in app.watchlist_symbols
        assert "TSLA" not in service.store.get_watchlist()


async def test_des_then_gp_switches_views():
    app, _ = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "DES")
        assert app.query_one(ContentSwitcher).current == "stats"
        await _submit(pilot, app, "GP")
        assert app.query_one(ContentSwitcher).current == "chart"


async def test_bare_ticker_loads_symbol():
    app, _ = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "AMZN")
        assert app.current_symbol == "AMZN"


async def test_toggle_chart_mode_binding():
    app, _ = _app()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(ChartPanel).mode == "candle"
        await pilot.press("c")
        assert app.query_one(ChartPanel).mode == "line"


async def test_cannot_remove_last_symbol():
    app, service = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "DEL SPY")
        assert app.watchlist_symbols == ["SPY"]
```

- [ ] **Step 2: Run tests to verify they fail, then pass**

Run: `.venv/bin/python -m pytest tests/test_app_commands.py -v`
Expected: if any assertion reveals a wiring bug, fix it in `app.py` (re-run until
green). Target: 5 passed.

Note on `action_submit()`: Textual's `Input` exposes `action_submit()` which
fires `Input.Submitted` with the current value — this is the headless equivalent
of pressing Enter in the focused bar. If it is unavailable in this Textual
version, replace `_submit` with: focus the bar, `await pilot.press(*text)`, then
`await pilot.press("enter")`.

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_app_commands.py
git commit -m "test: headless command-bar, view-switch, and toggle flows"
```

---

### Task 8: LaTeX user guide

**Files:**
- Create: `docs/manual/bbterm-guide.tex`
- Create (build output, gitignored): `docs/manual/bbterm-guide.pdf`
- Modify: `.gitignore`

Written last so it documents shipped behavior. `pdflatex` is verified present
(TeX Live 2025).

- [ ] **Step 1: Ignore LaTeX build artifacts**

Append to `.gitignore`:

```
docs/manual/*.aux
docs/manual/*.log
docs/manual/*.out
docs/manual/*.toc
docs/manual/*.pdf
```

- [ ] **Step 2: Write `docs/manual/bbterm-guide.tex`**

```latex
\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{fancyvrb}
\usepackage{booktabs}
\usepackage{hyperref}
\usepackage{parskip}
\title{bbterm --- A Beginner's Guide to Your Local Market Terminal}
\author{}
\date{}

\begin{document}
\maketitle
\tableofcontents

\section{What bbterm is}
bbterm is a market terminal you run in your own terminal window. It shows price
charts, a watchlist of symbols you follow, and a statistics panel. Market data
comes from Databento and is cached locally in a small database, so the app is
fast, works offline once data is fetched, and costs almost nothing to run.

\section{Starting the app}
From the project folder:
\begin{Verbatim}[frame=single]
.venv/bin/bbterm-sync     # one-time/daily: download recent daily prices
.venv/bin/bbterm          # launch the terminal
\end{Verbatim}
The first time, set your Databento key in your shell (\texttt{DATABENTO\_API\_KEY}).
Without it, bbterm still runs using a free fallback data source.

\section{The screen}
\begin{Verbatim}[frame=single]
+----------------------------------------------+
| : AAPL_                          (command)   |  <- command bar (top)
+----------+-----------------------------------+
| WATCHLIST|  AAPL  291.52  -6.48 (-2.18%)     |
| SPY  ... |  [ chart  OR  statistics ]        |  <- main panel
| AAPL ... |                                   |
+----------+-----------------------------------+
| SPY .. | QQQ .. | AAPL ..  (ticker strip)    |
| [GP]chart [DES]stats [c]line  q  ?=help      |  <- footer
+----------------------------------------------+
\end{Verbatim}
\textbf{Watchlist} (left): the symbols you follow, each with price and percent
change. \textbf{Main panel} (right): either the price chart or the statistics
view. \textbf{Ticker strip} (bottom): a compact running line of your watchlist.

\section{The command bar and the colon key}
The command bar is one line at the top where you type instructions instead of
hunting through menus. Because single keys are also shortcuts (for example
\texttt{q} quits), the bar is normally ``asleep''. Press \texttt{:} (the colon
key) to wake it up and move your typing into it. Type your command, press
\texttt{Enter} to run it, or press \texttt{Esc} to leave the bar without running
anything. This colon-to-type idea is borrowed from the \texttt{vim} editor.

\section{Commands}
\begin{tabular}{ll}
\toprule
Type this & What happens \\
\midrule
\texttt{AAPL} & Load Apple into the main panel \\
\texttt{ADD TSLA} & Add Tesla to your watchlist (saved) \\
\texttt{DEL SPY} & Remove SPY from your watchlist (saved) \\
\texttt{GP} & Show the price chart \\
\texttt{DES} & Show the statistics panel \\
\texttt{?} or \texttt{HELP} & Show a reminder of the commands \\
\bottomrule
\end{tabular}

\section{Keyboard shortcuts}
These work when the command bar is \emph{not} focused.
\begin{tabular}{ll}
\toprule
Key & Action \\
\midrule
\texttt{:} & Focus the command bar \\
\texttt{1}--\texttt{6} & Time range: 1D, 5D, 1M, 6M, 1Y, 5Y \\
\texttt{c} & Toggle candlestick / line chart \\
\texttt{r} & Refresh data \\
\texttt{q} & Quit \\
\bottomrule
\end{tabular}

\section{Reading the chart}
In candlestick mode, each candle is one time period. The thick body spans the
open and close prices; a green body means the price rose, red means it fell. The
thin lines (wicks) above and below show the highest and lowest prices reached.
The bars in the smaller panel below show trading volume. Press \texttt{c} for a
simpler line of closing prices instead.

\section{Reading the statistics panel (DES)}
\begin{tabular}{ll}
\toprule
Field & Meaning \\
\midrule
Last & Most recent price \\
Change & Price and percent move versus the previous close \\
52w High / Low & Highest and lowest price over the past year \\
1M Return & Percent change over about one month \\
YTD Return & Percent change since January 1st \\
Avg Vol & Average daily trading volume \\
Day Range & Today's low and high \\
\bottomrule
\end{tabular}
All statistics are computed from the price history already on your machine.

\end{document}
```

- [ ] **Step 3: Compile (twice, for the table of contents)**

Run:
```bash
cd docs/manual && pdflatex -interaction=nonstopmode bbterm-guide.tex >/dev/null && pdflatex -interaction=nonstopmode bbterm-guide.tex >/dev/null && cd ../.. && ls -la docs/manual/bbterm-guide.pdf
```
Expected: exit code 0 and a non-empty `bbterm-guide.pdf`. If `pdflatex` reports a
missing package, install it with `tlmgr install <package>` and re-run.

- [ ] **Step 4: Commit (source + .gitignore only; PDF is ignored)**

```bash
git add docs/manual/bbterm-guide.tex .gitignore
git commit -m "docs: LaTeX beginner's guide for bbterm (compiles to PDF)"
```

---

## Done criteria (maps to spec)

- Hybrid command bar: bare ticker + ADD/DEL/GP/DES/? — Tasks 1, 4, 6, 7.
- Candlestick + volume with `c` line toggle — Tasks 3, 6, 7.
- DES stats from bars (no new data source) — Tasks 2, 5, 6.
- Persisted watchlist editing via `set_watchlist` — Task 6, verified persistent in Task 7.
- Focus model (`:` focus, `Esc` blur, hotkeys gated) — Tasks 4, 6, 7.
- Error handling (unknown cmd, dup/missing/last-symbol) — Task 6, tested Task 7.
- LaTeX user guide compiled to PDF — Task 8.
- No credits spent: every test uses the fake provider; stats/candles read cached or synthetic bars.
```
