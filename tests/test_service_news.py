from datetime import datetime, timedelta

from bbterm.data.service import DataService
from bbterm.data.store import Store

RSS = (
    b'<?xml version="1.0"?><rss version="2.0"><channel>'
    b"<item><title>Apple up - Reuters</title><link>http://x/a</link>"
    b"<pubDate>Wed, 18 Jun 2025 14:30:00 GMT</pubDate>"
    b'<source url="http://r">Reuters</source></item></channel></rss>'
)


class FakeNews:
    name = "news"

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def get_news(self, symbol):
        self.calls += 1
        if self.fail:
            raise RuntimeError("boom")
        return RSS


async def test_get_news_fetches_parses_and_caches():
    news = FakeNews()
    svc = DataService(Store(":memory:"), None, None, news_provider=news)
    items = await svc.get_news("AAPL")
    assert items and items[0].title == "Apple up" and items[0].source == "Reuters"
    await svc.get_news("AAPL")          # fresh cache -> no refetch
    assert news.calls == 1


async def test_get_news_degrades_to_stale_cache_on_failure():
    store = Store(":memory:")
    store._con.execute(
        "INSERT OR REPLACE INTO news VALUES (?, ?, ?)",
        ["AAPL", datetime.now() - timedelta(hours=1), RSS.decode()],
    )
    news = FakeNews(fail=True)
    svc = DataService(store, None, None, news_provider=news)
    items = await svc.get_news("AAPL")
    assert news.calls == 1              # tried to refresh (stale)
    assert items and items[0].title == "Apple up"   # fell back to stale cache


async def test_get_news_returns_empty_when_no_cache_and_fetch_fails():
    svc = DataService(Store(":memory:"), None, None, news_provider=FakeNews(fail=True))
    assert await svc.get_news("AAPL") == []
