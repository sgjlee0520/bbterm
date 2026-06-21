# Magic Formula — Greenblatt Ranking for a Symbol & Watchlist (`MF`)

**Date:** 2026-06-21
**Status:** Approved (brainstorming, 2026-06-21)
**Builds on:** the SEC EDGAR fundamentals already fetched/cached for the `FA` view.

## Goal

Add an **`MF`** command that scores stocks with Joel Greenblatt's **Magic Formula**
(*The Little Book That Still Beats the Market*). The view shows two things:

1. **The loaded stock's numbers** — Earnings Yield, Return on Capital, Enterprise
   Value.
2. **A ranked watchlist table** — every watchlist symbol scored and ranked by the
   combined Magic Formula (cheap *and* high-quality = best).

No new data source or API key — it reuses the EDGAR company-facts bbterm already
caches, plus the latest price for market cap.

## The formula (and our approximations)

- **EBIT** ≈ reported **operating income** (XBRL `OperatingIncomeLoss`).
- **Market Cap** = shares outstanding × latest price (the ~15-min-delayed quote).
- **Enterprise Value (EV)** = Market Cap + Total Debt − Cash.
- **Earnings Yield** = EBIT ÷ EV.
- **Net Working Capital (NWC)** = Current Assets − Current Liabilities.
- **Net Fixed Assets (NFA)** = net Property, Plant & Equipment.
- **Tangible Capital** = NWC + NFA.
- **Return on Capital (ROC)** = EBIT ÷ Tangible Capital.
- **Combined rank** = (rank by Earnings Yield, high→low) + (rank by ROC,
  high→low); the **lowest combined total ranks #1**.

These are faithful but approximate (Greenblatt's published screen also normalizes
EBIT, excludes financials/utilities, and sets a market-cap floor — out of scope).
The view labels the numbers as an approximation.

## Data availability (confirmed against live EDGAR, AAPL)

All required XBRL concepts are present for normal US operating companies:
`OperatingIncomeLoss`, `AssetsCurrent`, `LiabilitiesCurrent`,
`PropertyPlantAndEquipmentNet`, `CashAndCashEquivalentsAtCarryingValue`,
`LongTermDebt` (+ `LongTermDebtCurrent`/`LongTermDebtNoncurrent`),
`CommonStockSharesOutstanding`.

**Not computable** (shown as `n/a`, excluded from the ranking):
ETFs (SPY, QQQ — no fundamentals), many banks/insurers and foreign (IFRS) filers
that don't report these exact concepts, and any company missing operating income.

## Data layer

### Models (`data/models.py`)

```python
@dataclass(frozen=True)
class MagicMetrics:
    symbol: str
    earnings_yield: float | None   # EBIT / EV  (fraction; None if not computable)
    roc: float | None              # EBIT / tangible capital (fraction; None if n/a)
    ev: float | None               # enterprise value (USD)
```

### Pure logic (`data/magic_formula.py`) — zero I/O, unit-tested

- `extract_magic_inputs(facts_json) -> MagicInputs | None` — pull the latest-FY
  values (reusing the `fundamentals.py` `_latest_fy`/concept-search helpers):
  `ebit` (`OperatingIncomeLoss`), `current_assets` (`AssetsCurrent`),
  `current_liabilities` (`LiabilitiesCurrent`), `ppe_net`
  (`PropertyPlantAndEquipmentNet`), `cash`
  (`CashAndCashEquivalentsAtCarryingValue`), `total_debt` (first of `LongTermDebt`,
  else `LongTermDebtNoncurrent` + `LongTermDebtCurrent`; plus `ShortTermBorrowings`
  if present), and `shares`
  (`CommonStockSharesOutstanding`/`EntityCommonStockSharesOutstanding`). Returns
  `None` if any of `ebit`, `current_assets`, `current_liabilities`, `ppe_net`,
  `shares` is missing (the company can't be scored).
  `MagicInputs` is a frozen dataclass of those floats.
- `compute_magic(symbol, inputs, price) -> MagicMetrics`:
  - `market_cap = inputs.shares * price`
  - `ev = market_cap + inputs.total_debt − inputs.cash`
  - `earnings_yield = inputs.ebit / ev` if `ev > 0` else `None`
  - `tangible = (inputs.current_assets − inputs.current_liabilities) + inputs.ppe_net`
  - `roc = inputs.ebit / tangible` if `tangible > 0` else `None`
- `rank_magic(metrics: list[MagicMetrics]) -> list[tuple[int, MagicMetrics]]` —
  consider only entries where **both** `earnings_yield` and `roc` are not `None`;
  rank each metric descending, sum the two ranks, sort ascending by the sum, and
  return `(combined_rank_position, metrics)` starting at 1. Ties broken by symbol.
  Non-computable entries are not returned here (the view lists them separately).

### Service (`data/service.py`)

- Factor the EDGAR-facts fetch out of `get_fundamentals` into a private helper
  `_edgar_facts(symbol) -> dict | None` (cache-through with the existing 24h TTL),
  and have both `get_fundamentals` and the new method use it (DRY).
- `get_magic(symbol) -> MagicMetrics | None`:
  - `facts = self._edgar_facts(symbol)`; if `None` → return `None`.
  - `inputs = extract_magic_inputs(facts)`; if `None` → return `None`.
  - `quote = await self.get_quote(symbol)`; if no price → return `None`.
  - return `compute_magic(symbol, inputs, quote.price)`.

## UI

### Command (`commands.py`)

Add `ShowMagic`; verb **`MF`** → `ShowMagic`. Unit-tested.

### Widget (`tui/widgets/magic.py`)

- `MagicFormulaView(Widget)` with `.show(current: MagicMetrics | None, ranked, na_symbols)`.
- `render_magic_text(current, ranked, na_symbols, current_symbol) -> str` pure helper:
  - A top block for the loaded stock: `AAPL — Earnings Yield 8.1% · ROC 41.2% · EV $3.10T`
    (or `not computable (ETF / financial / missing data)`).
  - A ranked table: `#  Symbol  EarnYld  ROC  Combined`, best first.
  - A trailing line listing any `n/a` symbols.
  - Yields are shown as percentages; EV humanized (reuse `stats.py`/`fundamentals.py`
    humanizers).

### App (`tui/app.py`)

- Add `MagicFormulaView(id="magic")` to the `ContentSwitcher`.
- `_dispatch` handles `ShowMagic`: switch + `load_magic()`.
- Worker `load_magic` (`@work(exclusive=True, group="magic")`): compute
  `get_magic` for `current_symbol` and for **each watchlist symbol** (cached, so
  repeat views are fast), split into computable vs `n/a`, `rank_magic` the
  computable ones, and `.show(...)`. Degrade-to-notice on error.
- Footer/help text gains `MF magic`.

## Error handling

- Any symbol that can't be scored → counted in `n/a`, never crashes the ranking.
- EDGAR/network failure for a symbol → that symbol degrades to cached facts or
  `n/a`; the rest still rank.
- Negative `ev` or `tangible` capital → that metric is `None` (the stock drops out
  of the ranking but is shown as `n/a`).

## Testing (no network)

- `tests/fixtures/` — a trimmed company-facts JSON with the needed concepts, plus
  one missing `OperatingIncomeLoss` (the "n/a" case).
- `test_magic_formula.py` — `extract_magic_inputs` (happy path + missing-concept →
  None), `compute_magic` (EY/ROC/EV math, negative-EV → None, negative-tangible →
  None), `rank_magic` (combined-rank ordering, excludes None entries).
- `test_commands.py` — `MF` → `ShowMagic`.
- `test_service_magic.py` — fake EDGAR provider + fake quote: `get_magic` returns
  metrics; missing facts → None; `_edgar_facts` shared by `get_fundamentals`.
- `test_app_commands.py` — `MF` switches the `ContentSwitcher` to `magic`.
- `render_magic_text` test (current block, ranked table, n/a line).

## Out of scope

Greenblatt's full screened universe / market-cap floor / sector exclusions, exact
EBIT normalization, historical backtests, anything beyond the watchlist.
