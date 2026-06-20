from bbterm.data.store import Store


def test_news_roundtrip():
    store = Store(":memory:")
    assert store.get_news("AAPL") is None
    store.set_news("AAPL", "<rss/>")
    cached = store.get_news("AAPL")
    assert cached is not None
    _, text = cached
    assert text == "<rss/>"
