from datetime import timezone

from bbterm.data.news import parse_news

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>"AAPL" stock - Google News</title>
<item><title>Apple hits record high - Reuters</title>
<link>https://example.com/a</link>
<pubDate>Wed, 18 Jun 2025 14:30:00 GMT</pubDate>
<source url="https://reuters.com">Reuters</source></item>
<item><title>Apple announces buyback - Bloomberg</title>
<link>https://example.com/b</link>
<pubDate>Tue, 17 Jun 2025 09:00:00 GMT</pubDate>
<source url="https://bloomberg.com">Bloomberg</source></item>
</channel></rss>"""


def test_parse_news_extracts_items():
    items = parse_news(RSS)
    assert len(items) == 2
    assert items[0].source == "Reuters"
    assert items[0].url == "https://example.com/a"
    assert items[0].published.tzinfo is not None


def test_parse_news_strips_source_suffix_from_title():
    items = parse_news(RSS)
    assert items[0].title == "Apple hits record high"  # " - Reuters" removed


def test_parse_news_orders_newest_first():
    items = parse_news(RSS)
    assert items[0].published > items[1].published


def test_parse_news_respects_limit():
    assert len(parse_news(RSS, limit=1)) == 1


def test_parse_news_malformed_returns_empty():
    assert parse_news(b"<not-valid") == []
