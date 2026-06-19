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
