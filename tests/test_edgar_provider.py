import json

import pytest

from bbterm.data.providers.edgar import EdgarProvider

TICKERS = json.dumps({
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft"},
})


def make_provider(responses):
    """responses: dict mapping url-substring -> bytes payload."""
    calls = []

    def opener(url, user_agent):
        calls.append((url, user_agent))
        for needle, payload in responses.items():
            if needle in url:
                return payload
        raise AssertionError(f"unexpected url {url}")

    return EdgarProvider(opener=opener), calls


def test_cik_zero_padded():
    provider, _ = make_provider({"company_tickers.json": TICKERS.encode()})
    assert provider._cik("AAPL") == "0000320193"


def test_cik_unknown_symbol_raises():
    provider, _ = make_provider({"company_tickers.json": TICKERS.encode()})
    with pytest.raises(KeyError):
        provider._cik("NOPE")


def test_get_facts_hits_right_url_and_sends_user_agent():
    facts = {"cik": 320193, "facts": {}}
    provider, calls = make_provider({
        "company_tickers.json": TICKERS.encode(),
        "companyfacts/CIK0000320193.json": json.dumps(facts).encode(),
    })
    assert provider.get_facts("AAPL") == facts
    assert all("bbterm/0.1" in ua for _, ua in calls)


def test_get_submissions_hits_right_url():
    subs = {"cik": 320193, "filings": {"recent": {}}}
    provider, _ = make_provider({
        "company_tickers.json": TICKERS.encode(),
        "submissions/CIK0000320193.json": json.dumps(subs).encode(),
    })
    assert provider.get_submissions("AAPL") == subs
