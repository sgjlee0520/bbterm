# Data Foundation + Databento Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the terminal on an async, provider-abstracted data layer with a DuckDB cache-through store, then add Databento as the primary historical source with a hard cost cap.

**Architecture:** UI widgets never fetch data; they render what `DataService` hands them. `DataService` (async) reads DuckDB first and fetches only missing date ranges from a provider, so each paid record is bought once. Providers are sync objects behind a `Protocol`, run via `asyncio.to_thread`; yfinance is the dev fallback, Databento the real source.

**Tech Stack:** Python 3.11+, Textual, plotext, DuckDB, databento, yfinance (dev only), pytest + pytest-asyncio.

**Conventions for every task:** run commands from `/Users/slee/bloomberg`; use `.venv/bin/python -m pytest` (no activation needed). Databento needs `DATABENTO_API_KEY`, which lives in `~/.zshrc` — non-interactive shells must `source ~/.zshrc` first (only Tasks 11 and 13 need it).

**Notes locked in during design:**
- Default watchlist becomes equities-only (no `BTC-USD`/`ETH-USD`): Databento equities datasets don't carry crypto. Crypto can return later via a separate provider.
- The yfinance provider drops the `t.info` name lookup (it was the slowest call). `Quote.name` defaults to `""`.
- Coverage tracking assumes the cached range per (symbol, interval) is contiguous (min/max timestamps). Fine for our access pattern (always fetch whole gaps).

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `src/bbterm/__init__.py`, `src/bbterm/data/__init__.py`, `src/bbterm/data/providers/__init__.py`, `src/bbterm/tui/__init__.py`, `src/bbterm/tui/widgets/__init__.py`, `tests/` (dir)
- Keep for now: `terminal/`, `main.py`, `requirements.txt` (deleted in Task 10 after parity)

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "bbterm"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "textual>=0.47.0",
    "plotext>=5.2.8",
    "duckdb>=0.9.0",
    "pandas>=2.0.0",
    "yfinance>=0.2.36",
    "databento>=0.34.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[project.scripts]
bbterm = "bbterm.tui.app:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create package skeleton**

```bash
mkdir -p src/bbterm/data/providers src/bbterm/tui/widgets tests data
touch src/bbterm/__init__.py src/bbterm/data/__init__.py \
      src/bbterm/data/providers/__init__.py src/bbterm/tui/__init__.py \
      src/bbterm/tui/widgets/__init__.py
```

- [ ] **Step 3: Create venv and install**

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Expected: install succeeds (databento + textual + duckdb resolve).

- [ ] **Step 4: Verify pytest runs and package imports**

Run: `.venv/bin/python -c "import bbterm; print('OK')" && .venv/bin/python -m pytest`
Expected: `OK`, then pytest exits with "no tests ran".

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/ && git commit -m "feat: src-layout package skeleton with pyproject"
```

---

### Task 2: Domain models (`Bar`, `Quote`)

**Files:**
- Create: `src/bbterm/data/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from datetime import datetime
from bbterm.data.models import Bar, Quote


def test_quote_derives_change_fields():
    q = Quote(symbol="AAPL", price=110.0, prev_close=100.0)
    assert q.change == 10.0
    assert q.pct_change == 10.0
    assert q.is_up
    assert q.change_str == "+10.00 (+10.00%)"


def test_quote_handles_zero_prev_close():
    q = Quote(symbol="X", price=5.0, prev_close=0.0)
    assert q.pct_change == 0.0


def test_bar_is_frozen_value_object():
    b = Bar("AAPL", "1d", datetime(2026, 1, 5), 1.0, 2.0, 0.5, 1.5, 100)
    assert b.close == 1.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bbterm.data.models'`

- [ ] **Step 3: Write the implementation**

```python
# src/bbterm/data/models.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Bar:
    symbol: str
    interval: str  # "1d" or "1m"
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    prev_close: float
    name: str = ""

    @property
    def change(self) -> float:
        return self.price - self.prev_close

    @property
    def pct_change(self) -> float:
        if not self.prev_close:
            return 0.0
        return self.change / self.prev_close * 100

    @property
    def is_up(self) -> bool:
        return self.change >= 0

    @property
    def change_str(self) -> str:
        sign = "+" if self.change >= 0 else ""
        return f"{sign}{self.change:.2f} ({sign}{self.pct_change:.2f}%)"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/models.py tests/test_models.py
git commit -m "feat: Bar and Quote domain models"
```

---

### Task 3: Config loading

**Files:**
- Create: `src/bbterm/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from pathlib import Path
from bbterm.config import load_config


def test_defaults_when_nothing_set(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    cfg = load_config(root=tmp_path)
    assert cfg.databento_api_key is None
    assert cfg.db_path == tmp_path / "data" / "market.duckdb"
    assert cfg.cost_cap_usd == 1.0
    assert cfg.databento_dataset == "EQUS.MINI"


def test_env_var_wins_over_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text('DATABENTO_API_KEY="db-from-file"\n')
    monkeypatch.setenv("DATABENTO_API_KEY", "db-from-env")
    cfg = load_config(root=tmp_path)
    assert cfg.databento_api_key == "db-from-env"


def test_dotenv_used_when_env_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "# comment\nDATABENTO_API_KEY=db-from-file\nBBTERM_COST_CAP_USD=0.25\n"
    )
    cfg = load_config(root=tmp_path)
    assert cfg.databento_api_key == "db-from-file"
    assert cfg.cost_cap_usd == 0.25
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bbterm.config'`

- [ ] **Step 3: Write the implementation**

```python
# src/bbterm/config.py
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    databento_api_key: str | None
    db_path: Path
    cost_cap_usd: float
    databento_dataset: str


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_config(root: Path | None = None) -> Config:
    root = root or Path.cwd()
    env = {**_load_dotenv(root / ".env"), **os.environ}
    return Config(
        databento_api_key=env.get("DATABENTO_API_KEY"),
        db_path=Path(env.get("BBTERM_DB_PATH", str(root / "data" / "market.duckdb"))),
        cost_cap_usd=float(env.get("BBTERM_COST_CAP_USD", "1.0")),
        databento_dataset=env.get("BBTERM_DATASET", "EQUS.MINI"),
    )
```

(Note: `EQUS.MINI` is a provisional default — Task 11 verifies the dataset against the live metadata API and changes this default if needed.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/config.py tests/test_config.py
git commit -m "feat: config loading from env and .env"
```

---

### Task 4: DuckDB store

**Files:**
- Create: `src/bbterm/data/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
from datetime import datetime
import pytest
from bbterm.data.models import Bar
from bbterm.data.store import Store, DEFAULT_WATCHLIST


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


def _bar(day: int, close: float = 10.0) -> Bar:
    return Bar("AAPL", "1d", datetime(2026, 1, day), 9.0, 11.0, 8.0, close, 100)


def test_upsert_and_range_query(store):
    store.upsert_bars([_bar(5), _bar(6), _bar(7)])
    got = store.get_bars("AAPL", "1d", datetime(2026, 1, 5), datetime(2026, 1, 6))
    assert [b.ts.day for b in got] == [5, 6]
    assert got[0] == _bar(5)


def test_upsert_is_idempotent_and_replaces(store):
    store.upsert_bars([_bar(5, close=10.0)])
    store.upsert_bars([_bar(5, close=99.0)])
    got = store.get_bars("AAPL", "1d", datetime(2026, 1, 1), datetime(2026, 1, 31))
    assert len(got) == 1
    assert got[0].close == 99.0


def test_coverage(store):
    assert store.coverage("AAPL", "1d") is None
    store.upsert_bars([_bar(5), _bar(9)])
    assert store.coverage("AAPL", "1d") == (datetime(2026, 1, 5), datetime(2026, 1, 9))


def test_intervals_are_separate(store):
    store.upsert_bars([_bar(5)])
    assert store.get_bars("AAPL", "1m", datetime(2026, 1, 1), datetime(2026, 1, 31)) == []


def test_watchlist_seeds_defaults_then_persists(store):
    assert store.get_watchlist() == DEFAULT_WATCHLIST
    store.set_watchlist(["TSLA", "SPY"])
    assert store.get_watchlist() == ["TSLA", "SPY"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bbterm.data.store'`

- [ ] **Step 3: Write the implementation**

```python
# src/bbterm/data/store.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb

from bbterm.data.models import Bar

DEFAULT_WATCHLIST = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]


class Store:
    def __init__(self, path: Path | str) -> None:
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(str(path))
        self._init_schema()

    def _init_schema(self) -> None:
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS ohlcv (
                symbol VARCHAR, interval VARCHAR, ts TIMESTAMP,
                open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
                volume BIGINT,
                PRIMARY KEY (symbol, interval, ts)
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                position INTEGER, symbol VARCHAR PRIMARY KEY
            )
            """
        )

    def upsert_bars(self, bars: list[Bar]) -> None:
        if not bars:
            return
        rows = [
            (b.symbol, b.interval, b.ts, b.open, b.high, b.low, b.close, b.volume)
            for b in bars
        ]
        self._con.executemany(
            "INSERT OR REPLACE INTO ohlcv VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
        )

    def get_bars(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Bar]:
        rows = self._con.execute(
            """
            SELECT symbol, interval, ts, open, high, low, close, volume
            FROM ohlcv
            WHERE symbol = ? AND interval = ? AND ts >= ? AND ts <= ?
            ORDER BY ts
            """,
            [symbol, interval, start, end],
        ).fetchall()
        return [Bar(*row) for row in rows]

    def coverage(
        self, symbol: str, interval: str
    ) -> tuple[datetime, datetime] | None:
        row = self._con.execute(
            "SELECT min(ts), max(ts) FROM ohlcv WHERE symbol = ? AND interval = ?",
            [symbol, interval],
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return row[0], row[1]

    def get_watchlist(self) -> list[str]:
        rows = self._con.execute(
            "SELECT symbol FROM watchlist ORDER BY position"
        ).fetchall()
        if not rows:
            self.set_watchlist(DEFAULT_WATCHLIST)
            return list(DEFAULT_WATCHLIST)
        return [r[0] for r in rows]

    def set_watchlist(self, symbols: list[str]) -> None:
        self._con.execute("DELETE FROM watchlist")
        self._con.executemany(
            "INSERT INTO watchlist VALUES (?, ?)", list(enumerate(symbols))
        )

    def close(self) -> None:
        self._con.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_store.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/store.py tests/test_store.py
git commit -m "feat: DuckDB store with ohlcv upsert, coverage, watchlist"
```

---

### Task 5: Provider protocol + fake provider

**Files:**
- Create: `src/bbterm/data/providers/base.py`, `tests/fakes.py`
- Test: `tests/test_providers_base.py`

Note: tests import the fake as `from fakes import ...` — pytest prepends `tests/` to `sys.path` because the directory has no `__init__.py`. Do not add `tests/__init__.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_providers_base.py
import pytest
from bbterm.data.providers.base import CostCapExceeded


def test_cost_cap_exceeded_carries_amounts():
    err = CostCapExceeded(estimated_usd=2.5, cap_usd=1.0)
    assert err.estimated_usd == 2.5
    assert err.cap_usd == 1.0
    assert "2.5" in str(err) and "1.00" in str(err)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_providers_base.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write base.py and fakes.py**

```python
# src/bbterm/data/providers/base.py
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from bbterm.data.models import Bar, Quote


class CostCapExceeded(Exception):
    def __init__(self, estimated_usd: float, cap_usd: float) -> None:
        self.estimated_usd = estimated_usd
        self.cap_usd = cap_usd
        super().__init__(
            f"estimated cost ${estimated_usd:.4f} exceeds cap ${cap_usd:.2f}"
        )


class BarProvider(Protocol):
    name: str

    def get_bars(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Bar]: ...


class QuoteProvider(Protocol):
    name: str

    def get_quote(self, symbol: str) -> Quote | None: ...
```

```python
# tests/fakes.py
from datetime import datetime, timedelta

from bbterm.data.models import Bar, Quote


def make_bars(symbol="AAPL", interval="1d", start=None, n=5, price=100.0):
    start = start or datetime(2026, 1, 5)
    step = timedelta(days=1) if interval == "1d" else timedelta(minutes=1)
    return [
        Bar(
            symbol, interval, start + i * step,
            price + i, price + i + 1, price + i - 1, price + i + 0.5, 1000 + i,
        )
        for i in range(n)
    ]


class FakeProvider:
    """Satisfies both BarProvider and QuoteProvider; records all calls."""

    name = "fake"

    def __init__(self, bars=None, quote=None):
        self.bars = bars or []
        self.quote = quote
        self.bar_calls: list[tuple] = []
        self.quote_calls: list[str] = []

    def get_bars(self, symbol, interval, start, end):
        self.bar_calls.append((symbol, interval, start, end))
        return [
            b for b in self.bars
            if b.symbol == symbol and b.interval == interval and start <= b.ts <= end
        ]

    def get_quote(self, symbol):
        self.quote_calls.append(symbol)
        return self.quote
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_providers_base.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/providers/base.py tests/fakes.py tests/test_providers_base.py
git commit -m "feat: provider protocols, CostCapExceeded, test fakes"
```

---

### Task 6: DataService (cache-through core)

**Files:**
- Create: `src/bbterm/data/service.py`
- Test: `tests/test_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_service.py
from datetime import datetime

from bbterm.data.models import Quote
from bbterm.data.service import DataService
from bbterm.data.store import Store
from fakes import FakeProvider, make_bars

START = datetime(2026, 1, 5)
END = datetime(2026, 1, 9)


def make_service(bars=None, quote=None, ttl=0.0):
    store = Store(":memory:")
    fake = FakeProvider(bars=bars or [], quote=quote)
    return DataService(store, fake, fake, fetch_ttl=ttl), fake


async def test_empty_store_fetches_full_range_and_caches():
    svc, fake = make_service(bars=make_bars(start=START, n=5))
    got = await svc.get_bars("AAPL", "1d", START, END)
    assert len(got) == 5
    assert fake.bar_calls == [("AAPL", "1d", START, END)]
    assert svc.store.coverage("AAPL", "1d") == (START, END)


async def test_covered_range_makes_no_provider_call():
    svc, fake = make_service(bars=make_bars(start=START, n=5))
    await svc.get_bars("AAPL", "1d", START, END)
    fake.bar_calls.clear()
    got = await svc.get_bars("AAPL", "1d", START, datetime(2026, 1, 7))
    assert len(got) == 3
    assert fake.bar_calls == []


async def test_forward_gap_fetches_only_the_gap():
    svc, fake = make_service(bars=make_bars(start=START, n=10))
    await svc.get_bars("AAPL", "1d", START, END)  # caches Jan 5-9
    fake.bar_calls.clear()
    later = datetime(2026, 1, 12)
    await svc.get_bars("AAPL", "1d", START, later)
    assert len(fake.bar_calls) == 1
    _, _, gap_start, gap_end = fake.bar_calls[0]
    assert gap_start == datetime(2026, 1, 10)
    assert gap_end == later


async def test_backward_gap_fetches_only_the_gap():
    svc, fake = make_service(bars=make_bars(start=datetime(2026, 1, 1), n=10))
    await svc.get_bars("AAPL", "1d", START, END)  # caches Jan 5-9
    fake.bar_calls.clear()
    earlier = datetime(2026, 1, 2)
    await svc.get_bars("AAPL", "1d", earlier, END)
    assert len(fake.bar_calls) == 1
    _, _, gap_start, gap_end = fake.bar_calls[0]
    assert gap_start == earlier
    assert gap_end == datetime(2026, 1, 4)


async def test_fetch_ttl_suppresses_repeated_forward_fetch():
    svc, fake = make_service(bars=make_bars(start=START, n=5), ttl=300.0)
    await svc.get_bars("AAPL", "1d", START, END)
    fake.bar_calls.clear()
    await svc.get_bars("AAPL", "1d", START, datetime(2026, 1, 12))
    assert fake.bar_calls == []  # within TTL: don't re-ask for newer data


async def test_get_quote_passthrough():
    svc, fake = make_service(quote=Quote("AAPL", 110.0, 100.0))
    q = await svc.get_quote("AAPL")
    assert q.price == 110.0
    assert fake.quote_calls == ["AAPL"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bbterm.data.service'`

- [ ] **Step 3: Write the implementation**

```python
# src/bbterm/data/service.py
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta

from bbterm.data.models import Bar, Quote
from bbterm.data.providers.base import BarProvider, QuoteProvider
from bbterm.data.store import Store

FETCH_TTL_SECONDS = 300.0


def _step(interval: str) -> timedelta:
    return timedelta(days=1) if interval == "1d" else timedelta(minutes=1)


class DataService:
    def __init__(
        self,
        store: Store,
        bar_provider: BarProvider,
        quote_provider: QuoteProvider,
        fetch_ttl: float = FETCH_TTL_SECONDS,
    ) -> None:
        self.store = store
        self._bars = bar_provider
        self._quotes = quote_provider
        self._ttl = fetch_ttl
        self._last_fetch: dict[tuple[str, str], float] = {}

    async def get_bars(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Bar]:
        coverage = self.store.coverage(symbol, interval)
        gaps: list[tuple[datetime, datetime]] = []
        if coverage is None:
            gaps.append((start, end))
        else:
            lo, hi = coverage
            if start < lo:
                gaps.append((start, lo - _step(interval)))
            if end > hi and not self._recently_fetched(symbol, interval):
                gaps.append((hi + _step(interval), end))
        for gap_start, gap_end in gaps:
            fetched = await asyncio.to_thread(
                self._bars.get_bars, symbol, interval, gap_start, gap_end
            )
            self.store.upsert_bars(fetched)
            self._last_fetch[(symbol, interval)] = time.monotonic()
        return self.store.get_bars(symbol, interval, start, end)

    async def get_quote(self, symbol: str) -> Quote | None:
        return await asyncio.to_thread(self._quotes.get_quote, symbol)

    def _recently_fetched(self, symbol: str, interval: str) -> bool:
        if self._ttl <= 0:
            return False
        last = self._last_fetch.get((symbol, interval))
        return last is not None and (time.monotonic() - last) < self._ttl
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_service.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/service.py tests/test_service.py
git commit -m "feat: async cache-through DataService with gap fetching and fetch TTL"
```

---

### Task 7: yfinance provider

**Files:**
- Create: `src/bbterm/data/providers/yfinance_.py`
- Test: `tests/test_yfinance_provider.py`

- [ ] **Step 1: Write the failing test (yfinance fully stubbed — no network)**

```python
# tests/test_yfinance_provider.py
from datetime import datetime
from types import SimpleNamespace

import pandas as pd

import bbterm.data.providers.yfinance_ as yfp
from bbterm.data.providers.yfinance_ import YFinanceProvider


class StubTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_info = SimpleNamespace(last_price=110.0, previous_close=100.0)

    def history(self, start=None, end=None, interval=None):
        idx = pd.to_datetime([datetime(2026, 1, 5), datetime(2026, 1, 6)])
        return pd.DataFrame(
            {
                "Open": [1.0, 2.0],
                "High": [1.5, 2.5],
                "Low": [0.5, 1.5],
                "Close": [1.2, 2.2],
                "Volume": [100, 200],
            },
            index=idx,
        )


def test_get_bars_maps_dataframe(monkeypatch):
    monkeypatch.setattr(yfp.yf, "Ticker", StubTicker)
    bars = YFinanceProvider().get_bars(
        "AAPL", "1d", datetime(2026, 1, 1), datetime(2026, 1, 31)
    )
    assert len(bars) == 2
    assert bars[0].symbol == "AAPL"
    assert bars[0].interval == "1d"
    assert bars[0].close == 1.2
    assert bars[1].volume == 200
    assert bars[0].ts == datetime(2026, 1, 5)


def test_get_quote_maps_fast_info(monkeypatch):
    monkeypatch.setattr(yfp.yf, "Ticker", StubTicker)
    q = YFinanceProvider().get_quote("AAPL")
    assert q.price == 110.0
    assert q.prev_close == 100.0


def test_errors_degrade_to_empty(monkeypatch):
    def boom(symbol):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(yfp.yf, "Ticker", boom)
    p = YFinanceProvider()
    assert p.get_bars("AAPL", "1d", datetime(2026, 1, 1), datetime(2026, 1, 2)) == []
    assert p.get_quote("AAPL") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_yfinance_provider.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bbterm/data/providers/yfinance_.py
from __future__ import annotations

from datetime import datetime

import yfinance as yf

from bbterm.data.models import Bar, Quote

_YF_INTERVAL = {"1d": "1d", "1m": "1m"}


class YFinanceProvider:
    """Dev/fallback provider. Unofficial Yahoo data — not for commercial use."""

    name = "yfinance"

    def get_bars(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Bar]:
        try:
            df = yf.Ticker(symbol).history(
                start=start, end=end, interval=_YF_INTERVAL[interval]
            )
        except Exception:
            return []
        bars: list[Bar] = []
        for ts, row in df.iterrows():
            naive = ts.to_pydatetime().replace(tzinfo=None)
            bars.append(
                Bar(
                    symbol, interval, naive,
                    float(row["Open"]), float(row["High"]),
                    float(row["Low"]), float(row["Close"]), int(row["Volume"]),
                )
            )
        return bars

    def get_quote(self, symbol: str) -> Quote | None:
        try:
            fast = yf.Ticker(symbol).fast_info
            price, prev = fast.last_price, fast.previous_close
            if price is None or prev is None:
                return None
            return Quote(symbol=symbol, price=float(price), prev_close=float(prev))
        except Exception:
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_yfinance_provider.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/providers/yfinance_.py tests/test_yfinance_provider.py
git commit -m "feat: yfinance fallback provider"
```

---

### Task 8: Service factory (Phase 1 version)

**Files:**
- Modify: `src/bbterm/data/__init__.py`
- Test: `tests/test_factory.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_factory.py
from bbterm.config import Config
from bbterm.data import build_service


def _config(tmp_path, key=None):
    return Config(
        databento_api_key=key,
        db_path=tmp_path / "m.duckdb",
        cost_cap_usd=1.0,
        databento_dataset="EQUS.MINI",
    )


def test_no_key_uses_yfinance_for_bars(tmp_path):
    svc = build_service(_config(tmp_path))
    assert svc._bars.name == "yfinance"
    assert svc._quotes.name == "yfinance"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_factory.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_service'`

- [ ] **Step 3: Write the implementation**

```python
# src/bbterm/data/__init__.py
from __future__ import annotations

from bbterm.config import Config
from bbterm.data.providers.yfinance_ import YFinanceProvider
from bbterm.data.service import DataService
from bbterm.data.store import Store


def build_service(config: Config) -> DataService:
    store = Store(config.db_path)
    yf_provider = YFinanceProvider()
    return DataService(store, yf_provider, yf_provider)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_factory.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/__init__.py tests/test_factory.py
git commit -m "feat: build_service factory (yfinance-only, Databento wired in later)"
```

---

### Task 9: Async TUI

**Files:**
- Create: `src/bbterm/tui/app.py`, `src/bbterm/tui/widgets/watchlist.py`, `src/bbterm/tui/widgets/chart.py`, `src/bbterm/tui/widgets/strip.py`
- Test: `tests/test_app.py`

Widgets are dumb renderers: each exposes `show(...)` and never fetches. All fetching happens in `App` workers.

- [ ] **Step 1: Write the widgets**

```python
# src/bbterm/tui/widgets/strip.py
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label

from bbterm.data.models import Quote


class TickerStrip(Widget):
    DEFAULT_CSS = """
    TickerStrip { height: 1; background: $boost; dock: bottom; }
    TickerStrip Label { width: 100%; }
    """

    def compose(self) -> ComposeResult:
        yield Label("", id="strip-label")

    def show(self, quotes: list[Quote]) -> None:
        text = Text()
        for i, q in enumerate(quotes):
            if i > 0:
                text.append("  |  ", style="dim")
            color = "green" if q.is_up else "red"
            sign = "+" if q.is_up else ""
            text.append(f"{q.symbol} ", style="bold white")
            text.append(f"{q.price:.2f} ", style=f"bold {color}")
            text.append(f"{sign}{q.pct_change:.2f}%", style=color)
        self.query_one("#strip-label", Label).update(text)
```

```python
# src/bbterm/tui/widgets/watchlist.py
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView

from bbterm.data.models import Quote


def _render_quote(q: Quote) -> Text:
    text = Text()
    text.append(f"{q.symbol:<8}", style="bold white")
    color = "green" if q.is_up else "red"
    text.append(f"{q.price:>10.2f}", style=f"bold {color}")
    sign = "+" if q.is_up else ""
    text.append(f"\n  {sign}{q.pct_change:.2f}%", style=color)
    return text


class WatchlistItem(ListItem):
    def __init__(self, quote: Quote) -> None:
        super().__init__()
        self.quote = quote

    def compose(self) -> ComposeResult:
        yield Label(_render_quote(self.quote))

    def update_quote(self, quote: Quote) -> None:
        self.quote = quote
        self.query_one(Label).update(_render_quote(quote))


class Watchlist(Widget):
    class TickerSelected(Message):
        def __init__(self, symbol: str) -> None:
            super().__init__()
            self.symbol = symbol

    DEFAULT_CSS = """
    Watchlist { width: 20; border-right: solid $primary; }
    Watchlist > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    Watchlist ListView { background: $surface; }
    Watchlist ListItem { padding: 0 1; height: 3; }
    Watchlist ListItem.--highlight { background: $accent 30%; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._items: dict[str, WatchlistItem] = {}

    def compose(self) -> ComposeResult:
        yield Label("WATCHLIST", classes="header")
        yield ListView()

    def show(self, quotes: list[Quote]) -> None:
        symbols = [q.symbol for q in quotes]
        if symbols != list(self._items.keys()):
            list_view = self.query_one(ListView)
            list_view.clear()
            self._items.clear()
            for q in quotes:
                item = WatchlistItem(q)
                self._items[q.symbol] = item
                list_view.append(item)
        else:
            for q in quotes:
                self._items[q.symbol].update_quote(q)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, WatchlistItem):
            self.post_message(self.TickerSelected(event.item.quote.symbol))
```

```python
# src/bbterm/tui/widgets/chart.py
from __future__ import annotations

import plotext as plt
from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from bbterm.data.models import Bar, Quote


class ChartPanel(Widget):
    DEFAULT_CSS = """
    ChartPanel { height: 1fr; }
    ChartPanel > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    ChartPanel > Static.plot { width: 100%; height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Label("", id="chart-header", classes="header")
        yield Static("", id="chart-plot", classes="plot")

    def show(
        self,
        symbol: str,
        period_label: str,
        bars: list[Bar],
        quote: Quote | None,
    ) -> None:
        header = self.query_one("#chart-header", Label)
        plot = self.query_one("#chart-plot", Static)

        if quote:
            color = "green" if quote.is_up else "red"
            text = Text()
            text.append(f"  {symbol}  ", style="bold white on black")
            text.append(f"  {quote.price:.2f}  ", style=f"bold {color}")
            text.append(f"  {quote.change_str}  ", style=color)
            header.update(text)
        else:
            header.update(f"  {symbol}")

        if not bars:
            plot.update("  No data available for this symbol/period.")
            return
        plot.update(self._render(symbol, period_label, bars, quote))

    def _render(
        self,
        symbol: str,
        period_label: str,
        bars: list[Bar],
        quote: Quote | None,
    ) -> str:
        width = max(self.size.width - 2, 40)
        height = max(self.size.height - 3, 10)

        closes = [b.close for b in bars]
        labels = [str(b.ts.date()) for b in bars]

        plt.clear_figure()
        plt.theme("dark")
        plt.plotsize(width, height)
        color = "green" if (quote and quote.is_up) else "red"
        plt.plot(closes, color=color, label=symbol)

        tick_count = min(6, len(labels))
        step = max(1, len(labels) // tick_count)
        ticks = list(range(0, len(labels), step))
        plt.xticks(ticks, [labels[i] for i in ticks])
        plt.title(f"{symbol} — {period_label}")
        return plt.build()
```

- [ ] **Step 2: Write the app**

```python
# src/bbterm/tui/app.py
from __future__ import annotations

from datetime import datetime, timedelta

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header

from bbterm.config import load_config
from bbterm.data import build_service
from bbterm.data.providers.base import CostCapExceeded
from bbterm.data.service import DataService
from bbterm.tui.widgets.chart import ChartPanel
from bbterm.tui.widgets.strip import TickerStrip
from bbterm.tui.widgets.watchlist import Watchlist

PERIODS: dict[str, tuple[str, timedelta, str]] = {
    "1d": ("1 Day", timedelta(days=1), "1m"),
    "5d": ("5 Days", timedelta(days=5), "1m"),
    "1mo": ("1 Month", timedelta(days=30), "1d"),
    "6mo": ("6 Months", timedelta(days=182), "1d"),
    "1y": ("1 Year", timedelta(days=365), "1d"),
    "5y": ("5 Years", timedelta(days=5 * 365), "1d"),
}


class BloombergApp(App):
    TITLE = "bbterm"
    CSS = """
    Screen { background: $surface; }
    #main { height: 1fr; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("1", "period('1d')", "1D"),
        Binding("2", "period('5d')", "5D"),
        Binding("3", "period('1mo')", "1M"),
        Binding("4", "period('6mo')", "6M"),
        Binding("5", "period('1y')", "1Y"),
        Binding("6", "period('5y')", "5Y"),
    ]

    def __init__(
        self,
        service: DataService | None = None,
        watchlist: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.service = service or build_service(load_config())
        self.watchlist_symbols = watchlist or self.service.store.get_watchlist()
        self.current_symbol = self.watchlist_symbols[0]
        self.current_period = "1mo"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield Watchlist()
            yield ChartPanel()
        yield TickerStrip()
        yield Footer()

    def on_mount(self) -> None:
        self.load_chart()
        self.load_quotes()
        self.set_interval(60, self.load_quotes)

    def on_watchlist_ticker_selected(
        self, message: Watchlist.TickerSelected
    ) -> None:
        self.current_symbol = message.symbol
        self.load_chart()

    def action_refresh(self) -> None:
        self.load_chart()
        self.load_quotes()

    def action_period(self, period: str) -> None:
        self.current_period = period
        self.load_chart()

    @work(exclusive=True, group="chart")
    async def load_chart(self) -> None:
        label, delta, interval = PERIODS[self.current_period]
        end = datetime.now()
        start = end - delta
        try:
            bars = await self.service.get_bars(
                self.current_symbol, interval, start, end
            )
        except CostCapExceeded as err:
            self.notify(str(err), severity="error", title="Cost cap")
            return
        quote = await self.service.get_quote(self.current_symbol)
        self.query_one(ChartPanel).show(self.current_symbol, label, bars, quote)

    @work(exclusive=True, group="quotes")
    async def load_quotes(self) -> None:
        quotes = []
        for symbol in self.watchlist_symbols:
            quote = await self.service.get_quote(symbol)
            if quote:
                quotes.append(quote)
        self.query_one(Watchlist).show(quotes)
        self.query_one(TickerStrip).show(quotes)


def main() -> None:
    BloombergApp().run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write the smoke test (fake service, no network)**

```python
# tests/test_app.py
from datetime import datetime, timedelta

from bbterm.data.models import Quote
from bbterm.data.service import DataService
from bbterm.data.store import Store
from bbterm.tui.app import BloombergApp
from bbterm.tui.widgets.chart import ChartPanel
from fakes import FakeProvider, make_bars


async def test_app_boots_and_renders_with_fake_data():
    bars = make_bars(
        "SPY", "1d", start=datetime.now() - timedelta(days=20), n=15
    )
    fake = FakeProvider(bars=bars, quote=Quote("SPY", 101.0, 100.0))
    service = DataService(Store(":memory:"), fake, fake, fetch_ttl=0.0)
    app = BloombergApp(service=service, watchlist=["SPY"])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(ChartPanel) is not None
        assert len(fake.quote_calls) >= 1
        assert len(fake.bar_calls) >= 1
```

- [ ] **Step 4: Run the test suite**

Run: `.venv/bin/python -m pytest -v`
Expected: all tests pass (models, config, store, providers, service, factory, app).

- [ ] **Step 5: Manual smoke run**

Run: `.venv/bin/bbterm` in a real terminal (uses yfinance — needs network).
Expected: app starts instantly showing layout; watchlist and chart fill in asynchronously without freezing; keys 1–6 switch periods; `q` quits. Second launch of the same chart period loads from DuckDB without delay.

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/tui/ tests/test_app.py
git commit -m "feat: async TUI on DataService — UI never blocks on network"
```

---

### Task 10: Remove old code (Phase 1 parity checkpoint)

**Files:**
- Delete: `terminal/`, `main.py`, `requirements.txt`

- [ ] **Step 1: Delete superseded files**

```bash
git rm -r terminal/ main.py requirements.txt
```

- [ ] **Step 2: Verify nothing references them and the suite passes**

Run: `grep -rn "from terminal" src/ tests/ ; .venv/bin/python -m pytest`
Expected: grep finds nothing; all tests pass.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove yfinance-era prototype, superseded by bbterm package"
```

---

### Task 11: Verify Databento dataset and record costs (free metadata calls)

No files — this resolves the one external unknown (exact dataset name) before writing the provider. All metadata endpoints are free.

- [ ] **Step 1: List equities datasets and quote real costs**

```bash
source ~/.zshrc && .venv/bin/python - <<'EOF'
import os
import databento as db

client = db.Historical(os.environ["DATABENTO_API_KEY"])
datasets = client.metadata.list_datasets()
print("equities datasets:", [d for d in datasets if "EQUS" in d or "DBEQ" in d])

candidate = "EQUS.MINI" if "EQUS.MINI" in datasets else "DBEQ.BASIC"
for schema, start in [("ohlcv-1d", "2025-06-01"), ("ohlcv-1m", "2026-06-08")]:
    cost = client.metadata.get_cost(
        dataset=candidate, symbols=["AAPL"], schema=schema,
        start=start, end="2026-06-11",
    )
    print(f"{candidate} {schema} AAPL since {start}: ${cost:.6f}")
EOF
```

Expected: a dataset list containing `EQUS.MINI` and/or `DBEQ.BASIC`; daily-bar cost for a year well under $0.01; a few days of 1-minute bars in the cents at most.

- [ ] **Step 2: Act on the result**

- If `EQUS.MINI` is unavailable, change the default in `src/bbterm/config.py` (`BBTERM_DATASET` fallback) and `tests/test_config.py` to the available dataset, run `.venv/bin/python -m pytest tests/test_config.py`, and commit as `fix: use <dataset> as default Databento dataset`.
- Record the printed costs in the commit message or plan notes — they validate the $1 default cap is generous.

---

### Task 12: Databento provider with cost guardrail

**Files:**
- Create: `src/bbterm/data/providers/databento_.py`
- Test: `tests/test_databento_provider.py`

- [ ] **Step 1: Write the failing tests (fake client injected — no network, no credits)**

```python
# tests/test_databento_provider.py
from datetime import datetime

import pandas as pd
import pytest

from bbterm.data.providers.base import CostCapExceeded
from bbterm.data.providers.databento_ import DatabentoProvider


class FakeStoreResult:
    def __init__(self, df):
        self._df = df

    def to_df(self):
        return self._df


class FakeDbClient:
    def __init__(self, cost=0.001, df=None):
        self._cost = cost
        self._df = df if df is not None else pd.DataFrame()
        self.cost_calls = []
        self.range_calls = []
        self.metadata = self
        self.timeseries = self

    def get_cost(self, **kwargs):
        self.cost_calls.append(kwargs)
        return self._cost

    def get_range(self, **kwargs):
        self.range_calls.append(kwargs)
        return FakeStoreResult(self._df)


def _df():
    idx = pd.to_datetime([datetime(2026, 1, 5), datetime(2026, 1, 6)])
    return pd.DataFrame(
        {
            "open": [1.0, 2.0],
            "high": [1.5, 2.5],
            "low": [0.5, 1.5],
            "close": [1.2, 2.2],
            "volume": [100, 200],
        },
        index=idx,
    )


def test_get_bars_checks_cost_then_fetches():
    client = FakeDbClient(cost=0.001, df=_df())
    provider = DatabentoProvider(
        api_key="db-x", dataset="EQUS.MINI", cost_cap_usd=1.0, client=client
    )
    bars = provider.get_bars(
        "AAPL", "1d", datetime(2026, 1, 1), datetime(2026, 1, 31)
    )
    assert len(client.cost_calls) == 1
    assert client.cost_calls[0]["schema"] == "ohlcv-1d"
    assert len(bars) == 2
    assert bars[0].close == 1.2
    assert bars[1].volume == 200
    assert bars[0].ts == datetime(2026, 1, 5)


def test_cost_above_cap_raises_without_fetching():
    client = FakeDbClient(cost=5.0, df=_df())
    provider = DatabentoProvider(
        api_key="db-x", dataset="EQUS.MINI", cost_cap_usd=1.0, client=client
    )
    with pytest.raises(CostCapExceeded) as exc:
        provider.get_bars("AAPL", "1d", datetime(2020, 1, 1), datetime(2026, 1, 1))
    assert exc.value.estimated_usd == 5.0
    assert client.range_calls == []


def test_minute_interval_uses_minute_schema():
    client = FakeDbClient(cost=0.001, df=_df())
    provider = DatabentoProvider(
        api_key="db-x", dataset="EQUS.MINI", cost_cap_usd=1.0, client=client
    )
    provider.get_bars("AAPL", "1m", datetime(2026, 1, 5), datetime(2026, 1, 6))
    assert client.cost_calls[0]["schema"] == "ohlcv-1m"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_databento_provider.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bbterm/data/providers/databento_.py
from __future__ import annotations

from datetime import datetime

import databento as db

from bbterm.data.models import Bar
from bbterm.data.providers.base import CostCapExceeded

_SCHEMA = {"1d": "ohlcv-1d", "1m": "ohlcv-1m"}


class DatabentoProvider:
    name = "databento"

    def __init__(
        self,
        api_key: str,
        dataset: str,
        cost_cap_usd: float,
        client: db.Historical | None = None,
    ) -> None:
        self._client = client or db.Historical(api_key)
        self._dataset = dataset
        self._cap = cost_cap_usd

    def get_bars(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Bar]:
        schema = _SCHEMA[interval]
        cost = float(
            self._client.metadata.get_cost(
                dataset=self._dataset, symbols=[symbol], schema=schema,
                start=start, end=end,
            )
        )
        if cost > self._cap:
            raise CostCapExceeded(cost, self._cap)
        result = self._client.timeseries.get_range(
            dataset=self._dataset, symbols=[symbol], schema=schema,
            start=start, end=end,
        )
        df = result.to_df()
        bars: list[Bar] = []
        for ts, row in df.iterrows():
            naive = ts.to_pydatetime().replace(tzinfo=None)
            bars.append(
                Bar(
                    symbol, interval, naive,
                    float(row["open"]), float(row["high"]),
                    float(row["low"]), float(row["close"]), int(row["volume"]),
                )
            )
        return bars
```

(Implementation note: if the live API rejects naive datetimes, format them as ISO date strings — `start.date().isoformat()` — at the two call sites; the tests don't constrain that.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_databento_provider.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/bbterm/data/providers/databento_.py tests/test_databento_provider.py
git commit -m "feat: Databento historical provider with pre-flight cost cap"
```

---

### Task 13: Wire Databento into the factory + live smoke test

**Files:**
- Modify: `src/bbterm/data/__init__.py`
- Modify: `tests/test_factory.py`

- [ ] **Step 1: Add the failing test**

```python
# append to tests/test_factory.py
def test_key_present_uses_databento_for_bars(tmp_path):
    svc = build_service(_config(tmp_path, key="db-test-key"))
    assert svc._bars.name == "databento"
    assert svc._quotes.name == "yfinance"  # quotes stay on free fallback
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_factory.py -v`
Expected: new test FAILS (`_bars.name == "yfinance"`), first test still passes.

- [ ] **Step 3: Update the factory**

```python
# src/bbterm/data/__init__.py
from __future__ import annotations

from bbterm.config import Config
from bbterm.data.providers.databento_ import DatabentoProvider
from bbterm.data.providers.yfinance_ import YFinanceProvider
from bbterm.data.service import DataService
from bbterm.data.store import Store


def build_service(config: Config) -> DataService:
    store = Store(config.db_path)
    yf_provider = YFinanceProvider()
    if config.databento_api_key:
        bars = DatabentoProvider(
            api_key=config.databento_api_key,
            dataset=config.databento_dataset,
            cost_cap_usd=config.cost_cap_usd,
        )
        return DataService(store, bars, yf_provider)
    return DataService(store, yf_provider, yf_provider)
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 5: Live smoke test (spends a fraction of a cent, prints cost first)**

```bash
source ~/.zshrc && .venv/bin/python - <<'EOF'
import asyncio
from datetime import datetime, timedelta
from bbterm.config import load_config
from bbterm.data import build_service

cfg = load_config()
svc = build_service(cfg)
print("bars provider:", svc._bars.name)
end = datetime.now()
bars = asyncio.run(svc.get_bars("AAPL", "1d", end - timedelta(days=30), end))
print(f"fetched {len(bars)} daily bars; last close: {bars[-1].close if bars else 'n/a'}")
bars2 = asyncio.run(svc.get_bars("AAPL", "1d", end - timedelta(days=30), end))
print("second call served from cache:", len(bars2), "bars")
EOF
```

Expected: provider is `databento`; ~20 daily bars; second call returns the same bars with no additional spend (TTL suppresses refetch). Then run `.venv/bin/bbterm` and confirm charts render from Databento data.

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/data/__init__.py tests/test_factory.py
git commit -m "feat: use Databento for bars when API key present"
```

---

### Task 14: Graceful degradation to cache + end-of-day sync command

**Files:**
- Modify: `src/bbterm/tui/app.py` (the `load_chart` worker)
- Create: `src/bbterm/sync.py`
- Modify: `pyproject.toml` (add `bbterm-sync` script)
- Test: `tests/test_sync.py`

- [ ] **Step 1: Make `load_chart` fall back to cached bars on provider failure**

Replace the `try/except` block inside `load_chart` in `src/bbterm/tui/app.py` with:

```python
        try:
            bars = await self.service.get_bars(
                self.current_symbol, interval, start, end
            )
        except CostCapExceeded as err:
            self.notify(str(err), severity="error", title="Cost cap")
            bars = self.service.store.get_bars(
                self.current_symbol, interval, start, end
            )
        except Exception as err:
            self.notify(
                f"Fetch failed ({err}); showing cached data",
                severity="warning", title="Stale data",
            )
            bars = self.service.store.get_bars(
                self.current_symbol, interval, start, end
            )
```

- [ ] **Step 2: Write the failing sync test**

```python
# tests/test_sync.py
from bbterm.data.service import DataService
from bbterm.data.store import Store
from bbterm.sync import sync_watchlist
from fakes import FakeProvider, make_bars
from datetime import datetime, timedelta


async def test_sync_fetches_daily_bars_for_every_watchlist_symbol():
    store = Store(":memory:")
    store.set_watchlist(["AAPL", "MSFT"])
    start = datetime.now() - timedelta(days=10)
    bars = make_bars("AAPL", "1d", start=start, n=5) + make_bars(
        "MSFT", "1d", start=start, n=5
    )
    fake = FakeProvider(bars=bars)
    service = DataService(store, fake, fake, fetch_ttl=0.0)

    counts = await sync_watchlist(service, days=365)

    assert set(counts) == {"AAPL", "MSFT"}
    assert counts["AAPL"] == 5
    assert {c[0] for c in fake.bar_calls} == {"AAPL", "MSFT"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bbterm.sync'`

- [ ] **Step 4: Write the implementation**

```python
# src/bbterm/sync.py
"""End-of-day sync: pull daily bars for the whole watchlist into DuckDB.

Run after market close (or any time): `bbterm-sync`
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from bbterm.config import load_config
from bbterm.data import build_service
from bbterm.data.providers.base import CostCapExceeded
from bbterm.data.service import DataService


async def sync_watchlist(service: DataService, days: int = 365) -> dict[str, int]:
    end = datetime.now()
    start = end - timedelta(days=days)
    counts: dict[str, int] = {}
    for symbol in service.store.get_watchlist():
        bars = await service.get_bars(symbol, "1d", start, end)
        counts[symbol] = len(bars)
    return counts


def main() -> None:
    service = build_service(load_config())
    try:
        counts = asyncio.run(sync_watchlist(service))
    except CostCapExceeded as err:
        raise SystemExit(f"aborted: {err}")
    for symbol, n in counts.items():
        print(f"{symbol}: {n} daily bars cached")


if __name__ == "__main__":
    main()
```

And add to `pyproject.toml` under `[project.scripts]`:

```toml
bbterm-sync = "bbterm.sync:main"
```

Then reinstall entry points: `.venv/bin/pip install -e ".[dev]" --quiet`

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/bbterm/sync.py tests/test_sync.py src/bbterm/tui/app.py pyproject.toml
git commit -m "feat: bbterm-sync EOD command; chart degrades to cached bars on fetch failure"
```

---

## Done criteria (maps to spec)

- UI never blocks: all fetching in workers / `to_thread` (Tasks 6, 9).
- Each Databento record paid once: cache-through + gap fetching + TTL (Task 6), verified live (Task 13 Step 5).
- Cost guardrail: pre-flight `get_cost` with configurable cap, surfaced via `notify` (Tasks 12, 9).
- Missing key → fallback mode (Task 13 factory branch).
- Provider failure degrades to cached data with a visible warning; EOD sync command fills the cache (Task 14).
- yfinance isolated behind protocol, deletable (Task 7).
- No credits spent by the test suite — only Task 13 Step 5 spends, knowingly (~$0.001).

Phase 3 (command bar, candlesticks, watchlist editing) is a separate plan, written after this one ships.
