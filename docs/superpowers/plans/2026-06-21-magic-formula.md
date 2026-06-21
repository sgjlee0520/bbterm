# Magic Formula (`MF`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `MF` command that scores the loaded stock and ranks the watchlist by Greenblatt's Magic Formula (Earnings Yield + Return on Capital), using the SEC EDGAR facts bbterm already caches.

**Architecture:** Pure functions in `data/magic_formula.py` (extract inputs from company-facts → compute metrics → rank), reusing `fundamentals.py` helpers. The service gains a shared `_edgar_facts` helper and `get_magic`; a `MagicFormulaView` + `MF` command surface it. No new data source or key.

**Tech Stack:** Python stdlib, Textual, DuckDB, pytest. EDGAR XBRL company-facts.

## Global Constraints

- No new dependencies, data sources, or API keys — reuse cached EDGAR company-facts + the latest quote.
- EBIT ≈ `OperatingIncomeLoss`; EV = market cap + total debt − cash; market cap = shares × latest price.
- Earnings Yield = EBIT/EV (None if EV ≤ 0); ROC = EBIT/(NWC + net PP&E) (None if that ≤ 0).
- Combined rank = rank-by-EY(desc) + rank-by-ROC(desc); lowest total = #1; ties by symbol.
- Non-computable symbols (ETFs, many financials/foreign filers, missing operating income) → shown as `n/a`, excluded from the ranking. Never crash.
- Ranking is across the **watchlist only**.
- Tests make **no network calls**.
- Work on the existing **`magic-formula`** branch.

---

### Task 1: `MagicMetrics` model + pure `magic_formula.py`

**Files:**
- Modify: `src/bbterm/data/models.py`
- Create: `src/bbterm/data/magic_formula.py`
- Test: `tests/test_magic_formula.py`

**Interfaces:**
- Produces: `MagicMetrics(symbol, earnings_yield: float|None, roc: float|None, ev: float|None)`;
  `MagicInputs` (frozen floats); `extract_magic_inputs(facts_json) -> MagicInputs | None`;
  `compute_magic(symbol, inputs, price) -> MagicMetrics`;
  `rank_magic(list[MagicMetrics]) -> list[tuple[int, MagicMetrics]]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_magic_formula.py`:

```python
from bbterm.data.magic_formula import (
    MagicInputs, MagicMetrics, compute_magic, extract_magic_inputs, rank_magic,
)


def _facts(**overrides):
    base = {
        "OperatingIncomeLoss": 133050000000,
        "AssetsCurrent": 147957000000,
        "LiabilitiesCurrent": 165631000000,
        "PropertyPlantAndEquipmentNet": 49834000000,
        "CashAndCashEquivalentsAtCarryingValue": 35934000000,
        "LongTermDebt": 90678000000,
    }
    base.update(overrides)
    usd = {
        c: {"units": {"USD": [{"end": "2024-09-28", "val": v, "fy": 2024, "fp": "FY"}]}}
        for c, v in base.items()
    }
    usd["CommonStockSharesOutstanding"] = {
        "units": {"shares": [{"end": "2024-09-28", "val": 14773260000, "fy": 2024, "fp": "FY"}]}
    }
    return {"facts": {"us-gaap": usd}}


def test_extract_inputs_happy_path():
    inp = extract_magic_inputs(_facts())
    assert inp is not None
    assert inp.ebit == 133050000000 and inp.shares == 14773260000
    assert inp.total_debt == 90678000000 and inp.cash == 35934000000


def test_extract_inputs_missing_operating_income_returns_none():
    f = _facts()
    del f["facts"]["us-gaap"]["OperatingIncomeLoss"]
    assert extract_magic_inputs(f) is None


def test_compute_magic_math():
    m = compute_magic("AAPL", extract_magic_inputs(_facts()), price=230.0)
    assert m.ev > 0
    assert round(m.earnings_yield, 4) == 0.0385
    assert round(m.roc, 2) == 4.14


def test_compute_magic_negative_ev_yields_none():
    inp = MagicInputs(ebit=100, current_assets=10, current_liabilities=5,
                      ppe_net=2, cash=1_000_000_000, total_debt=0, shares=1)
    m = compute_magic("X", inp, price=1.0)  # market cap 1, minus 1e9 cash -> EV < 0
    assert m.earnings_yield is None and m.roc is not None


def test_compute_magic_negative_tangible_yields_none():
    inp = MagicInputs(ebit=100, current_assets=5, current_liabilities=100,
                      ppe_net=10, cash=0, total_debt=0, shares=1)
    m = compute_magic("Y", inp, price=1_000_000.0)  # tangible = -85 -> ROC None
    assert m.roc is None


def test_rank_magic_orders_and_excludes_na():
    a = MagicMetrics("A", 0.10, 0.50, 1e9)   # best on both
    b = MagicMetrics("B", 0.05, 0.40, 1e9)
    c = MagicMetrics("C", None, None, None)  # not computable
    ranked = rank_magic([b, a, c])
    assert [(r, m.symbol) for r, m in ranked] == [(1, "A"), (2, "B")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_magic_formula.py -q`
Expected: FAIL — `ModuleNotFoundError: bbterm.data.magic_formula`.

- [ ] **Step 3: Add the `MagicMetrics` model**

In `src/bbterm/data/models.py`, append after `CongressTrade`:

```python
@dataclass(frozen=True)
class MagicMetrics:
    symbol: str
    earnings_yield: float | None   # EBIT / EV
    roc: float | None              # EBIT / tangible capital
    ev: float | None               # enterprise value (USD)
```

- [ ] **Step 4: Write `magic_formula.py`**

Create `src/bbterm/data/magic_formula.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from bbterm.data.fundamentals import _annual, _find_unit_series
from bbterm.data.models import MagicMetrics


@dataclass(frozen=True)
class MagicInputs:
    ebit: float
    current_assets: float
    current_liabilities: float
    ppe_net: float
    cash: float
    total_debt: float
    shares: float


def _latest(facts_json: dict, concepts: list[str], unit: str) -> float | None:
    for concept in concepts:
        series = _find_unit_series(facts_json, concept, unit)
        if not series:
            continue
        annual = _annual(series)
        if not annual:
            continue
        latest = max(annual, key=lambda d: (d["end"], d.get("fy", 0)))
        return float(latest["val"])
    return None


def extract_magic_inputs(facts_json: dict) -> MagicInputs | None:
    ebit = _latest(facts_json, ["OperatingIncomeLoss"], "USD")
    cur_assets = _latest(facts_json, ["AssetsCurrent"], "USD")
    cur_liab = _latest(facts_json, ["LiabilitiesCurrent"], "USD")
    ppe = _latest(facts_json, ["PropertyPlantAndEquipmentNet"], "USD")
    shares = _latest(
        facts_json,
        ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"],
        "shares",
    )
    if None in (ebit, cur_assets, cur_liab, ppe, shares):
        return None
    cash = _latest(facts_json, ["CashAndCashEquivalentsAtCarryingValue"], "USD") or 0.0
    debt = _latest(facts_json, ["LongTermDebt"], "USD")
    if debt is None:
        noncur = _latest(facts_json, ["LongTermDebtNoncurrent"], "USD") or 0.0
        cur = _latest(facts_json, ["LongTermDebtCurrent"], "USD") or 0.0
        debt = noncur + cur
    short = _latest(facts_json, ["ShortTermBorrowings"], "USD") or 0.0
    return MagicInputs(
        ebit=ebit, current_assets=cur_assets, current_liabilities=cur_liab,
        ppe_net=ppe, cash=cash, total_debt=debt + short, shares=shares,
    )


def compute_magic(symbol: str, inputs: MagicInputs, price: float) -> MagicMetrics:
    market_cap = inputs.shares * price
    ev = market_cap + inputs.total_debt - inputs.cash
    earnings_yield = inputs.ebit / ev if ev > 0 else None
    tangible = (inputs.current_assets - inputs.current_liabilities) + inputs.ppe_net
    roc = inputs.ebit / tangible if tangible > 0 else None
    return MagicMetrics(symbol=symbol, earnings_yield=earnings_yield, roc=roc, ev=ev)


def rank_magic(metrics: list[MagicMetrics]) -> list[tuple[int, MagicMetrics]]:
    computable = [m for m in metrics if m.earnings_yield is not None and m.roc is not None]
    if not computable:
        return []
    ey = {m.symbol: i for i, m in
          enumerate(sorted(computable, key=lambda m: m.earnings_yield, reverse=True))}
    roc = {m.symbol: i for i, m in
           enumerate(sorted(computable, key=lambda m: m.roc, reverse=True))}
    ordered = sorted(computable, key=lambda m: (ey[m.symbol] + roc[m.symbol], m.symbol))
    return [(i + 1, m) for i, m in enumerate(ordered)]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_magic_formula.py -q`
Expected: PASS — all 6.

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/data/models.py src/bbterm/data/magic_formula.py tests/test_magic_formula.py
git commit -m "feat: MagicMetrics model + magic_formula extract/compute/rank

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Service `_edgar_facts` refactor + `get_magic`

**Files:**
- Modify: `src/bbterm/data/service.py`
- Test: `tests/test_service_magic.py`

**Interfaces:**
- Consumes: `extract_magic_inputs`, `compute_magic`, `get_quote`.
- Produces: `async DataService._edgar_facts(symbol) -> dict | None` (shared cache-through);
  `async DataService.get_magic(symbol) -> MagicMetrics | None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_service_magic.py`:

```python
from bbterm.data.models import Quote
from bbterm.data.service import DataService
from bbterm.data.store import Store


def _facts():
    usd = {
        "OperatingIncomeLoss": 133050000000, "AssetsCurrent": 147957000000,
        "LiabilitiesCurrent": 165631000000, "PropertyPlantAndEquipmentNet": 49834000000,
        "CashAndCashEquivalentsAtCarryingValue": 35934000000, "LongTermDebt": 90678000000,
    }
    facts = {c: {"units": {"USD": [{"end": "2024-09-28", "val": v, "fy": 2024, "fp": "FY"}]}}
             for c, v in usd.items()}
    facts["CommonStockSharesOutstanding"] = {
        "units": {"shares": [{"end": "2024-09-28", "val": 14773260000, "fy": 2024, "fp": "FY"}]}}
    return {"cik": 1, "facts": {"us-gaap": facts}}


class FakeEdgar:
    name = "edgar"

    def __init__(self, facts):
        self._facts = facts

    def get_facts(self, symbol):
        return self._facts


class FakeQuotes:
    name = "fake"

    def get_quote(self, symbol):
        return Quote(symbol, 230.0, 220.0)


async def test_get_magic_returns_metrics():
    svc = DataService(Store(":memory:"), None, FakeQuotes(), edgar_provider=FakeEdgar(_facts()))
    m = await svc.get_magic("AAPL")
    assert m is not None and m.symbol == "AAPL"
    assert round(m.earnings_yield, 4) == 0.0385 and m.ev > 0


async def test_get_magic_missing_facts_returns_none():
    svc = DataService(Store(":memory:"), None, FakeQuotes(),
                      edgar_provider=FakeEdgar({"cik": 1, "facts": {"us-gaap": {}}}))
    assert await svc.get_magic("AAPL") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_service_magic.py -q`
Expected: FAIL — `DataService` has no `get_magic`.

- [ ] **Step 3: Refactor the EDGAR-facts fetch and add `get_magic`**

In `src/bbterm/data/service.py`, extend the imports:
```python
from bbterm.data.magic_formula import compute_magic, extract_magic_inputs
from bbterm.data.models import (
    Bar, CongressTrade, Filing, FundamentalMetric, MagicMetrics, NewsItem, Quote,
)
```

Replace the body of `get_fundamentals` with a call to a new shared helper. The
current method is:
```python
    async def get_fundamentals(self, symbol: str) -> list[FundamentalMetric]:
        cached = self.store.get_edgar_facts(symbol)
        if not self._edgar_fresh(cached):
            try:
                facts = await asyncio.to_thread(self._edgar.get_facts, symbol)
                self.store.set_edgar_facts(symbol, json.dumps(facts))
                cached = self.store.get_edgar_facts(symbol)
            except Exception:
                if cached is None:
                    raise
        _, payload = cached
        return extract_fundamentals(json.loads(payload))
```
Replace it with:
```python
    async def _edgar_facts(self, symbol: str) -> dict | None:
        cached = self.store.get_edgar_facts(symbol)
        if not self._edgar_fresh(cached):
            try:
                facts = await asyncio.to_thread(self._edgar.get_facts, symbol)
                self.store.set_edgar_facts(symbol, json.dumps(facts))
                cached = self.store.get_edgar_facts(symbol)
            except Exception:
                pass
        if cached is None:
            return None
        _, payload = cached
        return json.loads(payload)

    async def get_fundamentals(self, symbol: str) -> list[FundamentalMetric]:
        facts = await self._edgar_facts(symbol)
        if facts is None:
            return []
        return extract_fundamentals(facts)

    async def get_magic(self, symbol: str) -> MagicMetrics | None:
        facts = await self._edgar_facts(symbol)
        if facts is None:
            return None
        inputs = extract_magic_inputs(facts)
        if inputs is None:
            return None
        quote = await self.get_quote(symbol)
        if quote is None or quote.price is None:
            return None
        return compute_magic(symbol, inputs, quote.price)
```

- [ ] **Step 4: Run the magic + existing EDGAR service tests**

Run: `.venv/bin/python -m pytest tests/test_service_magic.py tests/test_service_edgar.py -q`
Expected: PASS — 2 magic tests + the 3 existing EDGAR tests (the refactor preserves
cache-through and degrade-to-cache).

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/service.py tests/test_service_magic.py
git commit -m "feat: DataService.get_magic; share _edgar_facts with get_fundamentals

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `MF` command

**Files:**
- Modify: `src/bbterm/commands.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Produces: `ShowMagic` (frozen, no fields); `parse_command("MF") -> ShowMagic()`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands.py`:

```python
def test_mf_parses_to_show_magic():
    from bbterm.commands import ShowMagic
    assert isinstance(parse_command("MF"), ShowMagic)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commands.py::test_mf_parses_to_show_magic -q`
Expected: FAIL — `ImportError: cannot import name 'ShowMagic'`.

- [ ] **Step 3: Add the command**

In `src/bbterm/commands.py`, add the dataclass after `ShowPoliticians`:
```python
@dataclass(frozen=True)
class ShowMagic:
    pass
```
and the verb branch after the `POL` branch:
```python
    if verb == "MF":
        return ShowMagic()
```

- [ ] **Step 4: Run the command tests**

Run: `.venv/bin/python -m pytest tests/test_commands.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/commands.py tests/test_commands.py
git commit -m "feat: MF command parses to ShowMagic

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `MagicFormulaView` widget + render helper

**Files:**
- Create: `src/bbterm/tui/widgets/magic.py`
- Test: `tests/test_magic_view.py`

**Interfaces:**
- Consumes: `MagicMetrics`, `human_money` (from `tui/widgets/fundamentals.py`).
- Produces: `render_magic_text(current_symbol, current, ranked, na_symbols) -> str`;
  `MagicFormulaView(Widget)` with `.show(current_symbol, current, ranked, na_symbols)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_magic_view.py`:

```python
from bbterm.data.magic_formula import rank_magic
from bbterm.data.models import MagicMetrics
from bbterm.tui.widgets.magic import render_magic_text


def test_render_shows_current_and_ranking():
    a = MagicMetrics("AAPL", 0.08, 0.40, 3.1e12)
    b = MagicMetrics("MSFT", 0.05, 0.30, 2.5e12)
    out = render_magic_text("AAPL", a, rank_magic([a, b]), ["SPY"])
    assert "AAPL" in out and "8.0%" in out and "40.0%" in out
    assert "MSFT" in out
    assert "Not computable: SPY" in out


def test_render_not_computable_current():
    out = render_magic_text("SPY", None, [], ["SPY"])
    assert "not computable" in out.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_magic_view.py -q`
Expected: FAIL — `ModuleNotFoundError: bbterm.tui.widgets.magic`.

- [ ] **Step 3: Write the widget**

Create `src/bbterm/tui/widgets/magic.py`:

```python
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from bbterm.data.models import MagicMetrics
from bbterm.tui.widgets.fundamentals import human_money


def _pct(x: float | None) -> str:
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def render_magic_text(
    current_symbol: str,
    current: MagicMetrics | None,
    ranked: list[tuple[int, MagicMetrics]],
    na_symbols: list[str],
) -> str:
    lines = [f"  Magic Formula — {current_symbol}", ""]
    if current is None or current.earnings_yield is None or current.roc is None:
        lines.append(f"  {current_symbol}: not computable (ETF / financial / missing data)")
    else:
        lines.append(
            f"  {current_symbol} — Earnings Yield {_pct(current.earnings_yield)} · "
            f"ROC {_pct(current.roc)} · EV {human_money(current.ev)}"
        )
    lines += ["", "  Watchlist ranking (best = cheap + high quality)",
              f"    {'#':<4}{'Symbol':<8}{'EarnYld':<10}{'ROC':<10}"]
    for rank, m in ranked:
        lines.append(f"    {rank:<4}{m.symbol:<8}{_pct(m.earnings_yield):<10}{_pct(m.roc):<10}")
    if na_symbols:
        lines += ["", "  Not computable: " + ", ".join(na_symbols)]
    lines += ["", "  Approximate (EBIT ≈ operating income, delayed price); not advice."]
    return "\n".join(lines)


class MagicFormulaView(Widget):
    DEFAULT_CSS = """
    MagicFormulaView { height: 1fr; }
    MagicFormulaView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    MagicFormulaView > Static.body { width: 100%; height: 1fr; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        yield Label("MAGIC FORMULA", classes="header")
        yield Static("  Select a symbol.", classes="body")

    def show(
        self,
        current_symbol: str,
        current: MagicMetrics | None,
        ranked: list[tuple[int, MagicMetrics]],
        na_symbols: list[str],
    ) -> None:
        self.query_one(".body", Static).update(
            Text(render_magic_text(current_symbol, current, ranked, na_symbols))
        )
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_magic_view.py -q`
Expected: PASS — both.

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/tui/widgets/magic.py tests/test_magic_view.py
git commit -m "feat: MagicFormulaView widget and render helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Wire `MF` into the app

**Files:**
- Modify: `src/bbterm/tui/app.py`
- Test: `tests/test_app_commands.py`

**Interfaces:**
- Consumes: `ShowMagic`, `MagicFormulaView`, `rank_magic`, `DataService.get_magic`.
- Produces: `MF` switches the `ContentSwitcher` to `magic` and shows the per-stock numbers + watchlist ranking.

- [ ] **Step 1: Write the failing test**

In `tests/test_app_commands.py`, add the test at the end (the existing `_app()` and
`FakeEdgar` already provide everything; `FakeProvider` serves as the quote provider):

```python
async def test_mf_switches_to_magic_view():
    app, _ = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "MF")
        assert app.query_one(ContentSwitcher).current == "magic"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_app_commands.py::test_mf_switches_to_magic_view -q`
Expected: FAIL — `ShowMagic` not handled / `magic` not a valid switcher id.

- [ ] **Step 3: Wire the app**

In `src/bbterm/tui/app.py`:

Add `ShowMagic` to the commands import:
```python
from bbterm.commands import (
    AddSymbol, Help, LoadSymbol, RemoveSymbol, ShowChart, ShowFilings,
    ShowFundamentals, ShowMagic, ShowNews, ShowPoliticians, ShowStats, Unknown,
    parse_command,
)
```

Add imports for the view and ranker:
```python
from bbterm.data.magic_formula import rank_magic
from bbterm.tui.widgets.magic import MagicFormulaView
```

In `compose`, add after `PoliticiansView(id="politicians")`:
```python
                yield MagicFormulaView(id="magic")
```

In `_dispatch`, add after the `ShowPoliticians` branch:
```python
        elif isinstance(command, ShowMagic):
            self.query_one("#switcher", ContentSwitcher).current = "magic"
            self.load_magic()
```

In `_refresh_active_view`, add before the `else`:
```python
        elif current == "magic":
            self.load_magic()
```

Add the worker near `load_politicians`:
```python
    @work(exclusive=True, group="magic")
    async def load_magic(self) -> None:
        try:
            current = await self.service.get_magic(self.current_symbol)
            results = {s: await self.service.get_magic(s) for s in self.watchlist_symbols}
        except Exception as err:
            self.notify(f"Magic Formula unavailable ({err})", severity="warning")
            current, results = None, {}
        computable = [m for m in results.values() if m is not None]
        na = [s for s, m in results.items() if m is None]
        ranked = rank_magic(computable)
        self.query_one(MagicFormulaView).show(self.current_symbol, current, ranked, na)
```

Update the `_HELP` string — change `POL congress` to `POL congress · MF magic`.

- [ ] **Step 4: Run the app-command tests**

Run: `.venv/bin/python -m pytest tests/test_app_commands.py -q`
Expected: PASS — new test plus all existing app-command tests.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — no failures (the new magic tests across Tasks 1–5 plus everything else).

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/tui/app.py tests/test_app_commands.py
git commit -m "feat: wire MF magic-formula command into the app

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Manual verification (after the suite is green)

- In `bbterm` (iTerm2): load `AAPL`, press `MF` → see AAPL's Earnings Yield / ROC / EV
  and a ranked table of your watchlist; ETFs like `SPY`/`QQQ` appear under "Not
  computable". Cross-check a value against the FA view if you like.

## Notes for the implementer

- Branch is already `magic-formula`.
- `magic_formula.py` reuses `_find_unit_series`/`_annual` from `fundamentals.py`
  (pure helpers in the same package) — do not duplicate them.
- The `_edgar_facts` refactor must keep the existing EDGAR service tests green
  (cache-through + degrade-to-cache).
- `load_magic` computes for the current symbol and every watchlist symbol; all are
  cached (24h), so repeat views are fast.
