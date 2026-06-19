from __future__ import annotations

import json
import time
import urllib.request

_USER_AGENT = "bbterm/0.1 (yagurootajum@gmail.com)"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


def _http_get(url: str, user_agent: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


class EdgarProvider:
    name = "edgar"

    def __init__(
        self,
        user_agent: str = _USER_AGENT,
        *,
        opener=None,
        rate_limit_sleep: float = 0.0,
    ) -> None:
        self._ua = user_agent
        self._open = opener or _http_get
        self._sleep = rate_limit_sleep
        self._cik_map: dict[str, str] | None = None

    def _fetch(self, url: str) -> bytes:
        if self._sleep:
            time.sleep(self._sleep)
        return self._open(url, self._ua)

    def _load_cik_map(self) -> dict[str, str]:
        raw = json.loads(self._fetch(_TICKERS_URL))
        out: dict[str, str] = {}
        for row in raw.values():
            out[str(row["ticker"]).upper()] = f"{int(row['cik_str']):010d}"
        return out

    def _cik(self, symbol: str) -> str:
        if self._cik_map is None:
            self._cik_map = self._load_cik_map()
        return self._cik_map[symbol.upper()]

    def get_facts(self, symbol: str) -> dict:
        url = _FACTS_URL.format(cik=self._cik(symbol))
        return json.loads(self._fetch(url))

    def get_submissions(self, symbol: str) -> dict:
        url = _SUBMISSIONS_URL.format(cik=self._cik(symbol))
        return json.loads(self._fetch(url))
