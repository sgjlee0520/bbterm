import urllib.parse

from bbterm.data.providers.news import NewsProvider


def test_get_news_builds_google_news_url():
    captured = {}

    def fake_open(url, ua):
        captured["url"] = url
        return b"<rss></rss>"

    NewsProvider(opener=fake_open).get_news("AAPL")
    assert "news.google.com/rss/search" in captured["url"]
    assert "AAPL" in urllib.parse.unquote(captured["url"])


def test_env_override_feed_url(monkeypatch):
    monkeypatch.setenv("BBTERM_NEWS_FEED_URL", "https://example.com/feed?q={query}")
    captured = {}

    def fake_open(url, ua):
        captured["url"] = url
        return b""

    NewsProvider(opener=fake_open).get_news("TSLA")
    assert captured["url"].startswith("https://example.com/feed?q=")
    assert "TSLA" in urllib.parse.unquote(captured["url"])
