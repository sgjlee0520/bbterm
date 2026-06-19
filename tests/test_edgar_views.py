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
                          date(2023, 9, 30), 2023, "FY", 4.78),
        FundamentalMetric("EPS (diluted)", 6.13, "USD/shares",
                          date(2023, 9, 30), 2023, "FY", None),
    ]
    text = render_fundamentals_text(metrics)
    assert "Revenue" in text
    assert "$383.29B" in text
    assert "FY2023" in text
    assert "+4.78%" in text
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
