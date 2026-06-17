# Phase 3 Design — Command Bar, Candlestick Charts, Watchlist Editing

**Date:** 2026-06-12
**Status:** Draft, awaiting user review
**Builds on:** Phases 1–2 (`bbterm` package, async DataService, DuckDB store, Databento + yfinance providers).

## Goal

Make bbterm feel like a real terminal: keyboard-driven navigation via a command
bar, Bloomberg-style candlestick + volume charts, and a watchlist you can edit
and that persists. No new data sources — everything is computed from cached
OHLCV bars, so no credits are spent and no licensing problem is reintroduced.

## Scope (locked during brainstorming)

- **Hybrid command bar:** a bare ticker loads a symbol; known verbs act as
  commands (`ADD`, `DEL`, `GP`, `DES`, `?`/`HELP`).
- **Candlestick + volume chart**, with a key (`c`) to toggle to the line view.
- **Stats panel (DES)** computed purely from bars (last, 52w high/low, period
  returns, avg volume, day range).
- **Persisted watchlist editing** via `ADD`/`DEL` (uses existing
  `Store.set_watchlist`).

- **User guide:** a LaTeX manual (`docs/manual/bbterm-guide.tex`) compiled to
  PDF, written for someone who has never used a Bloomberg terminal — explains
  the layout, the command bar and `:` focus model, every command, the
  chart/stats views, and how to run `bbterm` and `bbterm-sync`.

Out of scope: fundamentals/news, fuzzy symbol search, multiple chart overlays.

## Layout & navigation

```
┌ Header ─────────────────────────────────────┐
│ : AAPL_                          (command)   │  command bar, docked top
├──────────┬──────────────────────────────────┤
│ WATCHLIST│  AAPL  291.52  -6.48 (-2.18%)     │
│ SPY  ... │  [ ChartPanel | StatsView ]       │  main = ContentSwitcher
│ AAPL ... │   ...                             │
├──────────┴──────────────────────────────────┤
│ SPY .. | QQQ .. | AAPL .. (ticker strip)     │
│ [GP]chart [DES]stats [c]line  q  ?=help      │  Footer
```

- **Focus key `:`** moves keyboard focus into the command bar; **`Esc`** blurs
  it back to the app. App-level single-key bindings (`1`–`6` period, `c`
  line/candle toggle, `r` refresh, `q` quit) fire **only when the command bar is
  not focused**, so typing `ADD AAPL` never triggers a hotkey.
- The right-hand area is a Textual `ContentSwitcher` holding `ChartPanel` (the
  existing widget) and `StatsView`. `GP` selects chart; `DES` selects stats.
  Loading a new symbol keeps the current view.

## Components

New/changed files, each with one responsibility:

| File | Responsibility |
|---|---|
| `src/bbterm/commands.py` | Pure `parse_command(text) -> Command`. No UI, no I/O. |
| `src/bbterm/data/stats.py` | Pure `compute_stats(bars, quote) -> Stats`. No UI, no I/O. |
| `src/bbterm/tui/widgets/command_bar.py` | `Input` subclass; emits a `Submitted` message with raw text. |
| `src/bbterm/tui/widgets/chart.py` | Add candlestick + volume rendering and a `line`/`candle` mode flag (modify existing). |
| `src/bbterm/tui/widgets/stats.py` | `StatsView` renders a `Stats` into a table. |
| `src/bbterm/tui/app.py` | Wire command bar, ContentSwitcher, focus handling, dispatch (modify existing). |

### Command model (`commands.py`)

```
Command = one of:
  LoadSymbol(symbol)        # bare ticker, e.g. "AAPL"
  AddSymbol(symbol)         # "ADD TSLA"
  RemoveSymbol(symbol)      # "DEL SPY"  (alias "REMOVE")
  ShowChart()               # "GP"
  ShowStats()               # "DES"
  Help()                    # "?" or "HELP"
  Unknown(text)             # anything else → error toast
```

Parsing rules: trim, collapse whitespace, uppercase the verb. First token is
matched against the verb table; if it's a known verb, the rest is its argument.
If the single token is not a verb and looks like a symbol (alphanumeric, 1–6
chars, optional `.`/`-`), it's `LoadSymbol`. Otherwise `Unknown`. A verb that
requires a symbol but gets none → `Unknown` (drives a helpful error toast).

### Stats model (`stats.py`)

```
Stats(symbol, last, change, pct_change, high_52w, low_52w,
      ret_1m, ret_ytd, avg_volume, day_low, day_high)
```

`compute_stats(bars, quote)` derives everything from the daily-bar list (already
cached) plus the latest quote. Returns are computed against the close N bars ago
(1M ≈ 21 trading days) and the first bar of the current calendar year (YTD).
Missing windows (not enough history) yield `None` for that field, rendered as
`n/a`. Pure function → exhaustive unit tests, no UI.

## Data flow

1. User presses `:`, types a command, presses Enter.
2. `CommandBar` emits `Submitted(text)`; the app calls `parse_command(text)`.
3. App dispatches on the `Command` type:
   - `LoadSymbol` → set `current_symbol`, re-run the existing `load_chart`/stats
     worker for the active view.
   - `AddSymbol`/`RemoveSymbol` → mutate `watchlist_symbols`, call
     `store.set_watchlist`, refresh the watchlist + strip workers, toast result.
   - `ShowChart`/`ShowStats` → switch the ContentSwitcher to `ChartPanel` /
     `StatsView`; ensure data for the view is loaded.
   - `Help` → toast with the command list.
   - `Unknown` → error toast.
4. App blurs the command bar (`Esc` behavior) after dispatch.

Stats need a year of daily bars for 52w/YTD; the app requests `1y` `1d` bars
through the existing `DataService` (cache-through — no refetch if already
synced). Candlesticks use the bars already loaded for the selected period.

## Error handling

- Empty/whitespace command → no-op, blur the bar.
- `Unknown` command and verbs missing required args → error toast, no state
  change, no crash.
- `ADD` of a symbol already present → toast "already in watchlist", no
  duplicate. `DEL` of a symbol not present → toast "not in watchlist".
- `DEL` that would empty the watchlist → refused with a toast (keep ≥1 symbol so
  `current_symbol` stays valid).
- Provider/chart failures keep the existing Phase-2 behavior: degrade to cached
  data with a warning toast.

## Testing

- `parse_command`: table-driven unit tests over every command form, aliases,
  bad input, and missing args.
- `compute_stats`: unit tests for full history, short history (None fields), YTD
  boundary, and zero/again edge cases — all with synthetic bars.
- Candlestick render: a unit test that `ChartPanel` in candle mode produces
  non-empty output for sample bars and the "no data" string when empty.
- App smoke test (headless `run_test`): focus bar with `:`, submit `ADD TSLA`
  and assert the watchlist grew and persisted; submit `DES` and assert the
  switcher shows `StatsView`; submit `GP` and assert it shows `ChartPanel`;
  press `c` and assert the chart mode flips. Uses the fake provider — no
  network, no credits.

## User guide deliverable

Written last, once the features are final so it documents real behavior. Lives
in `docs/manual/bbterm-guide.tex`, compiled with `pdflatex` (full TeX Live is
installed) to `docs/manual/bbterm-guide.pdf`. Audience: a first-time terminal
user. Contents:

- What bbterm is and the local/low-cost data model (Databento + cache).
- Screen layout walkthrough (watchlist, chart/stats panel, ticker strip,
  command bar) with an annotated ASCII diagram.
- The command bar and the `:` focus model explained from scratch, plus `Esc`.
- A command reference table: bare ticker, `ADD`, `DEL`, `GP`, `DES`, `?`.
- Keyboard shortcuts: `1`–`6` periods, `c` line/candle, `r` refresh, `q` quit.
- Reading the charts: candlesticks (body, wicks, color) and the volume panel;
  the stats panel fields.
- Getting started: install, set `DATABENTO_API_KEY`, `bbterm-sync`, `bbterm`.

A compile step (`pdflatex`, run twice for the table of contents) verifies the
PDF builds with no errors as the final task of the plan.

## Alternatives considered

- **Verb-only REPL** (`chart AAPL`, `add TSLA`): uniform but less
  Bloomberg-like; rejected in favor of bare-ticker loading.
- **Candles-only** (drop the line view): simpler, but the line view is cheap to
  keep and useful for long ranges; kept behind the `c` toggle.
- **yfinance fundamentals for DES**: rich but reintroduces the commercial-use
  problem we removed in Phase 1; rejected in favor of bar-derived stats.
