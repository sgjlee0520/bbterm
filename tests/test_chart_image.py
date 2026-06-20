from datetime import datetime, timedelta

from bbterm.data.models import Bar
from bbterm.tui.widgets.chart_image import image_charts_available, render_candles_png

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _bars(n=20):
    base = datetime(2026, 1, 2)
    return [
        Bar("AAPL", "1d", base + timedelta(days=i),
            100 + i, 101 + i, 99 + i, 100.5 + i, 1_000_000 + i)
        for i in range(n)
    ]


def test_render_candles_png_returns_png_bytes():
    data = render_candles_png(_bars(), "AAPL", "1 Month")
    assert data[:8] == _PNG_SIG
    assert len(data) > 1000


def test_image_charts_available_returns_bool():
    # In the headless test environment this is False; just assert it is a bool
    # and does not raise.
    assert isinstance(image_charts_available(), bool)
