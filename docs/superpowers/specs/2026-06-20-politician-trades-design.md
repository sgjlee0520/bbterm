# Politician Trades — Congressional Buy/Sell for a Symbol (`POL`)

**Date:** 2026-06-20
**Status:** Approved (brainstorming, 2026-06-20). Data source **Lambda Finance**,
confirmed working on the free tier via a live test (see below).
**Builds on:** the EDGAR/news provider→cache→pure-parser→view→command pattern.

## Goal

Add a **`POL`** command that shows, for the currently-loaded stock, recent
**buy/sell trades by a curated list of politicians**, plus a derived per-politician
**net-activity summary**. Data comes from **Lambda Finance's congressional API**.

## Data-reality constraints (locked during brainstorming)

- Source = **Congressional STOCK Act disclosures**; covers **members of Congress
  only**.
- **Trump family: excluded** — not in Congress; no disclosure data exists.
- **JD Vance: historical only** — Senate trades through early 2025; he's now VP and
  files nothing. His trades are >1 year old and may fall outside the query window,
  so he will rarely/never appear. Kept on the roster but flagged.
- **Share counts do not exist** — amounts are **dollar ranges** (e.g.
  `$15,001 - $50,000`). "How many shares" is unanswerable.
- **Current holdings** are a separate annual filing not in this feed; out of scope.
  We derive a **net-activity estimate** from the transactions, labeled approximate.

## Source — Lambda Finance (live-test confirmed)

```
GET https://www.lambdafin.com/api/congressional/recent?ticker={SYMBOL}&days={DAYS}
Headers: Authorization: Bearer {LAMBDA_API_KEY}
         User-Agent: <a normal browser UA>     # REQUIRED — Cloudflare blocks Python's default UA (error 1010)
         Accept: application/json
```

- **Key:** free Lambda account (100 requests/month), read from env
  **`LAMBDA_API_KEY`** (optional, like `DATABENTO_API_KEY`). No key → the view shows
  a "set LAMBDA_API_KEY to enable politician trades" notice; nothing crashes.
- **`days`:** the endpoint defaults to 30 days; we request **`days=730`** for a
  2-year history. (Free tier allows it; we cache to respect the 100/month quota.)
- **Response shape (confirmed):**
  `{"trades": [ {...}, ... ], "count": N, "days": 730}`.
- **Per-trade fields (confirmed):** `symbol`, `representative` (name),
  `transactionDate` (YYYY-MM-DD), `disclosureDate`, `type` (`Purchase` / `Sale` /
  `Sale (Partial)` / `Exchange` …), `amount` (range string `"$1,001 - $15,000"`),
  `owner` (`Self`/`Spouse`), `chamber` (`house`/`senate`), `party`, `state`,
  `district`, `ptrLink`, `assetDescription`.

### Live test result (2026-06-20)

`ticker=NVDA&days=365` → 200, 36 trades, both chambers; roster members **Gilbert
Cisneros** and **Jefferson Shreve** present. The de-risk gate is **passed**; the
fields above are real, not guessed.

## Curated roster

A constant in `data/congress.py` (editable). Lambda uses full legal names, so the
roster stores those and matching is tolerant of first-name variants:

```
Nancy Pelosi, Jim Justice, Jefferson Shreve, Rick Scott, Mark Warner,
Pete Ricketts, Darrell Issa, Michael McCaul, Ro Khanna, Gilbert Cisneros (Gil),
JD Vance (historical)
```

The view shows **only** roster members (Lambda returns all of Congress for the
ticker; we filter down).

## Data layer

### Model (`data/models.py`)

```python
@dataclass(frozen=True)
class CongressTrade:
    politician: str       # "Gilbert Cisneros"
    chamber: str          # "house" | "senate"
    side: str             # "BUY" | "SELL"
    amount_low: float     # 15001.0
    amount_high: float    # 50000.0
    date: date            # transactionDate
```

### Provider (`data/providers/lambdafin_.py`)

`CongressProvider` mirrors `EdgarProvider`: stdlib `urllib`, **injectable fetcher**
so tests use no network.
- `name = "lambdafin"`; constructed with the API key.
- Sends the Bearer header **and a browser User-Agent** (required).
- `get_congress_trades(symbol, days=730) -> dict` returns the **raw JSON**.

### Pure logic (`data/congress.py`) — zero I/O, unit-tested

- `CONGRESS_ROSTER: list[str]` — curated full names.
- `_parse_amount(s) -> tuple[float, float]` — `"$15,001 - $50,000"` →
  `(15001.0, 50000.0)`; a single value or unparseable → `(0.0, 0.0)`.
- `parse_congress_trades(json) -> list[CongressTrade]` — read the `trades` array;
  map `type` (`Purchase`→`BUY`, anything starting `Sale`→`SELL`; skip others like
  `Exchange`); parse `amount`, `transactionDate`, `chamber`, `representative`.
- `filter_to_roster(trades, roster=CONGRESS_ROSTER) -> list[CongressTrade]` —
  match on **last name + first-name prefix** (so roster `Gil Cisneros` matches
  `Gilbert Cisneros`; `Nancy Pelosi` matches `Nancy Pelosi`), case-insensitive.
  Newest first.
- `summarize(trades) -> list[PoliticianSummary]` with
  `PoliticianSummary(politician, n_buys, n_sells, net_estimate)` where
  `net_estimate = Σ midpoint(buys) − Σ midpoint(sells)`,
  `midpoint = (amount_low + amount_high)/2`. Labeled approximate in the UI.

### Store (`data/store.py`)

```sql
CREATE TABLE IF NOT EXISTS congress_trades (symbol VARCHAR PRIMARY KEY, fetched_at TIMESTAMP, json VARCHAR);
```

`get_congress(symbol)` / `set_congress(symbol, text)` reuse `_get_edgar`/`_set_edgar`.

### Service (`data/service.py`)

`get_congress_trades(symbol) -> list[CongressTrade]`:
- Cache-through, **24h TTL** (`CONGRESS_TTL_SECONDS = 86400.0`), degrade to cache on
  failure, `[]` when nothing cached — like `get_news`. The long cache also protects
  the 100/month Lambda quota.
- No `lambda_api_key` configured → return `[]` (view shows the key notice).
- Returns roster-filtered, newest-first trades.

### Config (`config.py`)

Add `lambda_api_key: str | None` from `LAMBDA_API_KEY`.

## UI

### Command (`commands.py`)

Add `ShowPoliticians`; verb **`POL`** → `ShowPoliticians`. Unit-tested.

### Widget (`tui/widgets/politicians.py`)

- `PoliticiansView(Widget)` with `.show(trades, has_key)`.
- `render_politicians_text(trades) -> str` pure helper: grouped by politician, each
  group led by a **summary line**
  (`Nancy Pelosi (house) — 3 buys · 1 sell · net ≈ +$200K (est.)`) then that
  politician's trades (`BUY   $15,001 - $50,000   2025-11-18`), newest first.
- Empty states: no key → "Set LAMBDA_API_KEY to enable politician trades.";
  otherwise → "No congressional trades for {symbol}."

### App (`tui/app.py`)

- Add `PoliticiansView(id="politicians")` to the `ContentSwitcher`.
- `_dispatch` handles `ShowPoliticians`: switch + `load_politicians()` worker.
- Worker mirrors `load_news`; degrade-to-notice on error.
- Help text gains `POL congress`.

## Error handling

- No key → key notice, empty view, no crash.
- HTTP/network/Cloudflare failure → degrade to cached JSON if present, else
  "unavailable".
- Empty/odd payload → "No congressional trades for {symbol}."

## Testing (no network, no key)

- `tests/fixtures/congress_nvda.json` — a trimmed real Lambda payload (from the live
  test) with a couple roster names + a non-roster name + a `Sale` and a `Purchase`.
- `test_congress.py` — `_parse_amount`, `parse_congress_trades` (type mapping,
  amount/date), `filter_to_roster` (Gil↔Gilbert match, drops non-roster),
  `summarize` (counts + net midpoint math).
- `test_commands.py` — `POL` → `ShowPoliticians`.
- `test_service_congress.py` — fake provider: parse + cache + degrade + no-key → [].
- `test_app_commands.py` — `POL` switches the `ContentSwitcher`, fake provider.
- `render_politicians_text` test (summary line + trade rows + both notices).
- `scripts/smoke_congress.py` — manual live check (reads `LAMBDA_API_KEY`).

## Out of scope

Real holdings/share counts (don't exist), net-worth, non-roster politicians, trade
alerts, executive-branch (Trump / Vance-as-VP) data.
