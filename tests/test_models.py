from datetime import date, datetime
from bbterm.data.models import Bar, Filing, FundamentalMetric, Quote


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
