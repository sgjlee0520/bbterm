# Phase 4 — SEC EDGAR Fundamentals & Filings

**Status:** Approved (user delegated; "I trust you, finish the EDGAR building", 2026-06-18)
**Date:** 2026-06-18

## Goal

Add company fundamentals and recent SEC filings to bbterm, sourced entirely from
**SEC EDGAR** — free, official, and commercially usable (unlike yfinance). This
fills the biggest gap versus a real terminal while keeping the "sellable later"
licensing path clean.

EDGAR provides filings and structured XBRL financials, **not** a general news
wire. So "news" here means *recent filings* (10-K / 10-Q / 8-K, etc.) and
"fundamentals" means *XBRL company-facts* (revenue, net income, EPS, etc.).

## Scope

Two new `ContentSwitcher` views, each with its own command verb, matching the
existing `GP` (chart) / `DES` (stats) pattern:

- `FA`  → **FundamentalsView**: latest reported value per metric **+ YoY %**.
- `FIL` → **FilingsView**: list of recent filings (form, date, period, URL).

Out of scope: trailing multi-year tables, press-release/headline news, any paid
or non-commercial source, intraday fundamentals.

## Data layer

### Models (`data/models.py`)

```python
@dataclass(frozen=True)
class FundamentalMetric:
    label: str          # "Revenue"
    value: float        # 391_035_000_000
    unit: str           # "USD" | "USD/shares" | "shares"
    period_end: date    # 2024-09-28
    fy: int             # 2024
    fp: str             # "FY"
    yoy_pct: float | None   # +2.0, or None if no prior-year value

@dataclass(frozen=True)
class Filing:
    form: str           # "10-K"
    filed_date: date    # 2024-11-01
    period: str         # report period (may be "")
    accession: str      # "0000320193-24-000123"
    url: str            # human-readable EDGAR filing index URL
```

### Provider (`data/providers/edgar.py`)

`EdgarProvider` implements two new Protocols in `providers/base.py`, both
returning **raw JSON** (so the service can cache it verbatim and let the pure
extractors do the parsing): `FundamentalsProvider.get_facts(symbol) -> dict` and
`FilingsProvider.get_submissions(symbol) -> dict`.

- HTTP via stdlib `urllib.request` (zero new dependencies). All requests carry
  `User-Agent: bbterm/0.1 (yagurootajum@gmail.com)` as SEC requires, and a small
  inter-request sleep to respect the ~10 req/sec limit.
- Ticker→CIK resolution via `https://www.sec.gov/files/company_tickers.json`,
  fetched once per session and cached **in memory** (keeps the provider
  self-contained, no store dependency); zero-padded to 10 digits for API paths.
- Facts:    `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json`
- Filings:  `https://data.sec.gov/submissions/CIK{cik10}.json`
- Sync provider, called from the service via `asyncio.to_thread`, like the
  Databento/yfinance providers.

### Pure logic (`data/fundamentals.py`) — zero I/O, unit-tested

- `MetricSpec(label, concepts, unit)` and an ordered `METRIC_SPECS` table mapping
  display labels to candidate XBRL concept names (companies report under
  different concepts; first match wins). Metrics:
  Revenue, Net Income, EPS (diluted), Gross Profit, Total Assets,
  Total Liabilities, Stockholders' Equity, Operating Cash Flow,
  Shares Outstanding.
- `extract_fundamentals(facts_json) -> list[FundamentalMetric]`: for each spec,
  find the latest annual (`fp == "FY"`) datapoint, find the prior fiscal year's
  value, compute YoY %. Omit metrics the company never reports.
- `parse_filings(submissions_json, limit=20) -> list[Filing]`: flatten SEC's
  columnar `filings.recent` arrays into `Filing` rows, newest first, build the
  human filing-index URL from CIK + accession.

### Store (`data/store.py`)

Two cache tables in the existing `market.duckdb` (raw JSON cached so extraction
logic can evolve without re-fetching). The ticker→CIK map is kept in provider
memory, not the store.

```sql
CREATE TABLE edgar_facts   (symbol VARCHAR PRIMARY KEY, fetched_at TIMESTAMP, json VARCHAR);
CREATE TABLE edgar_filings (symbol VARCHAR PRIMARY KEY, fetched_at TIMESTAMP, json VARCHAR);
```

Getter/setter methods mirror the existing bar/watchlist accessors.

## Service (`data/service.py`)

`get_fundamentals(symbol) -> list[FundamentalMetric]` and
`get_filings(symbol) -> list[Filing]`:

- Cache-through with a **24h TTL** keyed on `fetched_at`. On miss/stale, fetch via
  `asyncio.to_thread`, persist raw JSON, then run the pure extractor.
- On fetch failure, degrade to cached JSON if present (mirrors `_bars_for`); if
  nothing cached, raise/return empty so the app can show a notice.
- All fetches reuse the app's single DB connection — no second process, honoring
  DuckDB's single-writer file lock.

## UI

### Commands (`commands.py`)

Add `ShowFundamentals` and `ShowFilings` dataclasses; `FA` → ShowFundamentals,
`FIL` → ShowFilings. Unit-tested.

### Widgets

- `tui/widgets/fundamentals.py` — `FundamentalsView(Widget)` with `.show(metrics)`;
  a `render_fundamentals_text(metrics)` pure helper building a labeled table:
  metric · humanized value (`$391.04B`, `$6.08`, `15.12B sh`) · `FY2024` · YoY %
  (sign-colored). Reuses/extends the humanizing helpers from `stats.py`.
- `tui/widgets/filings.py` — `FilingsView(Widget)` with `.show(filings)`;
  a `render_filings_text(filings)` pure helper: form · filed date · period · URL.

### App (`tui/app.py`)

- Add `FundamentalsView(id="fundamentals")` and `FilingsView(id="filings")` to the
  `ContentSwitcher`.
- `_dispatch` handles the two new commands: set `switcher.current` and launch a
  worker.
- Workers `load_fundamentals` / `load_filings` (`@work(exclusive=True, group=...)`)
  call the service and `.show(...)` the result; degrade-to-notice on failure.
- Footer/help text updated to mention `FA` and `FIL`.

## Error handling

- Unknown ticker / no CIK → `notify("No SEC filer found for X")`, empty panel.
- Network/HTTP failure → degrade to cached JSON if present, else
  `notify("EDGAR unavailable")`. No cost-cap path (EDGAR is free).
- Company missing a metric → row omitted (pure extraction handles it).

## Testing (no network)

- `tests/fixtures/` — trimmed real `companyfacts` + `submissions` JSON payloads.
- `test_fundamentals.py` — `extract_fundamentals` (YoY math, missing-metric
  omission, concept-fallback order) and `parse_filings`.
- `test_commands.py` — `FA` / `FIL` parse to the right commands.
- `test_app_commands.py` — `FA` / `FIL` switch the `ContentSwitcher`, using a
  `FakeEdgarProvider` (no network).
- Manual smoke script (excluded from the test run) hits live EDGAR once to verify
  User-Agent acceptance and CIK resolution.

## Non-goals / constraints carried forward

- Do **not** reintroduce yfinance for fundamentals (commercial-licensing reason).
- Tests must spend no Databento credits and make no network calls.
- Keep widgets dumb; all parsing/derivation in pure, tested modules.
```
