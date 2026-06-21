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
