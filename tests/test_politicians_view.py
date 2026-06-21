from datetime import date

from bbterm.data.models import CongressTrade
from bbterm.tui.widgets.politicians import render_politicians_text


def _t(side, lo, hi, d):
    return CongressTrade("Gilbert Cisneros", "house", side, lo, hi, date.fromisoformat(d))


def test_render_shows_summary_and_rows():
    trades = [_t("BUY", 15001, 50000, "2025-11-18"), _t("BUY", 1001, 15000, "2025-10-17")]
    out = render_politicians_text(trades)
    assert "Gilbert Cisneros" in out
    assert "2 buys" in out and "0 sells" in out
    assert "BUY" in out and "2025-11-18" in out


def test_render_no_key_notice():
    assert "LAMBDA_API_KEY" in render_politicians_text([], has_key=False)


def test_render_empty_with_key():
    out = render_politicians_text([], has_key=True)
    assert "No congressional trades" in out
