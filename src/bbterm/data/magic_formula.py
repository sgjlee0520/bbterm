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
