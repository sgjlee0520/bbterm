# Phase 3 Implementation Plan — Command Bar, Candlestick Charts, Watchlist Editing, User Guide

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make bbterm keyboard-driven like a real terminal: a hybrid command bar (`:` to focus), candlestick + volume charts with a line toggle, a bar-derived stats (DES) panel, persisted `ADD`/`DEL` watchlist editing, and a LaTeX user guide compiled to PDF.

**Architecture:** Two pure modules — `commands.parse_command` and `data.stats.compute_stats` — carry all the logic and are unit-tested with zero UI. Thin Textual widgets render their outputs; the app wires a `ContentSwitcher` (chart ⇄ stats), routes command-bar submissions through `parse_command`, and persists watchlist edits through the existing `Store`. The guide is written last against final behavior.

**Tech Stack:** Python 3.11+ (running 3.14), Textual 8.x, plotext 5.3.x, DuckDB, pytest + pytest-asyncio, TeX Live (`pdflatex`).

## Global Constraints

- Run everything from `/Users/slee/bloomberg`; use `.venv/bin/python -m pytest` (no activation).
- No new data sources and no network in the test suite — stats and candles use cached/synthetic `Bar` objects. Only manual smoke scripts may touch the live API.
- Existing widget is named `ChartPanel` (keep it). Existing `Store.set_watchlist(list[str])` and `Store.get_watchlist()` already persist watchlists.
- Verified API facts: plotext candlesticks need `plt.date_form("Y-m-d")` + `plt.datetime_to_string(dt)`; `plt.candlestick(dates, {"Open":[],"Close":[],"High":[],"Low":[]})`; volume via `plt.subplots(2,1)` + `plt.bar(dates, vols)`. Textual key name for `:` is `colon`. `ContentSwitcher.current = "<child-id>"` switches views.

---

### Task 1: Command parser (`commands.py`)

**Files:**
- Create: `src/bbterm/commands.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Produces: command dataclasses `LoadSymbol(symbol: str)`, `AddSymbol(symbol: str)`, `RemoveSymbol(symbol: str)`, `ShowChart()`, `ShowStats()`, `Help()`, `Unknown(text: str)`; and `parse_command(text: str) -> Command | None` (returns `None` for empty/whitespace input). All symbols are upper-cased.

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
    ("ADD tsla", AddSymbol("TSLA")),
    ("DEL spy", RemoveSymbol("SPY")),
    ("REMOVE spy", RemoveSymbol("SPY")),
    ("GP", ShowChart()),
    ("gp", ShowChart()),
    ("DES", ShowStats()),
    ("?", Help()),
    ("HELP", Help()),
])
def test_parses_known_forms(text, expected):
    assert parse_command(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "\t"])
def test_empty_is_none(text):
    assert parse_command(text) is None


@pytest.mark.parametrize("text", [
    "ADD",            # verb needs a symbol
    "DEL",
    "@@@",            # not a valid symbol
    "this is junk",   # multi-word non-verb
    "TOOLONGSYM",     # >6 chars
])
def test_unknown_forms(text):
    result = parse_command(text)
    assert isinstance(result, Unknown)
    assert result.text == text
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

_SYMBOL = re.compile(r"^[A-Z][A-Z0-9]{0,5}([.\-][A-Z0-9]{1,4})?$")


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


Command = (
    LoadSymbol | AddSymbol | RemoveSymbol | ShowChart | ShowStats | Help | Unknown
)


def _is_symbol(token: str) -> bool:
    return bool(_SYMBOL.match(token))


def parse_command(text: str) -> Command | None:
    raw = text.strip()
    if not raw:
        return None
    tokens = raw.split()
    verb = tokens[0].upper()
    arg = tokens[1].upper() if len(tokens) > 1 else None

    if verb in ("ADD",) and arg and _is_symbol(arg):
        return AddSymbol(arg)
    if verb in ("DEL", "REMOVE") and arg and _is_symbol(arg):
        return RemoveSymbol(arg)
    if verb == "GP" and arg is None:
        return ShowChart()
    if verb == "DES" and arg is None:
        return ShowStats()
    if verb in ("?", "HELP") and arg is None:
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

**Interfaces:**
- Consumes: `Bar` and `Quote` from `bbterm.data.models`; test helper `make_bars` from `tests/fakes.py`.
- Produces: `Stats` dataclass (fields below) and `compute_stats(symbol: str, bars: list[Bar], quote: Quote | None) -> Stats`. The "current year" for YTD is taken from the **last bar's** timestamp (deterministic; not `datetime.now()`). `ret_1m` compares the last close to the close 21 bars earlier.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_stats.py
from datetime import datetime

from bbterm.data.models import Bar, Quote
from bbterm.data.stats import Stats, compute_stats


def _bar(day_offset, year=2026, month=1, day=5, close=100.0, high=None, low=None,
         volume=1000):
    ts = datetime(year, month, day) if day_offset is None else datetime(2026, 1, 1)
    return Bar("AAPL", "1d", ts, close, high or close + 1, low or close - 1,
               close, volume)


def _series(n, start_close=100.0):
    # n daily bars over Jan 2026, close ramps +1/day
    bars = []
    for i in range(n):
        ts = datetime(2026, 1, 1) + __import__("datetime").timedelta(days=i)
        c = start_close + i
        bars.append(Bar("AAPL", "1d", ts, c, c + 2, c - 2, c, 1000 + i))
    return bars


def test_full_history_stats():
    bars = _series(30)  # closes 100..129
    quote = Quote("AAPL", 130.0, 129.0)
    s = compute_stats("AAPL", bars, quote)
    assert isinstance(s, Stats)
    assert s.symbol == "AAPL"
    assert s.last == 130.0
    assert s.change == 1.0
    assert s.high_52w == max(b.high for b in bars)
    assert s.low_52w == min(b.low for b in bars)
    # 1M return: last close (129) vs close 21 bars ago (closes[-22]=108) within series
    assert s.ret_1m is not None
    assert s.day_low == bars[-1].low
    assert s.day_high == bars[-1].high


def test_short_history_yields_none_windows():
    bars = _series(5)  # not enough for 1M (needs >=22)
    s = compute_stats("AAPL", bars, None)
    assert s.ret_1m is None
    assert s.last == bars[-1].close  # falls back to last close when no quote
    assert s.avg_volume == sum(b.volume for b in bars) / len(bars)


def test_ytd_uses_first_bar_of_last_bar_year():
    # bars span Dec 2025 -> Jan 2026; YTD anchors on first 2026 bar
    import datetime as dt
    bars = [
        Bar("AAPL", "1d", dt.datetime(2025, 12, 30), 90.0, 91, 89, 90.0, 1000),
        Bar("AAPL", "1d", dt.datetime(2026, 1, 2), 100.0, 101, 99, 100.0, 1000),
        Bar("AAPL", "1d", dt.datetime(2026, 1, 3), 110.0, 111, 109, 110.0, 1000),
    ]
    s = compute_stats("AAPL", bars, None)
    # YTD: (110 / 100 - 1) * 100 == 10.0  (anchored on Jan 2 close, not Dec)
    assert round(s.ret_ytd, 4) == 10.0


def test_empty_bars_safe():
    s = compute_stats("AAPL", [], Quote("AAPL", 50.0, 49.0))
    assert s.last == 50.0
    assert s.high_52w is None
    assert s.low_52w is None
    assert s.ret_1m is None
    assert s.ret_ytd is None
    assert s.avg_volume is None
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

_ONE_MONTH_BARS = 21  # ~trading days in a month


@dataclass(frozen=True)
class Stats:
    symbol: str
    last: float
    change: float
    pct_change: float
    high_52w: float | None
    low_52w: float | None
    ret_1m: float | None
    ret_ytd: float | None
    avg_volume: float | None
    day_low: float | None
    day_high: float | None


def _pct(now: float, then: float) -> float | None:
    if not then:
        return None
    return (now / then - 1) * 100


def compute_stats(symbol: str, bars: list[Bar], quote: Quote | None) -> Stats:
    if not bars:
        last = quote.price if quote else 0.0
        change = quote.change if quote else 0.0
        pct = quote.pct_change if quote else 0.0
        return Stats(symbol, last, change, pct, None, None, None, None, None,
                     None, None)

    closes = [b.close for b in bars]
    last_close = closes[-1]
    last = quote.price if quote else last_close
    if quote:
        change, pct = quote.change, quote.pct_change
    elif len(closes) >= 2:
        change = last_close - closes[-2]
        pct = _pct(last_close, closes[-2]) or 0.0
    else:
        change, pct = 0.0, 0.0

    high_52w = max(b.high for b in bars)
    low_52w = min(b.low for b in bars)

    ret_1m = (
        _pct(last_close, closes[-1 - _ONE_MONTH_BARS])
        if len(closes) > _ONE_MONTH_BARS else None
    )

    year = bars[-1].ts.year
    ytd_anchor = next((b.close for b in bars if b.ts.year == year), None)
    ret_ytd = _pct(last_close, ytd_anchor) if ytd_anchor else None

    avg_volume = sum(b.volume for b in bars) / len(bars)

    return Stats(
        symbol, last, change, pct, high_52w, low_52w, ret_1m, ret_ytd,
        avg_volume, bars[-1].low, bars[-1].high,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_stats.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/stats.py tests/test_stats.py
git commit -m "feat: bar-derived statistics (compute_stats)"
```

---

### Task 3: Candlestick + volume rendering in `ChartPanel`

**Files:**
- Modify: `src/bbterm/tui/widgets/chart.py`
- Test: `tests/test_chart_render.py`

**Interfaces:**
- Consumes: `Bar`, `Quote`.
- Produces: `ChartPanel.mode: str` (`"candle"` default, or `"line"`), `ChartPanel.toggle_mode() -> None` (flips the two), and `ChartPanel._build_candles(symbol: str, bars: list[Bar], width: int, height: int) -> str`. Existing `show(symbol, period_label, bars, quote)` now branches on `self.mode`. The existing line helper is renamed nothing — keep `_build_plot`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_chart_render.py
from datetime import datetime, timedelta

from bbterm.data.models import Bar
from bbterm.tui.widgets.chart import ChartPanel


def _bars(n=10):
    out = []
    for i in range(n):
        ts = datetime(2026, 1, 1) + timedelta(days=i)
        c = 100 + i
        out.append(Bar("AAPL", "1d", ts, c, c + 2, c - 2, c, 1000 + i * 10))
    return out


def test_default_mode_is_candle():
    assert ChartPanel().mode == "candle"


def test_toggle_mode_flips():
    panel = ChartPanel()
    panel.toggle_mode()
    assert panel.mode == "line"
    panel.toggle_mode()
    assert panel.mode == "candle"


def test_build_candles_returns_nonempty_for_bars():
    out = ChartPanel()._build_candles("AAPL", _bars(), width=70, height=20)
    assert isinstance(out, str)
    assert len(out.strip()) > 0


def test_build_candles_handles_single_bar():
    out = ChartPanel()._build_candles("AAPL", _bars(1), width=70, height=20)
    assert isinstance(out, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_chart_render.py -v`
Expected: FAIL — `AttributeError: 'ChartPanel' object has no attribute 'mode'`

- [ ] **Step 3: Read the current file, then implement**

Read `src/bbterm/tui/widgets/chart.py`. Add `mode`, `toggle_mode`, `_build_candles`, and branch `show()` on mode. Full new file:

```python
# src/bbterm/tui/widgets/chart.py
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
        super().__init__(**kwargs)  # forwards id=... from compose
        self.mode = "candle"  # "candle" | "line"
        self._last: tuple[str, str, list[Bar], Quote | None] | None = None

    def compose(self) -> ComposeResult:
        yield Label("", id="chart-header", classes="header")
        yield Static("", id="chart-plot", classes="plot")

    def toggle_mode(self) -> None:
        self.mode = "line" if self.mode == "candle" else "candle"
        if self._last is not None:
            self.show(*self._last)

    def show(
        self,
        symbol: str,
        period_label: str,
        bars: list[Bar],
        quote: Quote | None,
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
            mode_tag = "candle" if self.mode == "candle" else "line"
            text.append(f"  [{mode_tag}]  ", style="dim")
            header.update(text)
        else:
            header.update(f"  {symbol}")

        if not bars:
            plot.update("  No data available for this symbol/period.")
            return

        width = max(self.size.width - 2, 40)
        height = max(self.size.height - 3, 10)
        if self.mode == "candle":
            plot.update(self._build_candles(symbol, bars, width, height))
        else:
            plot.update(self._build_plot(symbol, period_label, bars, quote))

    def _build_candles(
        self, symbol: str, bars: list[Bar], width: int, height: int
    ) -> str:
        dates = [plt.datetime_to_string(b.ts) for b in bars]
        data = {
            "Open": [b.open for b in bars],
            "Close": [b.close for b in bars],
            "High": [b.high for b in bars],
            "Low": [b.low for b in bars],
        }
        vols = [b.volume for b in bars]

        plt.clear_figure()
        plt.theme("dark")
        plt.plotsize(width, height)
        plt.date_form("Y-m-d")
        plt.subplots(2, 1)

        price_h = max(height - 6, 6)
        plt.subplot(1, 1).plotsize(width, price_h)
        plt.candlestick(dates, data)
        plt.title(f"{symbol} (candles)")

        plt.subplot(2, 1).plotsize(width, max(height - price_h, 4))
        plt.bar(dates, vols)
        plt.ylabel("Vol")
        return plt.build()

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
```

Note `_build_candles` reads `self.size` only indirectly — it takes explicit `width`/`height`, so the unit test can call it on an unmounted `ChartPanel()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_chart_render.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run the existing app smoke test (regression)**

Run: `.venv/bin/python -m pytest tests/test_app.py -v`
Expected: still passes (ChartPanel mounts and renders).

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/tui/widgets/chart.py tests/test_chart_render.py
git commit -m "feat: candlestick + volume chart with line/candle mode toggle"
```

---

### Task 4: Command bar widget (`command_bar.py`)

**Files:**
- Create: `src/bbterm/tui/widgets/command_bar.py`
- Test: `tests/test_command_bar.py`

**Interfaces:**
- Produces: `CommandBar(Input)` with `DEFAULT_CSS`; it reuses Textual's built-in `Input.Submitted` message (no custom message). On submit it clears its own value. A unit test drives it inside a tiny host app.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_command_bar.py
from textual.app import App, ComposeResult
from textual.widgets import Input

from bbterm.tui.widgets.command_bar import CommandBar


class _Host(App):
    def __init__(self):
        super().__init__()
        self.submitted: list[str] = []

    def compose(self) -> ComposeResult:
        yield CommandBar()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.submitted.append(event.value)


async def test_submit_emits_value_and_clears():
    app = _Host()
    async with app.run_test() as pilot:
        bar = app.query_one(CommandBar)
        bar.focus()
        await pilot.pause()
        for ch in "AAPL":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        assert app.submitted == ["AAPL"]
        assert bar.value == ""  # cleared after submit
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_command_bar.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bbterm.tui.widgets.command_bar'`

- [ ] **Step 3: Write the implementation**

```python
# src/bbterm/tui/widgets/command_bar.py
from __future__ import annotations

from textual.widgets import Input


class CommandBar(Input):
    DEFAULT_CSS = """
    CommandBar {
        dock: top;
        border: none;
        background: $boost;
        color: $text;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__(placeholder="type a command — ticker, ADD, DEL, GP, DES, ?")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Let the app handle the value, then clear the line for the next command.
        self.clear()
```

Note: `Input.Submitted` bubbles to the app even though this handler runs first; the app's `on_input_submitted` still fires. `self.clear()` empties the field.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_command_bar.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/tui/widgets/command_bar.py tests/test_command_bar.py
git commit -m "feat: command bar input widget"
```

---

### Task 5: Stats view widget (`widgets/stats.py`)

**Files:**
- Create: `src/bbterm/tui/widgets/stats.py`
- Test: `tests/test_stats_view.py`

**Interfaces:**
- Consumes: `Stats` from `bbterm.data.stats`.
- Produces: `StatsView(Widget)` with `show(stats: Stats) -> None` that renders the fields into a `Static`. `None` numeric fields render as `n/a`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stats_view.py
from textual.app import App, ComposeResult

from bbterm.data.stats import Stats
from bbterm.tui.widgets.stats import StatsView


class _Host(App):
    def compose(self) -> ComposeResult:
        yield StatsView()


async def test_stats_view_renders_fields_and_na():
    stats = Stats(
        symbol="AAPL", last=291.52, change=-6.48, pct_change=-2.18,
        high_52w=342.1, low_52w=201.45, ret_1m=4.2, ret_ytd=None,
        avg_volume=58_300_000, day_low=289.0, day_high=296.4,
    )
    app = _Host()
    async with app.run_test() as pilot:
        view = app.query_one(StatsView)
        view.show(stats)
        await pilot.pause()
        rendered = app.query_one("#stats-body").render()
        text = rendered.plain if hasattr(rendered, "plain") else str(rendered)
        assert "AAPL" in text
        assert "342.10" in text       # 52w high formatted
        assert "n/a" in text          # ret_ytd is None
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


def _num(value: float | None, fmt: str = "{:.2f}") -> str:
    return "n/a" if value is None else fmt.format(value)


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def _vol(value: float | None) -> str:
    if value is None:
        return "n/a"
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if value >= div:
            return f"{value / div:.1f}{unit}"
    return f"{value:.0f}"


class StatsView(Widget):
    DEFAULT_CSS = """
    StatsView { height: 1fr; }
    StatsView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    StatsView > Static.body { padding: 1 2; }
    """

    def compose(self) -> ComposeResult:
        yield Label("", id="stats-header", classes="header")
        yield Static("", id="stats-body", classes="body")

    def show(self, stats: Stats) -> None:
        self.query_one("#stats-header", Label).update(f"  {stats.symbol} — Statistics")
        color = "green" if stats.change >= 0 else "red"
        rows = [
            ("Last", _num(stats.last)),
            ("Change", f"{stats.change:+.2f} ({_pct(stats.pct_change)})"),
            ("52w High", _num(stats.high_52w)),
            ("52w Low", _num(stats.low_52w)),
            ("1M Return", _pct(stats.ret_1m)),
            ("YTD Return", _pct(stats.ret_ytd)),
            ("Avg Vol", _vol(stats.avg_volume)),
            ("Day Range", f"{_num(stats.day_low)} – {_num(stats.day_high)}"),
        ]
        body = Text()
        for i, (label, value) in enumerate(rows):
            if i:
                body.append("\n")
            body.append(f"{label:<12}", style="dim")
            style = color if label == "Change" else "white"
            body.append(value, style=style)
        self.query_one("#stats-body", Static).update(body)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_stats_view.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/tui/widgets/stats.py tests/test_stats_view.py
git commit -m "feat: stats (DES) view widget"
```

---

### Task 6: Wire command bar, ContentSwitcher, focus, and dispatch into the app

**Files:**
- Modify: `src/bbterm/tui/app.py`
- Test: `tests/test_app_phase3.py`

**Interfaces:**
- Consumes: `parse_command` + command types (Task 1), `compute_stats` (Task 2), `ChartPanel.toggle_mode` (Task 3), `CommandBar` (Task 4), `StatsView` (Task 5), existing `Store.set_watchlist`.
- Produces: app behaviors — `:` focuses the command bar; `Esc` blurs it; submitting a command routes through `parse_command`; `ADD`/`DEL` persist and refresh; `GP`/`DES` switch the `ContentSwitcher`; `c` toggles chart mode; the last watchlist symbol cannot be deleted.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_app_phase3.py
from datetime import datetime, timedelta

from bbterm.data.models import Quote
from bbterm.data.service import DataService
from bbterm.data.store import Store
from bbterm.tui.app import BloombergApp
from bbterm.tui.widgets.chart import ChartPanel
from bbterm.tui.widgets.stats import StatsView
from fakes import FakeProvider, make_bars


def _service():
    bars = make_bars("SPY", "1d", start=datetime.now() - timedelta(days=400), n=300)
    bars += make_bars("TSLA", "1d", start=datetime.now() - timedelta(days=400), n=300)
    fake = FakeProvider(bars=bars, quote=Quote("SPY", 101.0, 100.0))
    return DataService(Store(":memory:"), fake, fake, fetch_ttl=0.0)


async def test_colon_focuses_command_bar_then_esc_blurs():
    app = BloombergApp(service=_service(), watchlist=["SPY"])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("colon")
        await pilot.pause()
        from bbterm.tui.widgets.command_bar import CommandBar
        assert app.focused is app.query_one(CommandBar)
        await pilot.press("escape")
        await pilot.pause()
        assert app.focused is not app.query_one(CommandBar)


async def test_add_command_persists_to_watchlist():
    service = _service()
    app = BloombergApp(service=service, watchlist=["SPY"])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("colon")
        for ch in "ADD TSLA":
            await pilot.press("space" if ch == " " else ch)
        await pilot.press("enter")
        await pilot.pause()
        assert "TSLA" in app.watchlist_symbols
        assert "TSLA" in service.store.get_watchlist()  # persisted


async def test_des_then_gp_switches_views():
    app = BloombergApp(service=_service(), watchlist=["SPY"])
    async with app.run_test() as pilot:
        await pilot.pause()
        switcher = app.query_one("#main-switcher")
        await pilot.press("colon")
        for ch in "DES":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        assert switcher.current == "stats"
        await pilot.press("colon")
        for ch in "GP":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        assert switcher.current == "chart"


async def test_cannot_delete_last_symbol():
    service = _service()
    app = BloombergApp(service=service, watchlist=["SPY"])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("colon")
        for ch in "DEL SPY":
            await pilot.press("space" if ch == " " else ch)
        await pilot.press("enter")
        await pilot.pause()
        assert app.watchlist_symbols == ["SPY"]  # refused


async def test_c_toggles_chart_mode():
    app = BloombergApp(service=_service(), watchlist=["SPY"])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(ChartPanel).mode == "candle"
        await pilot.press("c")
        await pilot.pause()
        assert app.query_one(ChartPanel).mode == "line"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_app_phase3.py -v`
Expected: FAIL — `#main-switcher` not found / `colon` binding missing.

- [ ] **Step 3: Implement the app changes**

Full new `src/bbterm/tui/app.py`:

```python
# src/bbterm/tui/app.py
from __future__ import annotations

from datetime import datetime, timedelta

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import ContentSwitcher, Footer, Header, Input

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

HELP_TEXT = (
    "Commands: <ticker> load · ADD <sym> · DEL <sym> · GP chart · "
    "DES stats · ? help   |   keys: 1-6 period · c line/candle · r refresh · q quit"
)


class BloombergApp(App):
    TITLE = "bbterm"
    CSS = """
    Screen { background: $surface; }
    #main { height: 1fr; }
    #main-switcher { width: 1fr; }
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
            with ContentSwitcher(initial="chart", id="main-switcher"):
                yield ChartPanel(id="chart")
                yield StatsView(id="stats")
        yield TickerStrip()
        yield Footer()

    def on_mount(self) -> None:
        self.load_chart()
        self.load_quotes()
        self.set_interval(60, self.load_quotes)

    # ----- input / commands -----

    def action_focus_command(self) -> None:
        self.query_one(CommandBar).focus()

    def on_key(self, event) -> None:
        # Esc blurs the command bar back to the app.
        if event.key == "escape" and self.focused is self.query_one(CommandBar):
            self.set_focus(None)
            event.stop()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.set_focus(None)
        command = parse_command(event.value)
        if command is None:
            return
        self._dispatch(command)

    def _dispatch(self, command) -> None:
        if isinstance(command, LoadSymbol):
            self.current_symbol = command.symbol
            self._refresh_active_view()
        elif isinstance(command, AddSymbol):
            self._add_symbol(command.symbol)
        elif isinstance(command, RemoveSymbol):
            self._remove_symbol(command.symbol)
        elif isinstance(command, ShowChart):
            self.query_one("#main-switcher", ContentSwitcher).current = "chart"
            self.load_chart()
        elif isinstance(command, ShowStats):
            self.query_one("#main-switcher", ContentSwitcher).current = "stats"
            self.load_stats()
        elif isinstance(command, Help):
            self.notify(HELP_TEXT, title="Help")
        elif isinstance(command, Unknown):
            self.notify(f"Unknown command: {command.text}", severity="warning")

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
            self.notify("Cannot remove the last symbol", severity="warning")
            return
        self.watchlist_symbols.remove(symbol)
        self.service.store.set_watchlist(self.watchlist_symbols)
        if self.current_symbol == symbol:
            self.current_symbol = self.watchlist_symbols[0]
            self._refresh_active_view()
        self.notify(f"Removed {symbol}")
        self.load_quotes()

    def _refresh_active_view(self) -> None:
        if self.query_one("#main-switcher", ContentSwitcher).current == "stats":
            self.load_stats()
        else:
            self.load_chart()

    # ----- actions -----

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
        self._refresh_active_view()

    def action_toggle_chart(self) -> None:
        self.query_one(ChartPanel).toggle_mode()

    # ----- workers -----

    async def _fetch_bars(self, interval: str, delta: timedelta) -> list:
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
        bars = await self._fetch_bars(interval, delta)
        quote = await self.service.get_quote(self.current_symbol)
        self.query_one(ChartPanel).show(self.current_symbol, label, bars, quote)

    @work(exclusive=True, group="stats")
    async def load_stats(self) -> None:
        # Stats always use a year of daily bars for 52w/YTD.
        bars = await self._fetch_bars("1d", timedelta(days=365))
        quote = await self.service.get_quote(self.current_symbol)
        stats = compute_stats(self.current_symbol, bars, quote)
        self.query_one(StatsView).show(stats)

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

- [ ] **Step 4: Run the new tests**

Run: `.venv/bin/python -m pytest tests/test_app_phase3.py -v`
Expected: 5 passed.

- [ ] **Step 5: Run the full suite (regression)**

Run: `.venv/bin/python -m pytest`
Expected: all pass (Phase 1/2 tests + new ones). If `tests/test_app.py` asserts old single-panel layout, it still holds — `ChartPanel` is present; no changes needed.

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/tui/app.py tests/test_app_phase3.py
git commit -m "feat: wire command bar, content switcher, focus model, watchlist editing"
```

---

### Task 7: LaTeX user guide compiled to PDF

**Files:**
- Create: `docs/manual/bbterm-guide.tex`
- Create: `docs/manual/.gitignore` (ignore LaTeX build artifacts, keep the PDF)
- Modify: root `.gitignore` is untouched; artifacts handled locally in `docs/manual/`.

**Interfaces:**
- Consumes: final command set and key bindings from Tasks 1–6 (document them exactly).
- Produces: `docs/manual/bbterm-guide.pdf`.

- [ ] **Step 1: Write the LaTeX source**

```latex
% docs/manual/bbterm-guide.tex
\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{booktabs}
\usepackage{fancyvrb}
\usepackage{xcolor}
\usepackage{titlesec}
\usepackage{hyperref}
\hypersetup{colorlinks=true, linkcolor=blue, urlcolor=blue}
\titleformat{\section}{\large\bfseries}{\thesection}{1em}{}

\title{\textbf{bbterm} — A Local Market Terminal\\[0.3em]
\large User Guide for First-Time Users}
\author{}
\date{}

\begin{document}
\maketitle

\section{What bbterm is}
bbterm is a Bloomberg-style market terminal that runs entirely on your own
machine. It pulls historical price data from Databento, caches it locally in a
DuckDB database, and shows it in a keyboard-driven terminal interface. Because
everything you have already viewed is cached, the app keeps working offline, and
each piece of market data is paid for at most once.

If you have never used a Bloomberg terminal: the core idea is that you drive
\emph{everything} from the keyboard by typing short commands, instead of
clicking menus. This guide explains that model from scratch.

\section{Starting the app}
\begin{Verbatim}[frame=single]
# one-time: set your Databento key in your shell profile (~/.zshrc)
export DATABENTO_API_KEY="db-..."

# cache a year of daily bars for your watchlist (optional but recommended)
.venv/bin/bbterm-sync

# launch the terminal
.venv/bin/bbterm
\end{Verbatim}
Without a key, bbterm still runs using a free fallback data source.

\section{The screen}
\begin{Verbatim}[frame=single]
+- Header --------------------------------------------+
| : AAPL_                              (command bar)   |
+----------+------------------------------------------+
| WATCHLIST|  AAPL  291.52  -6.48 (-2.18%)            |
| SPY  ... |  [ chart  or  statistics ]               |
| AAPL ... |   ...                                    |
+----------+------------------------------------------+
| SPY .. | QQQ .. | AAPL ..  (ticker strip)           |
| [GP]chart [DES]stats [c]line  q  ?=help  (footer)   |
+-----------------------------------------------------+
\end{Verbatim}
\textbf{Watchlist} (left): the symbols you follow, with live-ish price and
percent change. \textbf{Main panel} (right): either the price chart or the
statistics view. \textbf{Ticker strip} (bottom): a compact one-line summary of
the whole watchlist. \textbf{Command bar} (top): where you type commands.

\section{The command bar and the \texttt{:} focus key}
The command bar only listens to your typing when it is \emph{focused}. This
keeps single-key shortcuts (like \texttt{q} to quit) from firing while you type
a command.

\begin{itemize}
  \item Press \texttt{:} to move focus \emph{into} the command bar. It lights up.
  \item Type your command, then press \texttt{Enter} to run it. The line clears.
  \item Press \texttt{Esc} to leave the command bar; single-key shortcuts work
  again.
\end{itemize}
This is the same idea as the \texttt{:} command line in the \texttt{vim} editor.

\section{Command reference}
\begin{center}
\begin{tabular}{@{}lll@{}}
\toprule
\textbf{Type this} & \textbf{Example} & \textbf{What it does} \\
\midrule
\texttt{<ticker>}     & \texttt{AAPL}     & Load that symbol into the main panel \\
\texttt{ADD <sym>}    & \texttt{ADD TSLA} & Add a symbol to the watchlist (saved) \\
\texttt{DEL <sym>}    & \texttt{DEL SPY}  & Remove a symbol from the watchlist (saved) \\
\texttt{GP}           & \texttt{GP}       & Show the price chart \\
\texttt{DES}          & \texttt{DES}      & Show the statistics panel \\
\texttt{?}            & \texttt{?}        & Show the help line \\
\bottomrule
\end{tabular}
\end{center}
\noindent Watchlist edits are saved to the local database and persist across
restarts. The last remaining symbol cannot be removed.

\section{Keyboard shortcuts (command bar not focused)}
\begin{center}
\begin{tabular}{@{}ll@{}}
\toprule
\textbf{Key} & \textbf{Action} \\
\midrule
\texttt{1 2 3 4 5 6} & Time range: 1D, 5D, 1M, 6M, 1Y, 5Y \\
\texttt{c}           & Toggle the chart between candlesticks and a line \\
\texttt{r}           & Refresh the current view and quotes \\
\texttt{q}           & Quit \\
\texttt{:}           & Focus the command bar \\
\bottomrule
\end{tabular}
\end{center}

\section{Reading the chart}
In \textbf{candlestick} mode (the default) each bar is one period:
\begin{itemize}
  \item The thick \emph{body} spans the open and close prices. By convention a
  rising period (close above open) and a falling period use different colors.
  \item The thin \emph{wicks} above and below mark the high and low.
  \item The lower \emph{volume} panel shows how many shares traded each period.
\end{itemize}
Press \texttt{c} for a simple \textbf{line} of closing prices, which is easier to
read over long ranges.

\section{Reading the statistics panel (DES)}
\begin{center}
\begin{tabular}{@{}ll@{}}
\toprule
\textbf{Field} & \textbf{Meaning} \\
\midrule
Last        & Most recent price \\
Change      & Price and percent change versus the prior close \\
52w High/Low& Highest and lowest price over the cached window \\
1M Return   & Percent change over roughly the last month \\
YTD Return  & Percent change since the first session this year \\
Avg Vol     & Average daily volume over the window \\
Day Range   & The latest session's low and high \\
\bottomrule
\end{tabular}
\end{center}
Fields show \texttt{n/a} when there is not enough cached history to compute them
(for example YTD right after a fresh install). Run \texttt{bbterm-sync} to fill
the cache.

\section{Costs}
bbterm uses Databento's historical API only, never a live subscription. A full
year of daily bars for one symbol costs a fraction of a cent, and cached data is
never re-purchased. Each request is checked against a configurable cost cap
(\$1 by default) before it runs.

\end{document}
```

- [ ] **Step 2: Add a local gitignore for build artifacts**

```bash
cat > docs/manual/.gitignore <<'EOF'
*.aux
*.log
*.out
*.toc
EOF
```

- [ ] **Step 3: Compile to PDF (run pdflatex twice for references)**

Run:
```bash
cd docs/manual && pdflatex -interaction=nonstopmode bbterm-guide.tex && pdflatex -interaction=nonstopmode bbterm-guide.tex; cd /Users/slee/bloomberg
```
Expected: `Output written on bbterm-guide.pdf` with no error lines. Verify:
```bash
ls -la docs/manual/bbterm-guide.pdf
```
Expected: the PDF exists and is non-empty.

- [ ] **Step 4: Sanity-check the PDF content**

Run: `.venv/bin/python -c "import pathlib; b=pathlib.Path('docs/manual/bbterm-guide.pdf').read_bytes(); print('pdf bytes:', len(b)); assert b[:4]==b'%PDF'"`
Expected: prints a positive byte count and does not assert.

- [ ] **Step 5: Commit (source + PDF, not build artifacts)**

```bash
git add docs/manual/bbterm-guide.tex docs/manual/.gitignore docs/manual/bbterm-guide.pdf
git commit -m "docs: bbterm LaTeX user guide compiled to PDF"
```

---

## Final verification (whole phase)

- [ ] Run the full suite: `.venv/bin/python -m pytest` — expect all green.
- [ ] Manual smoke (real terminal, needs a TTY): `.venv/bin/bbterm`, then:
  press `:`, type `ADD NVDA`, Enter → NVDA appears in the watchlist and survives
  a restart; press `:`, type `DES`, Enter → stats panel; `GP` → chart; `c` →
  candles/line toggle; `1`–`6` change range; `q` quits.
- [ ] Confirm `docs/manual/bbterm-guide.pdf` opens and reads correctly.

## Done criteria (maps to spec)

- Hybrid command bar with `:` focus / `Esc` blur — Tasks 1, 4, 6.
- Candlestick + volume chart with `c` line toggle — Task 3, 6.
- Bar-derived DES stats panel — Tasks 2, 5, 6.
- Persisted `ADD`/`DEL` watchlist editing, last-symbol guard — Task 6.
- LaTeX user guide compiled to PDF — Task 7.
- No new data sources; test suite spends no credits — all tasks.
