from bbterm.data.stats import Stats
from bbterm.tui.widgets.stats import format_volume, render_stats_text


def test_format_volume_humanizes():
    assert format_volume(58_300_000) == "58.3M"
    assert format_volume(1_500) == "1.5K"
    assert format_volume(950) == "950"


def test_render_handles_none_fields():
    s = Stats("AAPL", 291.52, None, None, 342.1, 201.45,
              None, None, 58_300_000, 289.0, 296.4)
    text = render_stats_text(s)
    assert "AAPL" in text
    assert "n/a" in text          # change/ret_1m/ret_ytd are None
    assert "342.10" in text       # 52w high formatted
    assert "58.3M" in text
