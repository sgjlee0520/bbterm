import json
from datetime import date
from pathlib import Path

from bbterm.data.fundamentals import extract_fundamentals, parse_filings

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text())


def test_extract_returns_known_metrics_only():
    metrics = {m.label: m for m in extract_fundamentals(_load("companyfacts_sample.json"))}
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
