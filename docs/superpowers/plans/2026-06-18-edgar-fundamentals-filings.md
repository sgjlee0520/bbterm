# SEC EDGAR Fundamentals & Filings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `FA` (fundamentals) and `FIL` (recent filings) views to bbterm, sourced from SEC EDGAR.

**Architecture:** A sync `EdgarProvider` (stdlib `urllib`) fetches raw JSON; pure functions in `data/fundamentals.py` extract metrics and filings; `DataService` caches raw JSON in DuckDB with a 24h TTL; two dumb Textual widgets render the results, switched by command verbs like the existing `GP`/`DES`.

**Tech Stack:** Python 3.11+, Textual, DuckDB, stdlib `urllib.request`/`json`, pytest + pytest-asyncio.

## Global Constraints

- No new third-party dependencies — EDGAR access uses stdlib `urllib.request` + `json`.
- Every EDGAR request must send header `User-Agent: bbterm/0.1 (yagurootajum@gmail.com)`.
- Tests make **no network calls** and spend **no** Databento credits. EDGAR is hit only by a manual smoke script excluded from the test run.
- Do **not** use yfinance for fundamentals (commercial-licensing reason).
- Keep widgets dumb: all parsing/derivation lives in pure, unit-tested modules.
- `asyncio_mode = auto` is set; async tests need no decorator.
- Run tests with `.venv/bin/python -m pytest`.

---

### Task 1: Models — `FundamentalMetric` and `Filing`

**Files:**
- Modify: `src/bbterm/data/models.py`
- Test: `tests/test_models.py` (create)

**Interfaces:**
- Produces: `FundamentalMetric(label: str, value: float, unit: str, period_end: date, fy: int, fp: str, yoy_pct: float | None)` and `Filing(form: str, filed_date: date, period: str, accession: str, url: str)`, both frozen dataclasses.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from datetime import date

from bbterm.data.models import Filing, FundamentalMetric


def test_fundamental_metric_fields():
    m = FundamentalMetric(
        label="Revenue", value=391_035_000_000.0, unit="USD",
        period_end=date(2024, 9, 28), fy=2024, fp="FY", yoy_pct=2.0,
    )
    assert m.label == "Revenue"
    assert m.yoy_pct == 2.0


def test_filing_fields():
    f = Filing(
        form="10-K", filed_date=date(2024, 11, 1), period="2024-09-28",
        accession="0000320193-24-000123",
        url="https://www.sec.gov/x-index.htm",
    )
    assert f.form == "10-K"
    assert f.accession.endswith("000123")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'FundamentalMetric'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/bbterm/data/models.py` (add `from datetime import date` to the existing `from datetime import datetime` line, making it `from datetime import date, datetime`):

```python
@dataclass(frozen=True)
class FundamentalMetric:
    label: str
    value: float
    unit: str
    period_end: date
    fy: int
    fp: str
    yoy_pct: float | None


@dataclass(frozen=True)
class Filing:
    form: str
    filed_date: date
    period: str
    accession: str
    url: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/models.py tests/test_models.py
git commit -m "feat: FundamentalMetric and Filing models"
```

---

### Task 2: Pure logic — `extract_fundamentals` and `parse_filings`

**Files:**
- Create: `src/bbterm/data/fundamentals.py`
- Create: `tests/fixtures/__init__.py` (empty)
- Create: `tests/fixtures/companyfacts_sample.json`
- Create: `tests/fixtures/submissions_sample.json`
- Test: `tests/test_fundamentals.py`

**Interfaces:**
- Consumes: `FundamentalMetric`, `Filing` from Task 1.
- Produces:
  - `METRIC_SPECS: list[MetricSpec]` where `MetricSpec(label: str, concepts: list[str], unit: str)`.
  - `extract_fundamentals(facts_json: dict) -> list[FundamentalMetric]`
  - `parse_filings(submissions_json: dict, limit: int = 20) -> list[Filing]`

- [ ] **Step 1: Create the fixtures**

`tests/fixtures/__init__.py`: empty file.

`tests/fixtures/companyfacts_sample.json` — a trimmed payload shaped exactly like EDGAR's `companyfacts`. `Revenues` has two fiscal years (for YoY), `EarningsPerShareDiluted` under `USD/shares`, `CommonStockSharesOutstanding` under `shares`, and a concept (`Goodwill`) that is **not** in `METRIC_SPECS` to prove unrelated facts are ignored. `GrossProfit` is absent to prove missing metrics are omitted.

```json
{
  "cik": 320193,
  "entityName": "Apple Inc.",
  "facts": {
    "us-gaap": {
      "Revenues": {
        "units": {
          "USD": [
            {"end": "2022-09-24", "val": 365817000000, "fy": 2022, "fp": "FY", "form": "10-K"},
            {"end": "2023-09-30", "val": 383285000000, "fy": 2023, "fp": "FY", "form": "10-K"},
            {"end": "2023-12-30", "val": 119575000000, "fy": 2024, "fp": "Q1", "form": "10-Q"}
          ]
        }
      },
      "NetIncomeLoss": {
        "units": {
          "USD": [
            {"end": "2022-09-24", "val": 99803000000, "fy": 2022, "fp": "FY", "form": "10-K"},
            {"end": "2023-09-30", "val": 96995000000, "fy": 2023, "fp": "FY", "form": "10-K"}
          ]
        }
      },
      "EarningsPerShareDiluted": {
        "units": {
          "USD/shares": [
            {"end": "2023-09-30", "val": 6.13, "fy": 2023, "fp": "FY", "form": "10-K"}
          ]
        }
      },
      "Assets": {
        "units": {
          "USD": [
            {"end": "2023-09-30", "val": 352583000000, "fy": 2023, "fp": "FY", "form": "10-K"}
          ]
        }
      },
      "CommonStockSharesOutstanding": {
        "units": {
          "shares": [
            {"end": "2023-09-30", "val": 15550061000, "fy": 2023, "fp": "FY", "form": "10-K"}
          ]
        }
      },
      "Goodwill": {
        "units": {
          "USD": [
            {"end": "2023-09-30", "val": 0, "fy": 2023, "fp": "FY", "form": "10-K"}
          ]
        }
      }
    }
  }
}
```

`tests/fixtures/submissions_sample.json` — shaped like EDGAR's `submissions`, columnar `filings.recent` arrays, newest first:

```json
{
  "cik": 320193,
  "name": "Apple Inc.",
  "filings": {
    "recent": {
      "accessionNumber": ["0000320193-24-000123", "0000320193-24-000100"],
      "filingDate": ["2024-11-01", "2024-08-02"],
      "reportDate": ["2024-09-28", "2024-06-29"],
      "form": ["10-K", "10-Q"],
      "primaryDocument": ["aapl-20240928.htm", "aapl-20240629.htm"]
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_fundamentals.py
import json
from datetime import date
from pathlib import Path

from bbterm.data.fundamentals import extract_fundamentals, parse_filings

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text())


def test_extract_returns_known_metrics_only():
    metrics = {m.label: m for m in extract_fundamentals(_load("companyfacts_sample.json"))}
    # Present metrics extracted, unrelated/absent ones omitted
    assert "Revenue" in metrics
    assert "Net Income" in metrics
    assert "EPS (diluted)" in metrics
    assert "Total Assets" in metrics
    assert "Shares Outstanding" in metrics
    assert "Gross Profit" not in metrics  # absent from fixture


def test_extract_picks_latest_annual_and_yoy():
    metrics = {m.label: m for m in extract_fundamentals(_load("companyfacts_sample.json"))}
    rev = metrics["Revenue"]
    assert rev.value == 383285000000  # FY2023, not the Q1 2024 datapoint
    assert rev.fy == 2023
    assert rev.period_end == date(2023, 9, 30)
    # YoY vs FY2022 (365817000000): (383285-365817)/365817*100
    assert round(rev.yoy_pct, 2) == 4.77


def test_extract_yoy_none_without_prior_year():
    metrics = {m.label: m for m in extract_fundamentals(_load("companyfacts_sample.json"))}
    assert metrics["EPS (diluted)"].yoy_pct is None  # only one year in fixture
    assert metrics["EPS (diluted)"].unit == "USD/shares"


def test_parse_filings_newest_first_with_url():
    filings = parse_filings(_load("submissions_sample.json"))
    assert len(filings) == 2
    first = filings[0]
    assert first.form == "10-K"
    assert first.filed_date == date(2024, 11, 1)
    assert first.period == "2024-09-28"
    assert first.accession == "0000320193-24-000123"
    assert first.url == (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019324000123/0000320193-24-000123-index.htm"
    )


def test_parse_filings_respects_limit():
    assert len(parse_filings(_load("submissions_sample.json"), limit=1)) == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_fundamentals.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bbterm.data.fundamentals'`

- [ ] **Step 4: Write minimal implementation**

```python
# src/bbterm/data/fundamentals.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from bbterm.data.models import Filing, FundamentalMetric


@dataclass(frozen=True)
class MetricSpec:
    label: str
    concepts: list[str]   # candidate XBRL concept names, first match wins
    unit: str             # units key: "USD" | "USD/shares" | "shares"


METRIC_SPECS: list[MetricSpec] = [
    MetricSpec("Revenue",
               ["RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues", "SalesRevenueNet"], "USD"),
    MetricSpec("Net Income", ["NetIncomeLoss"], "USD"),
    MetricSpec("EPS (diluted)", ["EarningsPerShareDiluted"], "USD/shares"),
    MetricSpec("Gross Profit", ["GrossProfit"], "USD"),
    MetricSpec("Total Assets", ["Assets"], "USD"),
    MetricSpec("Total Liabilities", ["Liabilities"], "USD"),
    MetricSpec("Stockholders' Equity",
               ["StockholdersEquity",
                "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
               "USD"),
    MetricSpec("Operating Cash Flow",
               ["NetCashProvidedByUsedInOperatingActivities"], "USD"),
    MetricSpec("Shares Outstanding",
               ["CommonStockSharesOutstanding",
                "EntityCommonStockSharesOutstanding"], "shares"),
]


def _find_unit_series(facts_json: dict, concept: str, unit: str) -> list[dict] | None:
    """Return the datapoint list for concept+unit, searching us-gaap then dei."""
    facts = facts_json.get("facts", {})
    for taxonomy in ("us-gaap", "dei"):
        node = facts.get(taxonomy, {}).get(concept)
        if node:
            series = node.get("units", {}).get(unit)
            if series:
                return series
    return None


def _annual(series: list[dict]) -> list[dict]:
    return [d for d in series if d.get("fp") == "FY" and "end" in d and "val" in d]


def _extract_one(facts_json: dict, spec: MetricSpec) -> FundamentalMetric | None:
    for concept in spec.concepts:
        series = _find_unit_series(facts_json, concept, spec.unit)
        if not series:
            continue
        annual = _annual(series)
        if not annual:
            continue
        latest = max(annual, key=lambda d: (d["end"], d.get("fy", 0)))
        prior = [d for d in annual if d.get("fy") == latest.get("fy", 0) - 1]
        yoy = None
        if prior:
            prior_val = max(prior, key=lambda d: d["end"])["val"]
            if prior_val:
                yoy = (latest["val"] - prior_val) / abs(prior_val) * 100
        return FundamentalMetric(
            label=spec.label,
            value=float(latest["val"]),
            unit=spec.unit,
            period_end=date.fromisoformat(latest["end"]),
            fy=int(latest.get("fy", 0)),
            fp="FY",
            yoy_pct=yoy,
        )
    return None


def extract_fundamentals(facts_json: dict) -> list[FundamentalMetric]:
    out = []
    for spec in METRIC_SPECS:
        metric = _extract_one(facts_json, spec)
        if metric is not None:
            out.append(metric)
    return out


def parse_filings(submissions_json: dict, limit: int = 20) -> list[Filing]:
    cik = int(submissions_json.get("cik", 0))
    recent = submissions_json.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    periods = recent.get("reportDate", [])
    accns = recent.get("accessionNumber", [])
    out: list[Filing] = []
    for i in range(min(limit, len(forms))):
        acc = accns[i]
        acc_nodash = acc.replace("-", "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/"
            f"{acc_nodash}/{acc}-index.htm"
        )
        out.append(Filing(
            form=forms[i],
            filed_date=date.fromisoformat(dates[i]),
            period=periods[i] if i < len(periods) else "",
            accession=acc,
            url=url,
        ))
    return out
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_fundamentals.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/data/fundamentals.py tests/test_fundamentals.py tests/fixtures/
git commit -m "feat: pure EDGAR extraction (fundamentals + filings)"
```

---

### Task 3: Store cache tables for EDGAR

**Files:**
- Modify: `src/bbterm/data/store.py`
- Test: `tests/test_store_edgar.py`

**Interfaces:**
- Produces on `Store`:
  - `get_edgar_facts(symbol: str) -> tuple[datetime, str] | None` (fetched_at, raw json)
  - `set_edgar_facts(symbol: str, json_str: str) -> None`
  - `get_edgar_filings(symbol: str) -> tuple[datetime, str] | None`
  - `set_edgar_filings(symbol: str, json_str: str) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store_edgar.py
from bbterm.data.store import Store


def test_edgar_facts_roundtrip():
    store = Store(":memory:")
    assert store.get_edgar_facts("AAPL") is None
    store.set_edgar_facts("AAPL", '{"x": 1}')
    row = store.get_edgar_facts("AAPL")
    assert row is not None
    fetched_at, payload = row
    assert payload == '{"x": 1}'
    assert fetched_at is not None


def test_edgar_filings_roundtrip_and_replace():
    store = Store(":memory:")
    store.set_edgar_filings("AAPL", '{"a": 1}')
    store.set_edgar_filings("AAPL", '{"a": 2}')  # upsert overwrites
    _, payload = store.get_edgar_filings("AAPL")
    assert payload == '{"a": 2}'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_store_edgar.py -v`
Expected: FAIL with `AttributeError: 'Store' object has no attribute 'get_edgar_facts'`

- [ ] **Step 3: Write minimal implementation**

In `src/bbterm/data/store.py`, add `from datetime import datetime` is already imported. Add two `CREATE TABLE` statements inside `_init_schema` (after the `watchlist` table):

```python
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS edgar_facts (
                symbol VARCHAR PRIMARY KEY, fetched_at TIMESTAMP, json VARCHAR
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS edgar_filings (
                symbol VARCHAR PRIMARY KEY, fetched_at TIMESTAMP, json VARCHAR
            )
            """
        )
```

Add these methods to `Store` (before `close`):

```python
    def get_edgar_facts(self, symbol: str) -> tuple[datetime, str] | None:
        return self._get_edgar("edgar_facts", symbol)

    def set_edgar_facts(self, symbol: str, json_str: str) -> None:
        self._set_edgar("edgar_facts", symbol, json_str)

    def get_edgar_filings(self, symbol: str) -> tuple[datetime, str] | None:
        return self._get_edgar("edgar_filings", symbol)

    def set_edgar_filings(self, symbol: str, json_str: str) -> None:
        self._set_edgar("edgar_filings", symbol, json_str)

    def _get_edgar(self, table: str, symbol: str) -> tuple[datetime, str] | None:
        row = self._con.execute(
            f"SELECT fetched_at, json FROM {table} WHERE symbol = ?", [symbol]
        ).fetchone()
        if row is None:
            return None
        return row[0], row[1]

    def _set_edgar(self, table: str, symbol: str, json_str: str) -> None:
        self._con.execute(
            f"INSERT OR REPLACE INTO {table} VALUES (?, ?, ?)",
            [symbol, datetime.now(), json_str],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_store_edgar.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/store.py tests/test_store_edgar.py
git commit -m "feat: DuckDB cache tables for EDGAR facts and filings"
```

---

### Task 4: EdgarProvider and Protocols

**Files:**
- Modify: `src/bbterm/data/providers/base.py`
- Create: `src/bbterm/data/providers/edgar.py`
- Test: `tests/test_edgar_provider.py`

**Interfaces:**
- Consumes: nothing from prior tasks except stdlib.
- Produces:
  - In `base.py`: `FundamentalsProvider` Protocol with `name: str` and `get_facts(symbol: str) -> dict`; `FilingsProvider` Protocol with `name: str` and `get_submissions(symbol: str) -> dict`.
  - `EdgarProvider` class with `name = "edgar"`, `__init__(self, user_agent: str = "bbterm/0.1 (yagurootajum@gmail.com)", *, opener=None)`, methods `get_facts(symbol)`, `get_submissions(symbol)`, and `_cik(symbol) -> str` (10-digit zero-padded). The `opener` param accepts a callable `(url, user_agent) -> bytes` so tests inject a fake instead of hitting the network.

Note: this task's tests inject a fake fetcher; **no network in tests.**

- [ ] **Step 1: Write the failing test**

```python
# tests/test_edgar_provider.py
import json

import pytest

from bbterm.data.providers.edgar import EdgarProvider

TICKERS = json.dumps({
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft"},
})


def make_provider(responses):
    """responses: dict mapping url-substring -> bytes payload."""
    calls = []

    def opener(url, user_agent):
        calls.append((url, user_agent))
        for needle, payload in responses.items():
            if needle in url:
                return payload
        raise AssertionError(f"unexpected url {url}")

    return EdgarProvider(opener=opener), calls


def test_cik_zero_padded():
    provider, _ = make_provider({"company_tickers.json": TICKERS.encode()})
    assert provider._cik("AAPL") == "0000320193"


def test_cik_unknown_symbol_raises():
    provider, _ = make_provider({"company_tickers.json": TICKERS.encode()})
    with pytest.raises(KeyError):
        provider._cik("NOPE")


def test_get_facts_hits_right_url_and_sends_user_agent():
    facts = {"cik": 320193, "facts": {}}
    provider, calls = make_provider({
        "company_tickers.json": TICKERS.encode(),
        "companyfacts/CIK0000320193.json": json.dumps(facts).encode(),
    })
    assert provider.get_facts("AAPL") == facts
    # every call carried the User-Agent
    assert all("bbterm/0.1" in ua for _, ua in calls)


def test_get_submissions_hits_right_url():
    subs = {"cik": 320193, "filings": {"recent": {}}}
    provider, _ = make_provider({
        "company_tickers.json": TICKERS.encode(),
        "submissions/CIK0000320193.json": json.dumps(subs).encode(),
    })
    assert provider.get_submissions("AAPL") == subs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_edgar_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bbterm.data.providers.edgar'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/bbterm/data/providers/base.py`:

```python
class FundamentalsProvider(Protocol):
    name: str

    def get_facts(self, symbol: str) -> dict: ...


class FilingsProvider(Protocol):
    name: str

    def get_submissions(self, symbol: str) -> dict: ...
```

Create `src/bbterm/data/providers/edgar.py`:

```python
from __future__ import annotations

import json
import time
import urllib.request

_USER_AGENT = "bbterm/0.1 (yagurootajum@gmail.com)"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


def _http_get(url: str, user_agent: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


class EdgarProvider:
    name = "edgar"

    def __init__(
        self,
        user_agent: str = _USER_AGENT,
        *,
        opener=None,
        rate_limit_sleep: float = 0.0,
    ) -> None:
        self._ua = user_agent
        self._open = opener or _http_get
        self._sleep = rate_limit_sleep
        self._cik_map: dict[str, str] | None = None

    def _fetch(self, url: str) -> bytes:
        if self._sleep:
            time.sleep(self._sleep)
        return self._open(url, self._ua)

    def _load_cik_map(self) -> dict[str, str]:
        raw = json.loads(self._fetch(_TICKERS_URL))
        out: dict[str, str] = {}
        for row in raw.values():
            out[str(row["ticker"]).upper()] = f"{int(row['cik_str']):010d}"
        return out

    def _cik(self, symbol: str) -> str:
        if self._cik_map is None:
            self._cik_map = self._load_cik_map()
        return self._cik_map[symbol.upper()]

    def get_facts(self, symbol: str) -> dict:
        url = _FACTS_URL.format(cik=self._cik(symbol))
        return json.loads(self._fetch(url))

    def get_submissions(self, symbol: str) -> dict:
        url = _SUBMISSIONS_URL.format(cik=self._cik(symbol))
        return json.loads(self._fetch(url))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_edgar_provider.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/providers/base.py src/bbterm/data/providers/edgar.py tests/test_edgar_provider.py
git commit -m "feat: EdgarProvider with injectable fetcher and CIK resolution"
```

---

### Task 5: Service — `get_fundamentals` / `get_filings` with TTL cache

**Files:**
- Modify: `src/bbterm/data/service.py`
- Test: `tests/test_service_edgar.py`

**Interfaces:**
- Consumes: `Store.get_edgar_facts/set_edgar_facts/get_edgar_filings/set_edgar_filings` (Task 3); `FundamentalsProvider`/`FilingsProvider` (Task 4); `extract_fundamentals`/`parse_filings` (Task 2).
- Produces on `DataService`:
  - new optional `__init__` param `edgar_provider=None` (provider exposing `get_facts` + `get_submissions`).
  - `async get_fundamentals(symbol: str) -> list[FundamentalMetric]`
  - `async get_filings(symbol: str) -> list[Filing]`
  - module constant `EDGAR_TTL_SECONDS = 86400.0`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_service_edgar.py
import json

from bbterm.data.service import DataService
from bbterm.data.store import Store


class FakeEdgar:
    name = "edgar"

    def __init__(self):
        self.facts_calls = 0
        self.subs_calls = 0

    def get_facts(self, symbol):
        self.facts_calls += 1
        return {
            "cik": 1, "facts": {"us-gaap": {"Revenues": {"units": {"USD": [
                {"end": "2023-12-31", "val": 100, "fy": 2023, "fp": "FY"},
                {"end": "2022-12-31", "val": 80, "fy": 2022, "fp": "FY"},
            ]}}}},
        }

    def get_submissions(self, symbol):
        self.subs_calls += 1
        return {"cik": 1, "filings": {"recent": {
            "accessionNumber": ["0000000001-24-000001"],
            "filingDate": ["2024-01-15"], "reportDate": ["2023-12-31"],
            "form": ["10-K"], "primaryDocument": ["x.htm"],
        }}}


def _service(edgar):
    return DataService(Store(":memory:"), None, None, edgar_provider=edgar)


async def test_get_fundamentals_extracts_and_caches():
    edgar = FakeEdgar()
    svc = _service(edgar)
    metrics = await svc.get_fundamentals("AAPL")
    labels = {m.label for m in metrics}
    assert "Revenue" in labels
    # second call served from cache (TTL not expired) -> provider not hit again
    await svc.get_fundamentals("AAPL")
    assert edgar.facts_calls == 1


async def test_get_filings_parses_and_caches():
    edgar = FakeEdgar()
    svc = _service(edgar)
    filings = await svc.get_filings("AAPL")
    assert filings[0].form == "10-K"
    await svc.get_filings("AAPL")
    assert edgar.subs_calls == 1


async def test_get_fundamentals_degrades_to_cache_on_error():
    edgar = FakeEdgar()
    svc = _service(edgar)
    await svc.get_fundamentals("AAPL")  # warm cache

    def boom(symbol):
        raise RuntimeError("network down")

    edgar.get_facts = boom
    svc._edgar_fresh = lambda *a, **k: False  # force a refetch attempt
    metrics = await svc.get_fundamentals("AAPL")  # should fall back to cache
    assert any(m.label == "Revenue" for m in metrics)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_service_edgar.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'edgar_provider'`

- [ ] **Step 3: Write minimal implementation**

In `src/bbterm/data/service.py`:

Add imports at top (after existing imports):

```python
import json

from bbterm.data.fundamentals import extract_fundamentals, parse_filings
from bbterm.data.models import Bar, Filing, FundamentalMetric, Quote
```

(Replace the existing `from bbterm.data.models import Bar, Quote` line with the expanded one above.)

Add module constant near `FETCH_TTL_SECONDS`:

```python
EDGAR_TTL_SECONDS = 86400.0
```

Extend `__init__` signature and body:

```python
    def __init__(
        self,
        store: Store,
        bar_provider: BarProvider,
        quote_provider: QuoteProvider,
        fetch_ttl: float = FETCH_TTL_SECONDS,
        edgar_provider=None,
    ) -> None:
        self.store = store
        self._bars = bar_provider
        self._quotes = quote_provider
        self._ttl = fetch_ttl
        self._edgar = edgar_provider
        self._last_fetch: dict[tuple[str, str], float] = {}
```

Add methods at the end of the class:

```python
    def _edgar_fresh(self, cached) -> bool:
        if cached is None:
            return False
        fetched_at, _ = cached
        return (datetime.now() - fetched_at).total_seconds() < EDGAR_TTL_SECONDS

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

    async def get_filings(self, symbol: str) -> list[Filing]:
        cached = self.store.get_edgar_filings(symbol)
        if not self._edgar_fresh(cached):
            try:
                subs = await asyncio.to_thread(self._edgar.get_submissions, symbol)
                self.store.set_edgar_filings(symbol, json.dumps(subs))
                cached = self.store.get_edgar_filings(symbol)
            except Exception:
                if cached is None:
                    raise
        _, payload = cached
        return parse_filings(json.loads(payload))
```

Add `from datetime import datetime, timedelta` — `datetime` is already imported at the top of the file; confirm the existing import line is `from datetime import datetime, timedelta` (it is). No change needed there.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_service_edgar.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/service.py tests/test_service_edgar.py
git commit -m "feat: DataService.get_fundamentals/get_filings with 24h cache"
```

---

### Task 6: Commands — `FA` and `FIL` verbs

**Files:**
- Modify: `src/bbterm/commands.py`
- Test: `tests/test_commands.py` (append)

**Interfaces:**
- Consumes: `parse_command` (existing).
- Produces: frozen dataclasses `ShowFundamentals` and `ShowFilings`; `parse_command("FA")` → `ShowFundamentals()`, `parse_command("FIL")` → `ShowFilings()`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_commands.py`:

```python
from bbterm.commands import ShowFilings, ShowFundamentals, parse_command


def test_fa_parses_to_show_fundamentals():
    assert isinstance(parse_command("FA"), ShowFundamentals)
    assert isinstance(parse_command("fa"), ShowFundamentals)


def test_fil_parses_to_show_filings():
    assert isinstance(parse_command("FIL"), ShowFilings)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commands.py -k "fundamentals or filings" -v`
Expected: FAIL with `ImportError: cannot import name 'ShowFundamentals'`

- [ ] **Step 3: Write minimal implementation**

In `src/bbterm/commands.py`, add dataclasses (after `ShowStats`):

```python
@dataclass(frozen=True)
class ShowFundamentals:
    pass


@dataclass(frozen=True)
class ShowFilings:
    pass
```

In `parse_command`, add before the `if verb in ("?", "HELP"):` line:

```python
    if verb == "FA":
        return ShowFundamentals()
    if verb == "FIL":
        return ShowFilings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_commands.py -v`
Expected: PASS (all command tests pass)

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/commands.py tests/test_commands.py
git commit -m "feat: FA and FIL command verbs"
```

---

### Task 7: Widgets — `FundamentalsView` and `FilingsView`

**Files:**
- Create: `src/bbterm/tui/widgets/fundamentals.py`
- Create: `src/bbterm/tui/widgets/filings.py`
- Test: `tests/test_edgar_views.py`

**Interfaces:**
- Consumes: `FundamentalMetric`, `Filing` (Task 1).
- Produces:
  - `human_money(value: float) -> str` and `human_count(value: float) -> str` and `render_fundamentals_text(metrics: list[FundamentalMetric]) -> str` in `fundamentals.py`; `FundamentalsView(Widget)` with `.show(metrics)`.
  - `render_filings_text(filings: list[Filing]) -> str` in `filings.py`; `FilingsView(Widget)` with `.show(filings)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_edgar_views.py
from datetime import date

from bbterm.data.models import Filing, FundamentalMetric
from bbterm.tui.widgets.fundamentals import (
    human_money, render_fundamentals_text,
)
from bbterm.tui.widgets.filings import render_filings_text


def test_human_money_scales():
    assert human_money(391_035_000_000) == "$391.04B"
    assert human_money(6.13) == "$6.13"
    assert human_money(-2_500_000) == "-$2.50M"


def test_render_fundamentals_has_label_value_period_yoy():
    metrics = [
        FundamentalMetric("Revenue", 383285000000, "USD",
                          date(2023, 9, 30), 2023, "FY", 4.77),
        FundamentalMetric("EPS (diluted)", 6.13, "USD/shares",
                          date(2023, 9, 30), 2023, "FY", None),
    ]
    text = render_fundamentals_text(metrics)
    assert "Revenue" in text
    assert "$383.29B" in text
    assert "FY2023" in text
    assert "+4.77%" in text
    assert "n/a" in text  # EPS YoY is None


def test_render_filings_lists_rows():
    filings = [
        Filing("10-K", date(2024, 11, 1), "2024-09-28",
               "0000320193-24-000123", "https://x/index.htm"),
    ]
    text = render_filings_text(filings)
    assert "10-K" in text
    assert "2024-11-01" in text
    assert "https://x/index.htm" in text


def test_empty_renders_message():
    assert "No" in render_fundamentals_text([])
    assert "No" in render_filings_text([])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_edgar_views.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bbterm.tui.widgets.fundamentals'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/bbterm/tui/widgets/fundamentals.py
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from bbterm.data.models import FundamentalMetric


def human_money(value: float) -> str:
    sign = "-" if value < 0 else ""
    v = abs(float(value))
    for unit, size in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if v >= size:
            return f"{sign}${v / size:.2f}{unit}"
    return f"{sign}${v:.2f}"


def human_count(value: float) -> str:
    v = float(value)
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if v >= size:
            return f"{v / size:.2f}{unit}"
    return f"{int(v)}"


def _value_str(m: FundamentalMetric) -> str:
    if m.unit == "shares":
        return f"{human_count(m.value)} sh"
    return human_money(m.value)


def _yoy_str(yoy: float | None) -> str:
    if yoy is None:
        return "n/a"
    sign = "+" if yoy >= 0 else ""
    return f"{sign}{yoy:.2f}%"


def render_fundamentals_text(metrics: list[FundamentalMetric]) -> str:
    if not metrics:
        return "  No fundamentals available."
    lines = ["  Fundamentals (latest annual)", ""]
    for m in metrics:
        period = f"FY{m.fy}"
        lines.append(
            f"  {m.label:<22}{_value_str(m):>14}  {period:<8}{_yoy_str(m.yoy_pct):>9}"
        )
    return "\n".join(lines)


class FundamentalsView(Widget):
    DEFAULT_CSS = """
    FundamentalsView { height: 1fr; }
    FundamentalsView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    FundamentalsView > Static.body { width: 100%; height: 1fr; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        yield Label("FUNDAMENTALS", classes="header")
        yield Static("  Select a symbol.", classes="body")

    def show(self, metrics: list[FundamentalMetric]) -> None:
        self.query_one(".body", Static).update(
            Text(render_fundamentals_text(metrics))
        )
```

```python
# src/bbterm/tui/widgets/filings.py
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from bbterm.data.models import Filing


def render_filings_text(filings: list[Filing]) -> str:
    if not filings:
        return "  No filings available."
    lines = ["  Recent SEC filings", ""]
    for f in filings:
        date_str = f.filed_date.isoformat()
        lines.append(f"  {f.form:<8}{date_str:<12}{f.period:<12}{f.url}")
    return "\n".join(lines)


class FilingsView(Widget):
    DEFAULT_CSS = """
    FilingsView { height: 1fr; }
    FilingsView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    FilingsView > Static.body { width: 100%; height: 1fr; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        yield Label("FILINGS", classes="header")
        yield Static("  Select a symbol.", classes="body")

    def show(self, filings: list[Filing]) -> None:
        self.query_one(".body", Static).update(Text(render_filings_text(filings)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_edgar_views.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/tui/widgets/fundamentals.py src/bbterm/tui/widgets/filings.py tests/test_edgar_views.py
git commit -m "feat: FundamentalsView and FilingsView widgets"
```

---

### Task 8: Wire views into the app

**Files:**
- Modify: `src/bbterm/tui/app.py`
- Modify: `src/bbterm/data/__init__.py`
- Test: `tests/test_app_commands.py` (append)

**Interfaces:**
- Consumes: `ShowFundamentals`/`ShowFilings` (Task 6), `FundamentalsView`/`FilingsView` (Task 7), `DataService.get_fundamentals`/`get_filings` (Task 5), `EdgarProvider` (Task 4).
- Produces: `FA` switches `ContentSwitcher` to `fundamentals`; `FIL` switches to `filings`; workers `load_fundamentals`/`load_filings`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_app_commands.py`. First extend the fake setup at the top of the file by adding a fake EDGAR provider and passing it to the service. Add this class and update `_app`:

```python
class FakeEdgar:
    name = "edgar"

    def get_facts(self, symbol):
        return {"cik": 1, "facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            {"end": "2023-12-31", "val": 100, "fy": 2023, "fp": "FY"},
        ]}}}}}

    def get_submissions(self, symbol):
        return {"cik": 1, "filings": {"recent": {
            "accessionNumber": ["0000000001-24-000001"],
            "filingDate": ["2024-01-15"], "reportDate": ["2023-12-31"],
            "form": ["10-K"], "primaryDocument": ["x.htm"],
        }}}
```

Update the existing `_app()` to pass `edgar_provider=FakeEdgar()`:

```python
def _app():
    bars = make_bars("SPY", "1d", start=datetime.now() - timedelta(days=400), n=300)
    fake = FakeProvider(bars=bars, quote=Quote("SPY", 101.0, 100.0))
    service = DataService(Store(":memory:"), fake, fake, fetch_ttl=0.0,
                          edgar_provider=FakeEdgar())
    return BloombergApp(service=service, watchlist=["SPY"]), service
```

Add the new tests:

```python
async def test_fa_switches_to_fundamentals_view():
    app, _ = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "FA")
        assert app.query_one(ContentSwitcher).current == "fundamentals"


async def test_fil_switches_to_filings_view():
    app, _ = _app()
    async with app.run_test() as pilot:
        await _submit(pilot, app, "FIL")
        assert app.query_one(ContentSwitcher).current == "filings"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_app_commands.py -k "fundamentals or filings" -v`
Expected: FAIL — either the switcher has no `fundamentals` view, or `ShowFundamentals` isn't dispatched.

- [ ] **Step 3: Write minimal implementation**

In `src/bbterm/data/__init__.py`, construct and inject an `EdgarProvider`:

```python
from bbterm.data.providers.edgar import EdgarProvider
```

and in both `return DataService(...)` lines, add `edgar_provider=EdgarProvider()`:

```python
        return DataService(store, bars, yf_provider, edgar_provider=EdgarProvider())
    return DataService(store, yf_provider, yf_provider, edgar_provider=EdgarProvider())
```

In `src/bbterm/tui/app.py`:

Update imports:

```python
from bbterm.commands import (
    AddSymbol, Help, LoadSymbol, RemoveSymbol, ShowChart, ShowFilings,
    ShowFundamentals, ShowStats, Unknown, parse_command,
)
from bbterm.tui.widgets.fundamentals import FundamentalsView
from bbterm.tui.widgets.filings import FilingsView
```

In `compose`, add the two views inside the `ContentSwitcher`:

```python
            with ContentSwitcher(initial="chart", id="switcher"):
                yield ChartPanel(id="chart")
                yield StatsView(id="stats")
                yield FundamentalsView(id="fundamentals")
                yield FilingsView(id="filings")
```

In `_dispatch`, add branches (after the `ShowStats` branch):

```python
        elif isinstance(command, ShowFundamentals):
            self.query_one("#switcher", ContentSwitcher).current = "fundamentals"
            self.load_fundamentals()
        elif isinstance(command, ShowFilings):
            self.query_one("#switcher", ContentSwitcher).current = "filings"
            self.load_filings()
```

Add two workers (after `load_stats`):

```python
    @work(exclusive=True, group="fundamentals")
    async def load_fundamentals(self) -> None:
        try:
            metrics = await self.service.get_fundamentals(self.current_symbol)
        except Exception as err:
            self.notify(f"EDGAR unavailable ({err})", severity="warning")
            metrics = []
        self.query_one(FundamentalsView).show(metrics)

    @work(exclusive=True, group="filings")
    async def load_filings(self) -> None:
        try:
            filings = await self.service.get_filings(self.current_symbol)
        except Exception as err:
            self.notify(f"EDGAR unavailable ({err})", severity="warning")
            filings = []
        self.query_one(FilingsView).show(filings)
```

Update `_refresh_active_view` to refresh the new views when active:

```python
    def _refresh_active_view(self) -> None:
        current = self.query_one("#switcher", ContentSwitcher).current
        if current == "stats":
            self.load_stats()
        elif current == "fundamentals":
            self.load_fundamentals()
        elif current == "filings":
            self.load_filings()
        else:
            self.load_chart()
```

Update the `_HELP` string to mention the new verbs:

```python
_HELP = (
    "Commands: <ticker> load · ADD <sym> · DEL <sym> · GP chart · DES stats · "
    "FA fundamentals · FIL filings · ? help   |   Keys: :=command 1-6=period "
    "c=line/candle r=refresh q=quit"
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_app_commands.py -v`
Expected: PASS (all app-command tests, including the two new ones)

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (all prior tests + the new EDGAR tests)

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/tui/app.py src/bbterm/data/__init__.py tests/test_app_commands.py
git commit -m "feat: wire FA/FIL views, workers, and EdgarProvider into the app"
```

---

### Task 9: Manual smoke script + user-guide update

**Files:**
- Create: `scripts/smoke_edgar.py`
- Modify: `docs/manual/bbterm-guide.tex`

**Interfaces:**
- Consumes: `EdgarProvider`, `extract_fundamentals`, `parse_filings`.
- Produces: a runnable script (not collected by pytest — it lives under `scripts/`, and `testpaths = ["tests"]` excludes it) and updated docs.

- [ ] **Step 1: Create the smoke script**

```python
# scripts/smoke_edgar.py
"""Manual EDGAR smoke check — hits the live SEC API once. Run by hand:
    .venv/bin/python scripts/smoke_edgar.py AAPL
Not part of the pytest suite (no network in tests)."""
import sys

from bbterm.data.fundamentals import extract_fundamentals, parse_filings
from bbterm.data.providers.edgar import EdgarProvider


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    provider = EdgarProvider(rate_limit_sleep=0.2)
    print(f"CIK({symbol}) = {provider._cik(symbol)}")
    metrics = extract_fundamentals(provider.get_facts(symbol))
    for m in metrics:
        print(f"  {m.label:<22}{m.value:>18,.0f}  FY{m.fy}  yoy={m.yoy_pct}")
    print("--- filings ---")
    for f in parse_filings(provider.get_submissions(symbol), limit=5):
        print(f"  {f.form:<8}{f.filed_date}  {f.url}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the smoke script manually (one live call)**

Run: `.venv/bin/python scripts/smoke_edgar.py AAPL`
Expected: prints `CIK(AAPL) = 0000320193`, a list of fundamentals (Revenue, Net Income, etc.), and 5 recent filings with URLs. If this fails with HTTP 403, the `User-Agent` header is being rejected — verify it is set.

- [ ] **Step 3: Update the user guide**

In `docs/manual/bbterm-guide.tex`, add two rows to the Commands table (inside the `tabular`, before `\bottomrule`):

```latex
\texttt{FA} & Show company fundamentals (from SEC EDGAR) \\
\texttt{FIL} & Show recent SEC filings \\
```

And add a short section before `\section{Reading the statistics panel (DES)}`:

```latex
\section{Fundamentals and filings (FA / FIL)}
Type \texttt{FA} to see headline financials --- revenue, net income, earnings
per share, assets, and more --- with each figure's fiscal year and its change
versus the prior year. Type \texttt{FIL} to see the company's most recent filings
with the U.S. Securities and Exchange Commission (annual 10-K, quarterly 10-Q,
and event-driven 8-K reports), each with the date and a link. This data comes
from SEC EDGAR, is free and public, and is cached on your machine for a day.
```

- [ ] **Step 4: Rebuild the PDF**

Run: `cd docs/manual && pdflatex -interaction=nonstopmode bbterm-guide.tex >/dev/null && pdflatex -interaction=nonstopmode bbterm-guide.tex >/dev/null && cd ../..`
Expected: `bbterm-guide.pdf` regenerated, no fatal error (exit 0).

- [ ] **Step 5: Commit**

```bash
git add scripts/smoke_edgar.py docs/manual/bbterm-guide.tex
git commit -m "docs: EDGAR smoke script and user-guide FA/FIL section"
```

---

## Done criteria

- `.venv/bin/python -m pytest -q` passes with the new EDGAR tests.
- `FA` and `FIL` load real data in a live run (manual).
- No new third-party dependencies; EDGAR requests send the required `User-Agent`.
- User guide PDF rebuilt with the FA/FIL section.
