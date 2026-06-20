# Image Candlestick Charts + Pick-and-Open Filings — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render crisp mplfinance candlestick images in the terminal (iTerm2) with a text fallback, and make SEC filings a selectable list that opens in the browser on Enter.

**Architecture:** A pure `render_candles_png(bars, symbol, period_label) -> bytes` builds a PNG via mplfinance; `ChartPanel` shows it through `textual-image`'s `Image` widget when a real graphics protocol is available, else falls back to the existing plotext text chart. `FilingsView` becomes a Textual `OptionList`; selecting a row opens its URL via an injectable opener.

**Tech Stack:** mplfinance + matplotlib (Agg) + pandas → PNG; textual-image (Sixel/TGP) for display; Textual `OptionList`; pytest.

## Global Constraints

- Chart libraries are **bundled** (core deps): `matplotlib>=3.8`, `mplfinance>=0.12.10b0`, `textual-image>=0.13`.
- **Version bump to `0.2.0`.**
- **Graceful fallback:** no graphics protocol → existing plotext text chart. Line view stays text.
- **Filings open via keypress** (selectable list + Enter), browser opener **injectable** so tests make no real browser/network calls.
- Tests make **no network calls** and need **no real screen/tty** (image path is verified manually, not in pytest).
- Matplotlib must use the **Agg** backend (set before importing mplfinance) so rendering needs no display.
- Work on the existing **`image-charts`** branch.
- **Task 1 is a manual gate:** the crisp-image proof in iTerm2 must pass before Tasks 2–5.

---

### Task 1: Add dependencies, bump version, and the Step-0 proof (GATE)

**Files:**
- Modify: `pyproject.toml`
- Create: `scripts/proof_chart.py`

**Interfaces:**
- Produces: installed `matplotlib`/`mplfinance`/`textual-image`; a runnable proof script.

- [ ] **Step 1: Add deps and bump version in `pyproject.toml`**

In `[project].dependencies`, add the three lines:
```toml
    "matplotlib>=3.8",
    "mplfinance>=0.12.10b0",
    "textual-image>=0.13",
```
and change `version = "0.1.2"` to `version = "0.2.0"`.

- [ ] **Step 2: Reinstall**

Run: `.venv/bin/pip install -e ".[dev,databento]"`
Expected: installs matplotlib, mplfinance, textual-image (+ Pillow) without error.

- [ ] **Step 3: Create the proof script**

Create `scripts/proof_chart.py`:

```python
"""Step-0 proof — render a sample candlestick IMAGE in your terminal.
Run in iTerm2:  .venv/bin/python scripts/proof_chart.py   (press q to quit)
You should see a CRISP candlestick chart, not blocky colored blocks."""
import io
import random
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import mplfinance as mpf
import pandas as pd
from textual.app import App, ComposeResult
from textual.widgets import Label
from textual_image.renderable import Image as _Auto, SixelImage, TGPImage
from textual_image.widget import Image


def _sample_png() -> bytes:
    random.seed(1)
    base = datetime(2026, 1, 2)
    rows = {"Open": [], "High": [], "Low": [], "Close": [], "Volume": []}
    idx = []
    price = 100.0
    for i in range(40):
        op = price
        cl = op + random.uniform(-3, 3)
        rows["Open"].append(op)
        rows["Close"].append(cl)
        rows["High"].append(max(op, cl) + random.uniform(0, 2))
        rows["Low"].append(min(op, cl) - random.uniform(0, 2))
        rows["Volume"].append(random.randint(1_000_000, 5_000_000))
        idx.append(base + timedelta(days=i))
        price = cl
    df = pd.DataFrame(rows, index=pd.DatetimeIndex(idx))
    buf = io.BytesIO()
    mpf.plot(df, type="candle", volume=True,
             style=mpf.make_mpf_style(base_mpf_style="nightclouds"),
             title="SAMPLE — candlestick proof",
             savefig=dict(fname=buf, format="png", dpi=100, bbox_inches="tight"))
    return buf.getvalue()


class Proof(App):
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        crisp = _Auto in (SixelImage, TGPImage)
        yield Label(
            f"Renderer: {_Auto.__name__}  "
            + ("(graphics protocol — should be crisp)" if crisp
               else "(NO graphics protocol — will look blocky)")
            + "   ·  press q to quit"
        )
        yield Image(_sample_png())


if __name__ == "__main__":
    Proof().run()
```

- [ ] **Step 4: Commit the setup**

```bash
git add pyproject.toml scripts/proof_chart.py
git commit -m "build: bundle chart libs, bump 0.2.0, add Step-0 proof script

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 5: MANUAL GATE — run the proof in iTerm2**

The user runs, in **iTerm2**:
```bash
.venv/bin/python scripts/proof_chart.py
```
Expected: a crisp candlestick chart image appears; the top label says a graphics
protocol (Sixel/TGP) was selected. Press `q` to quit.

**Decision point:**
- **Crisp** → proceed to Task 2.
- **Blocky / label says "NO graphics protocol"** → STOP. The terminal isn't
  exposing Sixel/TGP. Troubleshoot (update iTerm2; iTerm2 → Settings → enable
  Sixel/graphics if available) and re-run. Do not build Tasks 2–5 until this is
  crisp, or reconsider the approach.

---

### Task 2: Pure PNG builder + capability check

**Files:**
- Create: `src/bbterm/tui/widgets/chart_image.py`
- Test: `tests/test_chart_image.py`

**Interfaces:**
- Consumes: `Bar`.
- Produces: `render_candles_png(bars: list[Bar], symbol: str, period_label: str) -> bytes`; `image_charts_available() -> bool`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_chart_image.py`:

```python
from datetime import datetime, timedelta

from bbterm.data.models import Bar
from bbterm.tui.widgets.chart_image import image_charts_available, render_candles_png

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _bars(n=20):
    base = datetime(2026, 1, 2)
    return [
        Bar("AAPL", "1d", base + timedelta(days=i),
            100 + i, 101 + i, 99 + i, 100.5 + i, 1_000_000 + i)
        for i in range(n)
    ]


def test_render_candles_png_returns_png_bytes():
    data = render_candles_png(_bars(), "AAPL", "1 Month")
    assert data[:8] == _PNG_SIG
    assert len(data) > 1000


def test_image_charts_available_returns_bool():
    # In the headless test environment this is False; just assert it is a bool
    # and does not raise.
    assert isinstance(image_charts_available(), bool)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_chart_image.py -v`
Expected: FAIL — `ModuleNotFoundError: bbterm.tui.widgets.chart_image`.

- [ ] **Step 3: Write the module**

Create `src/bbterm/tui/widgets/chart_image.py`:

```python
from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # render without a display; must precede mplfinance import

import mplfinance as mpf  # noqa: E402
import pandas as pd  # noqa: E402

from bbterm.data.models import Bar  # noqa: E402

_STYLE = mpf.make_mpf_style(base_mpf_style="nightclouds")


def render_candles_png(bars: list[Bar], symbol: str, period_label: str) -> bytes:
    df = pd.DataFrame(
        {
            "Open": [b.open for b in bars],
            "High": [b.high for b in bars],
            "Low": [b.low for b in bars],
            "Close": [b.close for b in bars],
            "Volume": [b.volume for b in bars],
        },
        index=pd.DatetimeIndex([b.ts for b in bars]),
    )
    buf = io.BytesIO()
    mpf.plot(
        df,
        type="candle",
        volume=True,
        style=_STYLE,
        title=f"{symbol} — {period_label}",
        savefig=dict(fname=buf, format="png", dpi=100, bbox_inches="tight"),
    )
    return buf.getvalue()


def image_charts_available() -> bool:
    """True only when textual-image auto-selected a real graphics protocol
    (Sixel or Kitty TGP). In a non-tty (tests) or a plain terminal this is False,
    and the caller falls back to the text chart."""
    try:
        from textual_image.renderable import Image as _Auto, SixelImage, TGPImage

        return _Auto in (SixelImage, TGPImage)
    except Exception:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_chart_image.py -v`
Expected: PASS — both. (A matplotlib font-cache message on first run is harmless.)

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/tui/widgets/chart_image.py tests/test_chart_image.py
git commit -m "feat: render_candles_png (mplfinance) and image-capability check

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Show image candles in `ChartPanel`, with text fallback

**Files:**
- Modify: `src/bbterm/tui/widgets/chart.py`
- Test: `tests/test_chart_render.py`

**Interfaces:**
- Consumes: `render_candles_png`, `image_charts_available`, `textual_image.widget.Image`.
- Produces: `ChartPanel` that shows an image for candle mode when graphics are available, else the existing text chart. Text/line behavior and `toggle_mode()` unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_chart_render.py`:

```python
def test_show_uses_text_when_images_unavailable(monkeypatch):
    import bbterm.tui.widgets.chart as chart_mod

    monkeypatch.setattr(chart_mod, "image_charts_available", lambda: False)
    panel = ChartPanel()
    panel._size_wh = (80, 24)
    # _render_candle returns the text plot (not image) when images are unavailable
    out = panel._render_candle("AAPL", "1 Month", _bars(), Quote("AAPL", 110, 100))
    assert out is None  # None signals "text path was used"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_chart_render.py::test_show_uses_text_when_images_unavailable -v`
Expected: FAIL — `ChartPanel` has no `_render_candle`.

- [ ] **Step 3: Update `ChartPanel`**

In `src/bbterm/tui/widgets/chart.py`, update imports at the top (note `import io`):

```python
import io

from textual_image.widget import Image

from bbterm.tui.widgets.chart_image import image_charts_available, render_candles_png
```

Add an `Image` widget to `compose` (hidden until used) and a body container.
Replace `compose` with:

```python
    def compose(self) -> ComposeResult:
        yield Label("", id="chart-header", classes="header")
        img = Image(id="chart-image")
        img.display = False
        yield img
        yield Static("", id="chart-plot", classes="plot")
```

Add `#chart-image { width: 100%; height: 1fr; }` to `DEFAULT_CSS` (inside the
existing CSS string).

Add a helper that returns the PNG for image-candle mode or `None` to mean "use
text", and route `show` through it. Replace the tail of `show` (the part after the
header block, starting at `if not bars:`) with:

```python
        if not bars:
            self.query_one("#chart-image", Image).display = False
            plot.update("  No data available for this symbol/period.")
            plot.display = True
            return

        png = self._render_candle(symbol, period_label, bars, quote)
        image = self.query_one("#chart-image", Image)
        if png is not None:
            # textual-image treats raw bytes as a file PATH; wrap in BytesIO so it
            # reads the PNG data.
            image.image = io.BytesIO(png)
            image.display = True
            plot.display = False
        else:
            plot.update(self._build_plot(symbol, period_label, bars, quote))
            plot.display = True
            image.display = False

    def _render_candle(self, symbol, period_label, bars, quote) -> bytes | None:
        """PNG bytes for an image candle chart, or None to use the text path
        (line mode, or no graphics protocol available)."""
        if self.mode != "candle" or not image_charts_available():
            return None
        try:
            return render_candles_png(bars, symbol, period_label)
        except Exception:
            return None
```

Keep `_build_plot`, `_dims`, `_apply_xticks`, and `toggle_mode` exactly as they
are (the text/line path and the candle fallback still use them).

- [ ] **Step 4: Run the chart tests**

Run: `.venv/bin/python -m pytest tests/test_chart_render.py -v`
Expected: PASS — the existing text/line/toggle tests plus the new fallback test.

- [ ] **Step 5: Confirm the app still mounts headless**

Run: `.venv/bin/python -m pytest tests/test_app_commands.py -q`
Expected: PASS — `GP` and the others still work (text path under pytest, since
`image_charts_available()` is False with no tty).

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/tui/widgets/chart.py tests/test_chart_render.py
git commit -m "feat: image candlestick charts in ChartPanel with text fallback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Filings as a selectable, open-in-browser list

**Files:**
- Modify: `src/bbterm/tui/widgets/filings.py`
- Modify: `src/bbterm/tui/app.py`
- Test: `tests/test_filings_open.py`

**Interfaces:**
- Consumes: `Filing`, an injectable `opener` defaulting to `webbrowser.open`.
- Produces: `FilingsView(opener=...)` with `.show(filings)`, a populated `OptionList`, and `_open_index(i)` that opens `filings[i].url` via the opener.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_filings_open.py`:

```python
from datetime import date

from bbterm.data.models import Filing
from bbterm.tui.widgets.filings import FilingsView


def _filing(form="10-K", url="https://sec.gov/x"):
    return Filing(form=form, filed_date=date(2026, 1, 5), period="2025", accession="a", url=url)


def test_open_index_calls_opener_with_url():
    opened = []
    fv = FilingsView(opener=opened.append)
    fv.show([_filing(url="https://sec.gov/aapl"), _filing(url="https://sec.gov/b")])
    fv._open_index(1)
    assert opened == ["https://sec.gov/b"]


def test_open_index_out_of_range_is_noop():
    opened = []
    fv = FilingsView(opener=opened.append)
    fv.show([])
    fv._open_index(0)
    assert opened == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_filings_open.py -v`
Expected: FAIL — `FilingsView()` takes no `opener`, no `_open_index`.

- [ ] **Step 3: Rewrite `FilingsView`**

Replace `src/bbterm/tui/widgets/filings.py` with:

```python
from __future__ import annotations

import webbrowser

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from bbterm.data.models import Filing


def _filing_label(f: Filing) -> str:
    return f"{f.form:<8}{f.filed_date.isoformat():<12}{f.period:<12}{f.url}"


class FilingsView(Widget):
    DEFAULT_CSS = """
    FilingsView { height: 1fr; }
    FilingsView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    FilingsView > Label.hint { color: $text-muted; padding: 0 1; }
    FilingsView > OptionList { height: 1fr; }
    """

    def __init__(self, opener=webbrowser.open, **kwargs) -> None:
        super().__init__(**kwargs)
        self._opener = opener
        self._filings: list[Filing] = []

    def compose(self) -> ComposeResult:
        yield Label("FILINGS", classes="header")
        yield Label("  ↑↓ select · Enter opens in browser", classes="hint")
        yield OptionList()

    def show(self, filings: list[Filing]) -> None:
        self._filings = filings
        olist = self.query_one(OptionList)
        olist.clear_options()
        if not filings:
            olist.add_option(Option("  No filings available.", disabled=True))
            return
        for f in filings:
            olist.add_option(Option(_filing_label(f)))

    def _open_index(self, index: int) -> None:
        if 0 <= index < len(self._filings):
            try:
                self._opener(self._filings[index].url)
            except Exception:
                pass  # never crash the UI on a failed open

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._open_index(event.option_index)
```

The old `render_filings_text` function is removed (the `OptionList` replaces the
text blob). The next step updates the two existing tests that referenced it.

- [ ] **Step 3b: Update `test_edgar_views.py` for the new filings API**

`test_edgar_views.py` imports the now-removed `render_filings_text`. Update it:

Change the filings import line:
```python
from bbterm.tui.widgets.filings import _filing_label
```

Replace `test_render_filings_lists_rows` with:
```python
def test_filing_label_has_form_date_url():
    f = Filing("10-K", date(2024, 11, 1), "2024-09-28",
               "0000320193-24-000123", "https://x/index.htm")
    label = _filing_label(f)
    assert "10-K" in label and "2024-11-01" in label and "https://x/index.htm" in label
```

In `test_empty_renders_message`, remove the filings line so only the fundamentals
assertion remains:
```python
def test_empty_renders_message():
    assert "No" in render_fundamentals_text([])
```

- [ ] **Step 4: Focus the filings list when `FIL` runs**

In `src/bbterm/tui/app.py`, in `_dispatch`, change the `ShowFilings` branch to focus
the list:

```python
        elif isinstance(command, ShowFilings):
            self.query_one("#switcher", ContentSwitcher).current = "filings"
            self.load_filings()
            self.query_one(FilingsView).query_one("OptionList").focus()
```

Update the `_HELP` string — change `FIL filings` to `FIL filings (Enter opens)`.

- [ ] **Step 5: Run filings + app tests**

Run: `.venv/bin/python -m pytest tests/test_filings_open.py tests/test_app_commands.py tests/test_edgar_views.py -v`
Expected: PASS — new open tests, the updated `_filing_label` test, `FIL` still
switches the view, and the fundamentals tests.

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/tui/widgets/filings.py src/bbterm/tui/app.py tests/test_filings_open.py tests/test_edgar_views.py
git commit -m "feat: filings as selectable list; Enter opens in browser

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: README, full suite, and manual visual check

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Note the new behavior in the README**

Under the Keys & commands section, add two rows (match the existing table format):
```markdown
| `GP` | Candlestick chart — crisp image in image-capable terminals (iTerm2), text elsewhere |
| `FIL` | Filings list — ↑↓ to select, Enter opens the filing in your browser |
```
And add a one-line note: "Image charts use Sixel/Kitty graphics; on other terminals
bbterm falls back to text charts automatically."

- [ ] **Step 2: Full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — no failures (existing tests + the new chart-image, chart-fallback,
and filings-open tests).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: image charts and Enter-to-open filings in README

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 4: MANUAL visual check in iTerm2**

The user runs `bbterm` in iTerm2:
- Load a ticker, press `GP` → a crisp candlestick image renders.
- Press `c` → clean line view (text).
- Press `FIL` → arrow-key through filings, press Enter → the filing opens in the
  browser.

---

## Notes for the implementer

- The branch is already `image-charts`.
- Tasks 2–5 are gated on Task 1's proof being **crisp** in iTerm2. If it is not,
  stop and report rather than building on a broken display assumption.
- `matplotlib.use("Agg")` must run before mplfinance is imported (handled in
  `chart_image.py`).
- The image path is verified manually (Task 1 + Task 5), not in pytest — pytest
  runs headless where `image_charts_available()` is False and the text path is used.
