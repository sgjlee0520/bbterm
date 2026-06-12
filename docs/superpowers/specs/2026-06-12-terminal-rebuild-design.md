# Terminal Rebuild Design — Local Market Terminal on Databento + DuckDB

**Date:** 2026-06-12
**Status:** Draft, awaiting user review

## Goals and constraints

- Runs locally on macOS, single user, with potential to become a product later.
- Minimum recurring cost: spend Databento credits only on data we keep; no live
  data subscriptions (the expensive tier); free sources only where license-safe.
- Replace yfinance as the primary source — it is unofficial scraping, rate-limited,
  and prohibited for commercial use. It remains as a dev-only fallback behind a
  provider interface so it can be deleted without touching the UI.

## Assessment of current code (what is kept / dropped)

| Piece | Verdict |
|---|---|
| Textual TUI framework | Keep |
| Widget split (watchlist / chart / strip) | Keep, port to async |
| plotext charts | Keep for now |
| Synchronous yfinance calls on UI thread | Drop — blocks UI 10s+ per refresh |
| yfinance as primary data source | Demote to dev fallback provider |
| No storage (DuckDB unused) | Replace with cache-through DuckDB store |
| Hard-coded watchlist | Move to persisted store |

## Architecture

```
bloomberg/
  pyproject.toml
  src/bbterm/
    config.py                 # env: DATABENTO_API_KEY, cost cap, db path
    data/
      providers/base.py       # Provider protocol: get_bars(), get_quote(), search()
      providers/databento_.py # historical API only (credits), cost guardrail
      providers/yfinance_.py  # dev/fallback, isolated behind the protocol
      store.py                # DuckDB: ohlcv, symbols, watchlists tables
      service.py              # async cache-through: store first, fetch missing ranges only
    tui/
      app.py                  # async refresh via Textual workers
      widgets/                # watchlist, chart, strip, command bar
  data/market.duckdb          # gitignored
  tests/
```

### Data flow

UI widgets never call providers directly. They call `DataService` (async), which:
1. Queries DuckDB for the requested symbol/date range.
2. Fetches only the missing range from the active provider.
3. Appends to DuckDB, returns the merged frame.

Result: each Databento record is paid for at most once, and the app works offline
for anything already fetched.

### Databento usage (cost control)

- Historical API only, against credits. Daily OHLCV (`ohlcv-1d`) from a low-cost
  consolidated US equities dataset; intraday `ohlcv-1m` fetched on demand for
  short chart periods and cached.
- Before every historical request, call the metadata cost endpoint; abort and
  surface the price if it exceeds a configurable cap (default $1 per request).
- No live/streaming subscription. "Live-ish" quotes come from periodic refresh
  (latest cached bar + dev fallback provider while developing).

### Concurrency

All network and DB I/O runs in Textual workers / threads. The UI thread renders
only. Startup shows cached data immediately, then refreshes in the background.

## Error handling

- Provider failures degrade to cached data with a stale-data indicator in the UI,
  never a crash or a freeze.
- Missing `DATABENTO_API_KEY` → app runs in fallback mode and says so in the UI.
- Cost cap exceeded → request refused with the quoted cost shown.

## Testing

- pytest. `DataService` and store tested with a fake in-memory provider and a
  temp DuckDB file. Databento provider tested against recorded responses; no
  credits spent in tests.

## Phases

1. **Foundation:** git init, pyproject + src layout, config, DuckDB store,
   provider protocol with yfinance provider ported, async TUI refactor.
   Exit criteria: same features as today, zero UI freezes, data cached locally.
2. **Databento:** historical provider (daily + intraday bars), cost guardrail,
   end-of-day sync command for the watchlist.
3. **Terminal features:** Bloomberg-style command bar (`AAPL G`, `AAPL DES`,
   watchlist add/remove), candlestick + volume charts, persisted watchlists.
4. **Later (business track):** fundamentals via SEC EDGAR (free), news,
   packaging/distribution, and only then evaluate a web UI and redistribution
   licensing — out of scope for this spec.

## Alternatives considered

- **Patch the existing app** (add async + caching, keep yfinance primary):
  cheapest now, but builds the product on a source that cannot be commercialized
  and ignores the credits already paid for. Rejected.
- **Jump to a web app** (FastAPI + React): more sellable eventually, but doubles
  scope before the data layer exists. The data layer designed here is UI-agnostic,
  so a web client can be added later without rework. Deferred.
