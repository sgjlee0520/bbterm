from __future__ import annotations

import json
import urllib.parse
import urllib.request

_BASE = "https://www.lambdafin.com/api/congressional/recent"
# Cloudflare blocks Python's default urllib UA (error 1010); send a browser UA.
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _http_get(url: str, headers: dict) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


class CongressProvider:
    name = "lambdafin"

    def __init__(self, api_key: str, *, opener=None) -> None:
        self._key = api_key
        self._open = opener or _http_get

    def get_congress_trades(self, symbol: str, days: int = 365) -> dict:
        url = f"{_BASE}?ticker={urllib.parse.quote(symbol)}&days={days}"
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Accept": "application/json",
            "User-Agent": _UA,
        }
        return json.loads(self._open(url, headers))
