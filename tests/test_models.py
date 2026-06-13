from datetime import datetime
from bbterm.data.models import Bar, Quote


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
