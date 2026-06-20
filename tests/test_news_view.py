from datetime import datetime, timezone

from bbterm.data.models import NewsItem
from bbterm.tui.widgets.news import _relative_age, render_news_text

NOW = datetime(2025, 6, 18, 15, 0, tzinfo=timezone.utc)


def test_relative_age():
    assert _relative_age(datetime(2025, 6, 18, 14, 0, tzinfo=timezone.utc), NOW) == "1h ago"
    assert _relative_age(datetime(2025, 6, 16, 15, 0, tzinfo=timezone.utc), NOW) == "2d ago"
    assert _relative_age(None, NOW) == "—"


def test_render_news_text():
    items = [NewsItem("Apple up", "Reuters",
                      datetime(2025, 6, 18, 14, 0, tzinfo=timezone.utc), "http://x/a")]
    out = render_news_text(items, now=NOW)
    assert "Apple up" in out and "Reuters" in out
    assert "1h ago" in out and "http://x/a" in out


def test_render_news_text_empty():
    assert "No news" in render_news_text([])
