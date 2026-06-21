from bbterm.data.providers.lambdafin_ import CongressProvider


def test_get_congress_trades_builds_url_and_auth():
    captured = {}

    def fake_open(url, headers):
        captured["url"] = url
        captured["headers"] = headers
        return b'{"trades": [], "count": 0, "days": 730}'

    out = CongressProvider(api_key="secret", opener=fake_open).get_congress_trades("AAPL")
    assert "ticker=AAPL" in captured["url"] and "days=365" in captured["url"]  # Lambda caps days at 365
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert "Mozilla" in captured["headers"]["User-Agent"]  # Cloudflare needs a browser UA
    assert out == {"trades": [], "count": 0, "days": 730}
