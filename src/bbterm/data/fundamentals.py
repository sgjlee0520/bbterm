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
