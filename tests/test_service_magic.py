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
