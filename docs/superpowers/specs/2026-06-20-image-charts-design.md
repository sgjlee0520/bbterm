# Image Candlestick Charts + Pick-and-Open Filings

**Date:** 2026-06-20
**Status:** Approved (brainstorming, 2026-06-20)
**Builds on:** the existing `ChartPanel` (plotext text charts) and `FilingsView`.

## Goals

1. **Crisp candlestick charts** rendered as real images (mplfinance → PNG, shown
   via `textual-image`) in image-capable terminals (the user runs **iTerm2**),
   replacing the noisy text candlesticks.
2. **SEC filings you can actually open** — make the filings view a selectable list
   where you highlight a filing and press **Enter** to open it in the browser.

## Hard constraint: prove the risky part first

The one genuinely uncertain piece is whether a chart image displays crisply inside
a Textual app in the user's iTerm2. **Before building the feature**, the user runs a
throwaway proof script in iTerm2 that renders a sample candlestick image via the
real stack (mplfinance + textual-image). Only if it looks crisp do we proceed.
This is the first task in the plan and gates everything after it.

## Decisions (locked during brainstorming)

- **Chart libraries are bundled** (core dependencies, not an optional extra):
  `matplotlib`, `mplfinance`, `textual-image`.
- **Filings open via keypress**: a selectable list + Enter → open in browser
  (more reliable than clickable links across terminals).
- **Graceful fallback**: when no terminal image protocol is available, candles fall
  back to the existing plotext text chart. The line view (`c`) stays text.
- **Version bump to `0.2.0`** (visible upgrade + new dependencies).

## Dependencies (`pyproject.toml`)

Add to core `dependencies`:

```
"matplotlib>=3.8",
"mplfinance>=0.12.10b0",
"textual-image>=0.13",
```

(`mplfinance` pulls `matplotlib`; `textual-image` pulls `Pillow`. `pandas` is
already a dependency.) Bump `version` to `0.2.0`.

## Chart rendering

### Pure image builder (`tui/widgets/chart_image.py`) — testable, no screen

`render_candles_png(bars, symbol, period_label, up=True, width_px=1000, height_px=600) -> bytes`:

- Build a pandas `DataFrame` indexed by each bar's timestamp with columns
  `Open, High, Low, Close, Volume`.
- Render with mplfinance to an in-memory PNG buffer:
  `mpf.plot(df, type="candle", volume=True, style=<dark style>, returnfig` or
  `savefig=dict(fname=buf, format="png", dpi=...))`. Use a dark style
  (`mpf.make_mpf_style(base_mpf_style="nightclouds", ...)`) so it matches the TUI.
- Return the PNG `bytes`. Pure (no widget, no I/O beyond the in-memory buffer) —
  unit-tested by asserting the result starts with the PNG signature
  `b"\x89PNG\r\n\x1a\n"` and is non-trivially sized.

### Terminal capability check

A small helper decides whether real image rendering is available (a supported
graphics protocol such as iTerm2/Kitty/Sixel), using `textual-image`'s terminal
query. If unavailable → use the text fallback. This keeps bbterm working on plain
Terminal.app and over SSH.

### `ChartPanel` integration (`tui/widgets/chart.py`)

- Keep the existing header and the text `Static` (used for line mode and the
  candle **fallback**).
- Add a `textual-image` `Image` widget for image-mode candles. On `show(...)` with
  `mode == "candle"` and image support present: render the PNG, set it on the
  `Image` widget, and make the `Image` visible (hide the text `Static`); otherwise
  show the text `Static` (existing `_build_plot`). Line mode always uses text.
- `toggle_mode()` switches candle/line as today.
- `_build_plot` (text) is unchanged and retained as the fallback path, so the
  existing `test_chart_render.py` tests keep passing.

## Filings: pick-and-open (`tui/widgets/filings.py`, `tui/app.py`)

- Replace the flat `Static` body with a Textual **`OptionList`**: one option per
  filing, labelled `form · filed date · period`, with the filing's `url` stored
  alongside (e.g. an `{index: url}` map or the `Filing` carried on the option).
- `FilingsView.show(filings)` populates the `OptionList`.
- On `OptionList.OptionSelected` (fires on Enter), open the filing's URL via an
  injectable opener defaulting to `webbrowser.open` — injectable so tests pass a
  fake and make no network/browser calls.
- App focus: when `FIL` is dispatched, switch the `ContentSwitcher` to the filings
  view **and focus the `OptionList`** so arrow keys + Enter work. `:` still returns
  focus to the command bar (existing behavior).
- A short hint line ("↑↓ select · Enter opens in browser") is shown above the list.

## UI / help text

- Footer/help mentions that filings open with Enter.
- No new command verbs; `GP`/`FIL` behavior is unchanged apart from the above.

## Error handling

- Chart image render failure (bad data, mplfinance error) → log nothing noisy;
  fall back to the text chart for that render.
- No image protocol → text chart (by design, not an error).
- Filing open failure → `notify("Could not open filing")`; never crash.
- Empty filings → the list shows "No filings available." and Enter is a no-op.

## Testing (no network, no browser, no screen)

- `test_chart_image.py` — `render_candles_png` returns valid PNG bytes for sample
  bars (PNG signature + size > 0); handles a single bar without raising.
- `test_filings_open.py` — selecting a filing calls the injected opener with the
  correct URL; empty list selects nothing. Uses a fake opener (records calls).
- Existing `test_chart_render.py` (text/line path) stays green.
- `test_app_commands.py` — `FIL` still switches to the filings view (focus added).
- Manual proof: `scripts/proof_chart.py` in iTerm2 (the Step-0 gate) and a visual
  check of `GP` + `FIL` in the running app.

## Out of scope

- Image news/links (news view keeps text for now — possible later follow-up).
- Interactive chart zoom/pan, indicators/overlays.
- Sixel tuning for terminals other than the user's iTerm2 (fallback covers them).

## Risks

- **Image-in-Textual display** is the real unknown — mitigated by the Step-0 proof
  before any feature code.
- `OptionList` focus vs. single-key hotkeys: while the filings list has focus, app
  hotkeys (`c`, digits) are captured by the list; `:` always restores the command
  bar. Acceptable and documented.
