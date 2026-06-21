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


def test_build_candle_output_nonempty():
    panel = ChartPanel()
    panel._size_wh = (80, 24)  # avoid depending on a mounted layout
    out = panel._build_plot("AAPL", "1 Month", _bars(), Quote("AAPL", 110, 100))
    assert isinstance(out, str) and out.strip() != ""


def test_show_uses_text_when_images_unavailable(monkeypatch):
    import bbterm.tui.widgets.chart as chart_mod

    monkeypatch.setattr(chart_mod, "image_charts_available", lambda: False)
    panel = ChartPanel()
    panel._size_wh = (80, 24)
    # _render_candle returns None (text path) when images are unavailable
    out = panel._render_candle("AAPL", "1 Month", _bars(), Quote("AAPL", 110, 100))
    assert out is None
