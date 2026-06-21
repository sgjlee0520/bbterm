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
    import json
    store = Store(":memory:")
    store._con.execute(
        "INSERT OR REPLACE INTO congress_trades VALUES (?, ?, ?)",
        ["NVDA", datetime.now() - timedelta(days=2), json.dumps(PAYLOAD)],
    )
    cg = FakeCongress(fail=True)
    svc = DataService(store, None, None, congress_provider=cg)
    trades = await svc.get_congress_trades("NVDA")
    assert cg.calls == 1 and [t.politician for t in trades] == ["Gilbert Cisneros"]
