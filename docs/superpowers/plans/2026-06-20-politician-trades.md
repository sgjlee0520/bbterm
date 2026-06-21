# Politician Trades (`POL`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `POL` command showing, for the current stock, a curated list of politicians' congressional buy/sell trades plus a per-politician net-activity summary, sourced from Lambda Finance.

**Architecture:** Mirrors the EDGAR/news feature — `CongressProvider` (Lambda, stdlib urllib, Bearer + browser User-Agent, test-injectable) → raw JSON cached in DuckDB (24h TTL) → pure `congress.py` (parse/filter-to-roster/summarize) → `PoliticiansView` → `POL` command. Optional `LAMBDA_API_KEY`; no key → a notice.

**Tech Stack:** Python stdlib (`urllib`, `re`, `datetime`), Textual, DuckDB, pytest.

## Global Constraints

- Source: `https://www.lambdafin.com/api/congressional/recent?ticker={SYMBOL}&days=730`, header `Authorization: Bearer {LAMBDA_API_KEY}` **and a browser `User-Agent`** (Cloudflare blocks Python's default UA).
- Key from env **`LAMBDA_API_KEY`** (optional, like `DATABENTO_API_KEY`); no key → empty view + notice, never crash.
- Confirmed response: `{"trades": [ {representative, transactionDate, type, amount, chamber, symbol, ...} ], "count", "days"}`. `amount` is a range string (`"$15,001 - $50,000"`).
- Curated roster only; match on last name + first-name prefix (so `Gil Cisneros` matches `Gilbert Cisneros`).
- Trades not holdings; no share counts; Trump family absent; Vance historical-only.
- Tests make **no network calls** and need **no key**.
- Cache TTL 24h (`CONGRESS_TTL_SECONDS = 86400.0`) — also protects the 100/month Lambda quota.
- Work on the existing **`politician-trades`** branch.
- The Lambda live-test gate already **passed** (brainstorming) — no separate gate task.

---

### Task 1: `CongressTrade` model + pure `congress.py`

**Files:**
- Modify: `src/bbterm/data/models.py`
- Create: `src/bbterm/data/congress.py`
- Test: `tests/test_congress.py`

**Interfaces:**
- Produces: `CongressTrade(politician, chamber, side, amount_low, amount_high, date)`;
  `CONGRESS_ROSTER: list[str]`; `parse_congress_trades(payload: dict) -> list[CongressTrade]`;
  `filter_to_roster(trades, roster=CONGRESS_ROSTER) -> list[CongressTrade]`;
  `summarize(trades) -> list[PoliticianSummary]` with
  `PoliticianSummary(politician, n_buys, n_sells, net_estimate)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_congress.py`:

```python
from bbterm.data.congress import (
    CONGRESS_ROSTER, PoliticianSummary, filter_to_roster, parse_congress_trades,
    summarize,
)

PAYLOAD = {
    "trades": [
        {"symbol": "NVDA", "representative": "Gilbert Cisneros",
         "transactionDate": "2025-11-18", "type": "Purchase",
         "amount": "$15,001 - $50,000", "chamber": "house"},
        {"symbol": "NVDA", "representative": "Gilbert Cisneros",
         "transactionDate": "2025-10-17", "type": "Purchase",
         "amount": "$1,001 - $15,000", "chamber": "house"},
        {"symbol": "NVDA", "representative": "Nancy Pelosi",
         "transactionDate": "2025-09-01", "type": "Sale (Full)",
         "amount": "$250,001 - $500,000", "chamber": "house"},
        {"symbol": "NVDA", "representative": "Dwight Evans",  # not on roster
         "transactionDate": "2025-11-21", "type": "Purchase",
         "amount": "$1,001 - $15,000", "chamber": "house"},
        {"symbol": "NVDA", "representative": "Some One",
         "transactionDate": "2025-08-01", "type": "Exchange",  # skipped type
         "amount": "$1,001 - $15,000", "chamber": "house"},
    ],
    "count": 5, "days": 730,
}


def test_parse_maps_type_amount_and_skips_non_buy_sell():
    trades = parse_congress_trades(PAYLOAD)
    # 4 Purchase/Sale rows; the Exchange row is skipped
    assert len(trades) == 4
    cisneros = [t for t in trades if t.politician == "Gilbert Cisneros"][0]
    assert cisneros.side == "BUY"
    assert (cisneros.amount_low, cisneros.amount_high) == (15001.0, 50000.0)
    pelosi = [t for t in trades if t.politician == "Nancy Pelosi"][0]
    assert pelosi.side == "SELL"


def test_filter_keeps_roster_with_first_name_variant_drops_others():
    trades = filter_to_roster(parse_congress_trades(PAYLOAD))
    names = {t.politician for t in trades}
    assert "Gilbert Cisneros" in names   # roster has "Gil Cisneros"
    assert "Nancy Pelosi" in names
    assert "Dwight Evans" not in names   # not on roster
    # newest first
    assert trades[0].date >= trades[-1].date


def test_summarize_counts_and_net_estimate():
    trades = filter_to_roster(parse_congress_trades(PAYLOAD))
    s = {x.politician: x for x in summarize(trades)}
    cis = s["Gilbert Cisneros"]
    assert cis.n_buys == 2 and cis.n_sells == 0
    # net = mid(15001,50000) + mid(1001,15000) = 32500.5 + 8000.5 = 40501.0
    assert cis.net_estimate == 40501.0
    pel = s["Nancy Pelosi"]
    assert pel.n_sells == 1 and pel.net_estimate == -375000.5


def test_roster_is_nonempty():
    assert "Nancy Pelosi" in CONGRESS_ROSTER and len(CONGRESS_ROSTER) >= 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_congress.py -q`
Expected: FAIL — `ModuleNotFoundError: bbterm.data.congress`.

- [ ] **Step 3: Add the `CongressTrade` model**

In `src/bbterm/data/models.py`, append after `NewsItem`:

```python
@dataclass(frozen=True)
class CongressTrade:
    politician: str
    chamber: str          # "house" | "senate"
    side: str             # "BUY" | "SELL"
    amount_low: float
    amount_high: float
    date: date
```

- [ ] **Step 4: Write `congress.py`**

Create `src/bbterm/data/congress.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from bbterm.data.models import CongressTrade

CONGRESS_ROSTER: list[str] = [
    "Nancy Pelosi", "Jim Justice", "Jefferson Shreve", "Rick Scott",
    "Mark Warner", "Pete Ricketts", "Darrell Issa", "Michael McCaul",
    "Ro Khanna", "Gil Cisneros", "JD Vance",
]


@dataclass(frozen=True)
class PoliticianSummary:
    politician: str
    n_buys: int
    n_sells: int
    net_estimate: float


def _parse_amount(s: str | None) -> tuple[float, float]:
    nums = [n.replace(",", "") for n in re.findall(r"[\d,]+", s or "")]
    vals = [float(n) for n in nums if n.isdigit()]
    if not vals:
        return (0.0, 0.0)
    if len(vals) == 1:
        return (vals[0], vals[0])
    return (vals[0], vals[1])


def parse_congress_trades(payload: dict) -> list[CongressTrade]:
    out: list[CongressTrade] = []
    for t in payload.get("trades", []):
        typ = (t.get("type") or "").strip()
        if typ == "Purchase":
            side = "BUY"
        elif typ.startswith("Sale"):
            side = "SELL"
        else:
            continue  # Exchange / other — not a buy or sell
        try:
            d = datetime.strptime(t.get("transactionDate", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        lo, hi = _parse_amount(t.get("amount"))
        out.append(CongressTrade(
            politician=(t.get("representative") or "").strip(),
            chamber=(t.get("chamber") or "").strip(),
            side=side, amount_low=lo, amount_high=hi, date=d,
        ))
    return out


def _tokens(name: str) -> list[str]:
    return name.lower().replace(",", " ").split()


def _matches(roster_name: str, trade_name: str) -> bool:
    r, t = _tokens(roster_name), _tokens(trade_name)
    if not r or not t or r[-1] != t[-1]:  # last names must match exactly
        return False
    rf, tf = r[0], t[0]                    # first-name prefix (either direction)
    return rf.startswith(tf) or tf.startswith(rf)


def filter_to_roster(
    trades: list[CongressTrade], roster: list[str] = CONGRESS_ROSTER
) -> list[CongressTrade]:
    kept = [t for t in trades if any(_matches(r, t.politician) for r in roster)]
    kept.sort(key=lambda t: t.date, reverse=True)
    return kept


def summarize(trades: list[CongressTrade]) -> list[PoliticianSummary]:
    by: dict[str, list[CongressTrade]] = {}
    for t in trades:
        by.setdefault(t.politician, []).append(t)
    out: list[PoliticianSummary] = []
    for name, ts in by.items():
        n_buys = sum(1 for t in ts if t.side == "BUY")
        n_sells = sum(1 for t in ts if t.side == "SELL")
        net = sum(
            (t.amount_low + t.amount_high) / 2 * (1 if t.side == "BUY" else -1)
            for t in ts
        )
        out.append(PoliticianSummary(name, n_buys, n_sells, net))
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_congress.py -q`
Expected: PASS — all 4.

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/data/models.py src/bbterm/data/congress.py tests/test_congress.py
git commit -m "feat: CongressTrade model + congress parse/filter/summarize

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `CongressProvider` (Lambda) + smoke script

**Files:**
- Create: `src/bbterm/data/providers/lambdafin_.py`
- Create: `scripts/smoke_congress.py`
- Test: `tests/test_congress_provider.py`

**Interfaces:**
- Produces: `CongressProvider(api_key, *, opener=None)` with `name = "lambdafin"` and
  `get_congress_trades(symbol: str, days: int = 730) -> dict`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_congress_provider.py`:

```python
from bbterm.data.providers.lambdafin_ import CongressProvider


def test_get_congress_trades_builds_url_and_auth():
    captured = {}

    def fake_open(url, headers):
        captured["url"] = url
        captured["headers"] = headers
        return b'{"trades": [], "count": 0, "days": 730}'

    out = CongressProvider(api_key="secret", opener=fake_open).get_congress_trades("AAPL")
    assert "ticker=AAPL" in captured["url"] and "days=730" in captured["url"]
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert "Mozilla" in captured["headers"]["User-Agent"]  # Cloudflare needs a browser UA
    assert out == {"trades": [], "count": 0, "days": 730}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_congress_provider.py -q`
Expected: FAIL — `ModuleNotFoundError: bbterm.data.providers.lambdafin_`.

- [ ] **Step 3: Write the provider**

Create `src/bbterm/data/providers/lambdafin_.py`:

```python
from __future__ import annotations

import json
import urllib.parse
import urllib.request

_BASE = "https://www.lambdafin.com/api/congressional/recent"
# Cloudflare blocks Python's default urllib UA (error 1010); send a browser UA.
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _http_get(url: str, headers: dict) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


class CongressProvider:
    name = "lambdafin"

    def __init__(self, api_key: str, *, opener=None) -> None:
        self._key = api_key
        self._open = opener or _http_get

    def get_congress_trades(self, symbol: str, days: int = 730) -> dict:
        url = f"{_BASE}?ticker={urllib.parse.quote(symbol)}&days={days}"
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Accept": "application/json",
            "User-Agent": _UA,
        }
        return json.loads(self._open(url, headers))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_congress_provider.py -q`
Expected: PASS.

- [ ] **Step 5: Add the manual smoke script**

Create `scripts/smoke_congress.py`:

```python
"""Manual congress-trades smoke check — hits live Lambda Finance once. Run by hand:
    .venv/bin/python scripts/smoke_congress.py NVDA
Reads LAMBDA_API_KEY from .env. Not part of the pytest suite (no network in tests)."""
import sys
from pathlib import Path

from bbterm.config import _load_dotenv
from bbterm.data.congress import filter_to_roster, parse_congress_trades, summarize
from bbterm.data.providers.lambdafin_ import CongressProvider


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    key = _load_dotenv(Path(".env")).get("LAMBDA_API_KEY")
    if not key:
        print("No LAMBDA_API_KEY in .env"); return
    raw = CongressProvider(api_key=key).get_congress_trades(symbol)
    trades = filter_to_roster(parse_congress_trades(raw))
    print(f"{symbol}: {len(trades)} roster trades")
    for s in summarize(trades):
        print(f"  {s.politician}: {s.n_buys} buys, {s.n_sells} sells, net~{s.net_estimate:,.0f}")
    for t in trades:
        print(f"    {t.side:<5} ${t.amount_low:,.0f}-${t.amount_high:,.0f}  {t.date}  {t.politician}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/data/providers/lambdafin_.py scripts/smoke_congress.py tests/test_congress_provider.py
git commit -m "feat: CongressProvider (Lambda Finance) and smoke script

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Store `congress_trades` cache table

**Files:**
- Modify: `src/bbterm/data/store.py`
- Test: `tests/test_store_congress.py`

**Interfaces:**
- Produces: `Store.get_congress(symbol) -> tuple[datetime, str] | None`, `Store.set_congress(symbol, text)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_store_congress.py`:

```python
from bbterm.data.store import Store


def test_congress_roundtrip():
    store = Store(":memory:")
    assert store.get_congress("AAPL") is None
    store.set_congress("AAPL", '{"trades": []}')
    cached = store.get_congress("AAPL")
    assert cached is not None and cached[1] == '{"trades": []}'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_store_congress.py -q`
Expected: FAIL — `AttributeError: 'Store' object has no attribute 'get_congress'`.

- [ ] **Step 3: Add the table**

In `src/bbterm/data/store.py`, inside `_init_schema`, after the `news` `CREATE TABLE`
block, add:

```python
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS congress_trades (
                symbol VARCHAR PRIMARY KEY, fetched_at TIMESTAMP, json VARCHAR
            )
            """
        )
```

- [ ] **Step 4: Add the accessors**

After the `set_news` method, add:

```python
    def get_congress(self, symbol: str) -> tuple[datetime, str] | None:
        return self._get_edgar("congress_trades", symbol)

    def set_congress(self, symbol: str, text: str) -> None:
        self._set_edgar("congress_trades", symbol, text)
```

- [ ] **Step 5: Run the test**

Run: `.venv/bin/python -m pytest tests/test_store_congress.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/data/store.py tests/test_store_congress.py
git commit -m "feat: congress_trades cache table in the store

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Config key + `DataService.get_congress_trades` + wire provider

**Files:**
- Modify: `src/bbterm/config.py`
- Modify: `src/bbterm/data/service.py`
- Modify: `src/bbterm/data/__init__.py`
- Test: `tests/test_service_congress.py`

**Interfaces:**
- Consumes: `Store.get_congress`/`set_congress`, `parse_congress_trades`, `filter_to_roster`, `CongressProvider.get_congress_trades`.
- Produces: `Config.lambda_api_key: str | None`; `DataService(..., congress_provider=None)` with
  `async get_congress_trades(symbol) -> list[CongressTrade]` and property `has_congress -> bool`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_service_congress.py`:

```python
from datetime import datetime, timedelta

from bbterm.data.service import DataService
from bbterm.data.store import Store

PAYLOAD = {
    "trades": [
        {"symbol": "NVDA", "representative": "Gilbert Cisneros",
         "transactionDate": "2025-11-18", "type": "Purchase",
         "amount": "$15,001 - $50,000", "chamber": "house"},
        {"symbol": "NVDA", "representative": "Dwight Evans",
         "transactionDate": "2025-11-21", "type": "Purchase",
         "amount": "$1,001 - $15,000", "chamber": "house"},
    ],
    "count": 2, "days": 730,
}


class FakeCongress:
    name = "lambdafin"

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def get_congress_trades(self, symbol, days=730):
        self.calls += 1
        if self.fail:
            raise RuntimeError("boom")
        return PAYLOAD


async def test_get_congress_trades_parses_filters_caches():
    cg = FakeCongress()
    svc = DataService(Store(":memory:"), None, None, congress_provider=cg)
    trades = await svc.get_congress_trades("NVDA")
    assert [t.politician for t in trades] == ["Gilbert Cisneros"]  # Evans filtered out
    await svc.get_congress_trades("NVDA")  # fresh cache -> no refetch
    assert cg.calls == 1
    assert svc.has_congress is True


async def test_get_congress_trades_no_provider_returns_empty():
    svc = DataService(Store(":memory:"), None, None, congress_provider=None)
    assert await svc.get_congress_trades("NVDA") == []
    assert svc.has_congress is False


async def test_get_congress_trades_degrades_to_stale_cache():
    store = Store(":memory:")
    import json
    store._con.execute(
        "INSERT OR REPLACE INTO congress_trades VALUES (?, ?, ?)",
        ["NVDA", datetime.now() - timedelta(days=2), json.dumps(PAYLOAD)],
    )
    cg = FakeCongress(fail=True)
    svc = DataService(store, None, None, congress_provider=cg)
    trades = await svc.get_congress_trades("NVDA")
    assert cg.calls == 1 and [t.politician for t in trades] == ["Gilbert Cisneros"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_service_congress.py -q`
Expected: FAIL — no `congress_provider` kwarg / no `get_congress_trades`.

- [ ] **Step 3: Add the config field**

In `src/bbterm/config.py`, add `lambda_api_key` to the `Config` dataclass **as the
last field, with a default** (so existing `Config(...)` constructions that don't
pass it — e.g. `test_factory` — keep working):
```python
    lambda_api_key: str | None = None
```
and in `load_config`'s `Config(...)` add:
```python
        lambda_api_key=env.get("LAMBDA_API_KEY"),
```

- [ ] **Step 4: Extend the service**

In `src/bbterm/data/service.py`:

Extend imports:
```python
from bbterm.data.congress import filter_to_roster, parse_congress_trades
from bbterm.data.models import Bar, CongressTrade, Filing, FundamentalMetric, NewsItem, Quote
```

Add the TTL constant (after `NEWS_TTL_SECONDS`):
```python
CONGRESS_TTL_SECONDS = 86400.0
```

Add the constructor param (after `news_provider=None,`):
```python
        congress_provider=None,
```
and in the body (after `self._news = news_provider`):
```python
        self._congress = congress_provider
```

Append to the class (after `get_news`):
```python
    # ---- congressional trades ---------------------------------------------
    @property
    def has_congress(self) -> bool:
        return self._congress is not None

    def _congress_fresh(self, cached) -> bool:
        if cached is None:
            return False
        fetched_at, _ = cached
        return (datetime.now() - fetched_at).total_seconds() < CONGRESS_TTL_SECONDS

    async def get_congress_trades(self, symbol: str) -> list[CongressTrade]:
        if self._congress is None:
            return []
        cached = self.store.get_congress(symbol)
        if not self._congress_fresh(cached):
            try:
                raw = await asyncio.to_thread(self._congress.get_congress_trades, symbol)
                self.store.set_congress(symbol, json.dumps(raw))
                cached = self.store.get_congress(symbol)
            except Exception:
                pass
        if cached is None:
            return []
        _, payload = cached
        return filter_to_roster(parse_congress_trades(json.loads(payload)))
```

- [ ] **Step 5: Wire the provider into `build_service`**

In `src/bbterm/data/__init__.py`: add the import
```python
from bbterm.data.providers.lambdafin_ import CongressProvider
```
construct it (after `news = NewsProvider()`):
```python
    congress = (
        CongressProvider(api_key=config.lambda_api_key)
        if config.lambda_api_key else None
    )
```
and add `congress_provider=congress` to **both** `DataService(...)` returns, e.g.:
```python
        return DataService(store, bars, yf_provider, edgar_provider=edgar, news_provider=news, congress_provider=congress)
    return DataService(store, yf_provider, yf_provider, edgar_provider=edgar, news_provider=news, congress_provider=congress)
```

- [ ] **Step 6: Run the service + factory tests**

Run: `.venv/bin/python -m pytest tests/test_service_congress.py tests/test_factory.py -q`
Expected: PASS — 3 congress service tests + the factory tests.

- [ ] **Step 7: Commit**

```bash
git add src/bbterm/config.py src/bbterm/data/service.py src/bbterm/data/__init__.py tests/test_service_congress.py
git commit -m "feat: DataService.get_congress_trades (24h cache) + LAMBDA_API_KEY

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `ShowPoliticians` command + `POL` verb

**Files:**
- Modify: `src/bbterm/commands.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Produces: `ShowPoliticians` (frozen, no fields); `parse_command("POL") -> ShowPoliticians()`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands.py`:

```python
def test_pol_parses_to_show_politicians():
    from bbterm.commands import ShowPoliticians
    assert isinstance(parse_command("POL"), ShowPoliticians)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commands.py::test_pol_parses_to_show_politicians -q`
Expected: FAIL — `ImportError: cannot import name 'ShowPoliticians'`.

- [ ] **Step 3: Add the command**

In `src/bbterm/commands.py`, add the dataclass after `ShowNews`:
```python
@dataclass(frozen=True)
class ShowPoliticians:
    pass
```
and the verb branch after the `N` branch:
```python
    if verb == "POL":
        return ShowPoliticians()
```

- [ ] **Step 4: Run the command tests**

Run: `.venv/bin/python -m pytest tests/test_commands.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/commands.py tests/test_commands.py
git commit -m "feat: POL command parses to ShowPoliticians

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: `PoliticiansView` widget + render helper

**Files:**
- Create: `src/bbterm/tui/widgets/politicians.py`
- Test: `tests/test_politicians_view.py`

**Interfaces:**
- Consumes: `CongressTrade`, `summarize`.
- Produces: `render_politicians_text(trades, has_key=True) -> str`; `PoliticiansView(Widget)` with `.show(trades, has_key=True)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_politicians_view.py`:

```python
from datetime import date

from bbterm.data.models import CongressTrade
from bbterm.tui.widgets.politicians import render_politicians_text


def _t(side, lo, hi, d):
    return CongressTrade("Gilbert Cisneros", "house", side, lo, hi, date.fromisoformat(d))


def test_render_shows_summary_and_rows():
    trades = [_t("BUY", 15001, 50000, "2025-11-18"), _t("BUY", 1001, 15000, "2025-10-17")]
    out = render_politicians_text(trades)
    assert "Gilbert Cisneros" in out
    assert "2 buys" in out and "0 sells" in out
    assert "BUY" in out and "2025-11-18" in out


def test_render_no_key_notice():
    assert "LAMBDA_API_KEY" in render_politicians_text([], has_key=False)


def test_render_empty_with_key():
    out = render_politicians_text([], has_key=True)
    assert "No congressional trades" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_politicians_view.py -q`
Expected: FAIL — `ModuleNotFoundError: bbterm.tui.widgets.politicians`.

- [ ] **Step 3: Write the widget**

Create `src/bbterm/tui/widgets/politicians.py`:

```python
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from bbterm.data.models import CongressTrade
from bbterm.data.congress import summarize


def _net_str(net: float) -> str:
    sign = "+" if net >= 0 else "-"
    v = abs(net)
    if v >= 1e6:
        return f"{sign}${v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{sign}${v / 1e3:.0f}K"
    return f"{sign}${v:.0f}"


def render_politicians_text(trades: list[CongressTrade], has_key: bool = True) -> str:
    if not has_key:
        return "  Set LAMBDA_API_KEY (a free Lambda Finance key) to enable politician trades."
    if not trades:
        return "  No congressional trades for this symbol."
    summaries = {s.politician: s for s in summarize(trades)}
    grouped: dict[str, list[CongressTrade]] = {}
    for t in trades:
        grouped.setdefault(t.politician, []).append(t)
    lines = ["  Congressional trades (amounts are disclosed ranges; net is approximate)", ""]
    for name, ts in grouped.items():
        s = summaries[name]
        lines.append(
            f"  {name} ({ts[0].chamber}) — {s.n_buys} buys · {s.n_sells} sells · "
            f"net ≈ {_net_str(s.net_estimate)} (est.)"
        )
        for t in ts:
            lines.append(
                f"      {t.side:<5}${t.amount_low:,.0f} - ${t.amount_high:,.0f}   "
                f"{t.date.isoformat()}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


class PoliticiansView(Widget):
    DEFAULT_CSS = """
    PoliticiansView { height: 1fr; }
    PoliticiansView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    PoliticiansView > Static.body { width: 100%; height: 1fr; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        yield Label("CONGRESS", classes="header")
        yield Static("  Select a symbol.", classes="body")

    def show(self, trades: list[CongressTrade], has_key: bool = True) -> None:
        self.query_one(".body", Static).update(
            Text(render_politicians_text(trades, has_key))
        )
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_politicians_view.py -q`
Expected: PASS — all 3.

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/tui/widgets/politicians.py tests/test_politicians_view.py
git commit -m "feat: PoliticiansView widget and render helper

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Wire `POL` into the app

**Files:**
- Modify: `src/bbterm/tui/app.py`
- Test: `tests/test_app_commands.py`

**Interfaces:**
- Consumes: `ShowPoliticians`, `PoliticiansView`, `DataService.get_congress_trades`, `DataService.has_congress`.
- Produces: `POL` switches the `ContentSwitcher` to `politicians` and loads trades.

- [ ] **Step 1: Write the failing test**

In `tests/test_app_commands.py`, after the `FakeNews` class add:

```python
class FakeCongress:
    name = "lambdafin"

    def get_congress_trades(self, symbol, days=730):
        return {"trades": [], "count": 0, "days": 730}
```

In `_app()`, pass it to the service:
```python
    service = DataService(Store(":memory:"), fake, fake, fetch_ttl=0.0,
                          edgar_provider=FakeEdgar(), news_provider=FakeNews(),
                          congress_provider=FakeCongress())
```

Add the test at the end of the file:
```python
async def test_pol_switches_to_politicians_view():
    app, _ = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "POL")
        assert app.query_one(ContentSwitcher).current == "politicians"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_app_commands.py::test_pol_switches_to_politicians_view -q`
Expected: FAIL — `ShowPoliticians` not handled / `politicians` not a valid switcher id.

- [ ] **Step 3: Wire the app**

In `src/bbterm/tui/app.py`:

Add `ShowPoliticians` to the commands import:
```python
from bbterm.commands import (
    AddSymbol, Help, LoadSymbol, RemoveSymbol, ShowChart, ShowFilings,
    ShowFundamentals, ShowNews, ShowPoliticians, ShowStats, Unknown, parse_command,
)
```

Add the widget import after the news import:
```python
from bbterm.tui.widgets.politicians import PoliticiansView
```

In `compose`, add after `NewsView(id="news")`:
```python
                yield PoliticiansView(id="politicians")
```

In `_dispatch`, add after the `ShowNews` branch:
```python
        elif isinstance(command, ShowPoliticians):
            self.query_one("#switcher", ContentSwitcher).current = "politicians"
            self.load_politicians()
```

In `_refresh_active_view`, add before the `else`:
```python
        elif current == "politicians":
            self.load_politicians()
```

Add the worker near `load_news`:
```python
    @work(exclusive=True, group="politicians")
    async def load_politicians(self) -> None:
        try:
            trades = await self.service.get_congress_trades(self.current_symbol)
        except Exception as err:
            self.notify(f"Congress data unavailable ({err})", severity="warning")
            trades = []
        self.query_one(PoliticiansView).show(trades, has_key=self.service.has_congress)
```

Update the `_HELP` string — change `N news` to `N news · POL congress`.

- [ ] **Step 4: Run the app-command tests**

Run: `.venv/bin/python -m pytest tests/test_app_commands.py -q`
Expected: PASS — new test plus all existing app-command tests.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — no failures (the new congress tests across Tasks 1–7 plus everything else).

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/tui/app.py tests/test_app_commands.py
git commit -m "feat: wire POL congress command into the app

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Manual verification (after the suite is green)

- Live: `.venv/bin/python scripts/smoke_congress.py NVDA` — prints roster trades + summaries.
- In `bbterm` (iTerm2): load `NVDA`, press `POL` → see roster members' buy/sell trades + summary. Try a symbol with no roster trades → "No congressional trades" notice. (Without `LAMBDA_API_KEY` → the key notice.)

## Notes for the implementer

- Branch is already `politician-trades`.
- The Lambda live-test gate already passed; fields in this plan are real.
- `congress.py` is pure (no I/O); the provider is the only network code, and it is injectable for tests.
- Do not commit `.env` (gitignored). Tests never read the key.
