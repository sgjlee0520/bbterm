from bbterm.data.magic_formula import rank_magic
from bbterm.data.models import MagicMetrics
from bbterm.tui.widgets.magic import render_magic_text


def test_render_shows_current_and_ranking():
    a = MagicMetrics("AAPL", 0.08, 0.40, 3.1e12)
    b = MagicMetrics("MSFT", 0.05, 0.30, 2.5e12)
    out = render_magic_text("AAPL", a, rank_magic([a, b]), ["SPY"])
    assert "AAPL" in out and "8.0%" in out and "40.0%" in out
    assert "MSFT" in out
    assert "Not computable: SPY" in out


def test_render_not_computable_current():
    out = render_magic_text("SPY", None, [], ["SPY"])
    assert "not computable" in out.lower()
