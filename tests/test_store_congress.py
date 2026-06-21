from bbterm.data.store import Store


def test_congress_roundtrip():
    store = Store(":memory:")
    assert store.get_congress("AAPL") is None
    store.set_congress("AAPL", '{"trades": []}')
    cached = store.get_congress("AAPL")
    assert cached is not None and cached[1] == '{"trades": []}'
