from bbterm.data.store import Store


def test_edgar_facts_roundtrip():
    store = Store(":memory:")
    assert store.get_edgar_facts("AAPL") is None
    store.set_edgar_facts("AAPL", '{"x": 1}')
    row = store.get_edgar_facts("AAPL")
    assert row is not None
    fetched_at, payload = row
    assert payload == '{"x": 1}'
    assert fetched_at is not None


def test_edgar_filings_roundtrip_and_replace():
    store = Store(":memory:")
    store.set_edgar_filings("AAPL", '{"a": 1}')
    store.set_edgar_filings("AAPL", '{"a": 2}')  # upsert overwrites
    _, payload = store.get_edgar_filings("AAPL")
    assert payload == '{"a": 2}'
