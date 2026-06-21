# Politician Trades — Congressional Buy/Sell for a Symbol (`POL`)

**Date:** 2026-06-20
**Status:** Approved (brainstorming, 2026-06-20)
**Builds on:** the EDGAR/news provider→cache→pure-parser→view→command pattern.

## Goal

Add a **`POL`** command that shows, for the currently-loaded stock, recent
**buy/sell trades by a curated list of politicians**, plus a derived per-politician
**net-activity summary**. Data comes from **Finnhub's congressional-trading API**.

## Data-reality constraints (locked during brainstorming)

- The only structured source of politician trades is **Congressional STOCK Act
  disclosures**. This covers **members of Congress only**.
- **Trump family: excluded** — not in Congress, no disclosure data exists anywhere.
- **JD Vance: historical only** — his Senate-era trades (through early 2025) are in
  the data; nothing since he became VP.
- **Share counts do not exist** in disclosures — amounts are **dollar ranges**
  (e.g. `$15,001–$50,000`). "How many shares" is unanswerable by any source.
- **Current holdings** come from a *different* (annual) filing not in Finnhub's free
  feed; out of scope. We derive a **net-activity estimate** from the transactions
  instead, clearly labeled approximate.

## Source

**Finnhub** congressional-trading endpoint, queried by symbol:
`https://finnhub.io/api/v1/stock/congressional-trading?symbol={SYMBOL}&token={KEY}`

- Requires a **free Finnhub API key**, read from env **`FINNHUB_API_KEY`** (optional,
  exactly like `DATABENTO_API_KEY`). No key → the view shows a "set FINNHUB_API_KEY
  to enable politician trades" notice; nothing crashes.
- **Live-test gate (de-risk):** before building the feature, a smoke script hits the
  live endpoint with the user's key for a known active ticker and prints the raw
  records. This confirms (a) the endpoint is on the free tier and (b) the **exact
  field names**, which the parser is then written against. If it's premium/empty,
  we pivot before investing. This is the first plan task and gates the rest.

### Expected response shape (to be confirmed by the live test)

Roughly `{"symbol": "AAPL", "data": [ {name, transactionDate, transactionType,
amountFrom, amountTo, ...}, ... ]}`. The parser's exact field reads are finalized
from the live-test output.

## Curated roster

A constant list in `data/congress.py` (editable):

```
Nancy Pelosi, Jim Justice, Jefferson Shreve, Rick Scott, Mark Warner,
Pete Ricketts, Darrell Issa, Michael McCaul, Ro Khanna, Gil Cisneros, JD Vance
```

The view shows **only** trades by people on this roster (Finnhub returns all of
Congress for the ticker; we filter down).

## Data layer

### Model (`data/models.py`)

```python
@dataclass(frozen=True)
class CongressTrade:
    politician: str       # "Nancy Pelosi"
    side: str             # "BUY" | "SELL"
    amount_low: float     # 15001
    amount_high: float    # 50000
    date: date            # transaction date
```

### Provider (`data/providers/finnhub_.py`)

`CongressProvider` mirrors `EdgarProvider`: stdlib `urllib`, **injectable fetcher**
so tests use no network.
- `name = "finnhub"`; constructed with the API key.
- `get_congress_trades(symbol) -> dict` returns the **raw JSON**.

### Pure logic (`data/congress.py`) — zero I/O, unit-tested

- `CONGRESS_ROSTER: list[str]` — the curated names.
- `parse_congress_trades(json) -> list[CongressTrade]` — flatten Finnhub's `data`
  array; map transactionType (`Purchase`→`BUY`, `Sale`/`Sale (partial)`→`SELL`);
  parse dates and amount range. Unknown/other types are skipped.
- `filter_to_roster(trades, roster=CONGRESS_ROSTER) -> list[CongressTrade]` —
  case-insensitive name match (normalize, match on the roster name appearing in the
  Finnhub name, handling `Last, First` ordering). Newest first.
- `summarize(trades) -> list[PoliticianSummary]` where
  `PoliticianSummary(politician, n_buys, n_sells, net_estimate)` and
  `net_estimate = Σ midpoint(buys) − Σ midpoint(sells)` using
  `midpoint = (amount_low + amount_high) / 2`. Labeled approximate in the UI.

### Store (`data/store.py`)

Cache table mirroring the EDGAR/news tables:

```sql
CREATE TABLE IF NOT EXISTS congress_trades (symbol VARCHAR PRIMARY KEY, fetched_at TIMESTAMP, json VARCHAR);
```

`get_congress(symbol)` / `set_congress(symbol, text)` reuse `_get_edgar`/`_set_edgar`.

### Service (`data/service.py`)

`get_congress_trades(symbol) -> list[CongressTrade]`:
- Cache-through, **24h TTL** (`CONGRESS_TTL_SECONDS = 86400.0`), degrade to cache
  on failure, `[]` when nothing cached, like `get_news`.
- If no `finnhub_api_key` configured → return `[]` (the view shows the key notice).
- Returns roster-filtered, newest-first trades.

### Config (`config.py`)

Add `finnhub_api_key: str | None` from `FINNHUB_API_KEY`.

## UI

### Command (`commands.py`)

Add `ShowPoliticians`; verb **`POL`** → `ShowPoliticians`. Unit-tested.

### Widget (`tui/widgets/politicians.py`)

- `PoliticiansView(Widget)` with `.show(trades)`.
- `render_politicians_text(trades) -> str` pure helper: grouped by politician, each
  group led by a **summary line** (`Nancy Pelosi — 3 buys · 1 sell · net ≈ +$200K (est.)`)
  followed by that politician's trades (`BUY  $15,001–$50,000  2024-01-15`),
  newest first. Empty → a notice: no key set → "Set FINNHUB_API_KEY…", else
  "No congressional trades for {symbol}."

### App (`tui/app.py`)

- Add `PoliticiansView(id="politicians")` to the `ContentSwitcher`.
- `_dispatch` handles `ShowPoliticians`: switch + `load_politicians()` worker.
- Worker mirrors `load_news`; degrade-to-notice on error.
- Help text gains `POL congress`.

## Error handling

- No key → key notice, empty view, no crash.
- HTTP/network failure → degrade to cached JSON if present, else "unavailable".
- Empty/odd payload → "No congressional trades for {symbol}."

## Testing (no network, no key)

- `tests/fixtures/` — a trimmed real Finnhub congressional payload (from the live
  test) with a couple roster names + a non-roster name.
- `test_congress.py` — `parse_congress_trades` (type mapping, amounts, dates),
  `filter_to_roster` (keeps roster, drops others, name-order handling),
  `summarize` (buy/sell counts, net midpoint math).
- `test_commands.py` — `POL` → `ShowPoliticians`.
- `test_service_congress.py` — fake provider: parse + cache + degrade + no-key → [].
- `test_app_commands.py` — `POL` switches the `ContentSwitcher`, fake provider.
- `render_politicians_text` test (summary line + trade rows + notices).
- `scripts/smoke_congress.py` — manual live check (the de-risk gate).

## Out of scope

Real holdings/share counts (don't exist), net-worth, non-roster politicians, trade
alerts, executive-branch (Trump/Vance-as-VP) data.
