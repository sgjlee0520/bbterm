from datetime import datetime, timedelta

from bbterm.data.models import Bar, Quote
from bbterm.tui.widgets.chart import ChartPanel


def _bars(n=10):
    base = datetime(2026, 1, 2)
    return [
        Bar("AAPL", "1d", base + timedelta(days=i),
            100 + i, 101 + i, 99 + i, 100.5 + i, 1_000_000 + i)
        for i in range(n)
    ]


def test_default_mode_is_candle():
    assert ChartPanel().mode == "candle"


def test_build_candle_output_nonempty():
    panel = ChartPanel()
    panel._size_wh = (80, 24)  # avoid depending on a mounted layout
    out = panel._build_plot("AAPL", "1 Month", _bars(), Quote("AAPL", 110, 100))
    assert isinstance(out, str) and out.strip() != ""


def test_build_line_output_nonempty():
    panel = ChartPanel()
    panel.mode = "line"
    panel._size_wh = (80, 24)
    out = panel._build_plot("AAPL", "1 Month", _bars(), None)
    assert isinstance(out, str) and out.strip() != ""


def test_toggle_mode_flips():
    panel = ChartPanel()
    assert panel.mode == "candle"
    panel.toggle_mode()
    assert panel.mode == "line"
    panel.toggle_mode()
    assert panel.mode == "candle"
