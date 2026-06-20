from __future__ import annotations

import os
import urllib.parse
import urllib.request

_USER_AGENT = "bbterm/0.1 (yagurootajum@gmail.com)"
_DEFAULT_FEED = (
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
)


def _http_get(url: str, user_agent: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


class NewsProvider:
    name = "news"

    def __init__(
        self,
        user_agent: str = _USER_AGENT,
        *,
        opener=None,
        feed_url: str | None = None,
    ) -> None:
        self._ua = user_agent
        self._open = opener or _http_get
        self._feed = feed_url or os.environ.get("BBTERM_NEWS_FEED_URL", _DEFAULT_FEED)

    def get_news(self, symbol: str) -> bytes:
        query = urllib.parse.quote(f'"{symbol}" stock')
        return self._open(self._feed.format(query=query), self._ua)
