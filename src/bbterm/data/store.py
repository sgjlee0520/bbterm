from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb

from bbterm.data.models import Bar

DEFAULT_WATCHLIST = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]


class Store:
    def __init__(self, path: Path | str) -> None:
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(str(path))
        self._init_schema()

    def _init_schema(self) -> None:
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS ohlcv (
                symbol VARCHAR, interval VARCHAR, ts TIMESTAMP,
                open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
                volume BIGINT,
                PRIMARY KEY (symbol, interval, ts)
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                position INTEGER, symbol VARCHAR PRIMARY KEY
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS edgar_facts (
                symbol VARCHAR PRIMARY KEY, fetched_at TIMESTAMP, json VARCHAR
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS edgar_filings (
                symbol VARCHAR PRIMARY KEY, fetched_at TIMESTAMP, json VARCHAR
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS news (
                symbol VARCHAR PRIMARY KEY, fetched_at TIMESTAMP, json VARCHAR
            )
            """
        )

    def upsert_bars(self, bars: list[Bar]) -> None:
        if not bars:
            return
        rows = [
            (b.symbol, b.interval, b.ts, b.open, b.high, b.low, b.close, b.volume)
            for b in bars
        ]
        self._con.executemany(
            "INSERT OR REPLACE INTO ohlcv VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows
        )

    def get_bars(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[Bar]:
        rows = self._con.execute(
            """
            SELECT symbol, interval, ts, open, high, low, close, volume
            FROM ohlcv
            WHERE symbol = ? AND interval = ? AND ts >= ? AND ts <= ?
            ORDER BY ts
            """,
            [symbol, interval, start, end],
        ).fetchall()
        return [Bar(*row) for row in rows]

    def coverage(
        self, symbol: str, interval: str
    ) -> tuple[datetime, datetime] | None:
        row = self._con.execute(
            "SELECT min(ts), max(ts) FROM ohlcv WHERE symbol = ? AND interval = ?",
            [symbol, interval],
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return row[0], row[1]

    def get_watchlist(self) -> list[str]:
        rows = self._con.execute(
            "SELECT symbol FROM watchlist ORDER BY position"
        ).fetchall()
        if not rows:
            self.set_watchlist(DEFAULT_WATCHLIST)
            return list(DEFAULT_WATCHLIST)
        return [r[0] for r in rows]

    def set_watchlist(self, symbols: list[str]) -> None:
        self._con.execute("DELETE FROM watchlist")
        self._con.executemany(
            "INSERT INTO watchlist VALUES (?, ?)", list(enumerate(symbols))
        )

    def get_edgar_facts(self, symbol: str) -> tuple[datetime, str] | None:
        return self._get_edgar("edgar_facts", symbol)

    def set_edgar_facts(self, symbol: str, json_str: str) -> None:
        self._set_edgar("edgar_facts", symbol, json_str)

    def get_edgar_filings(self, symbol: str) -> tuple[datetime, str] | None:
        return self._get_edgar("edgar_filings", symbol)

    def set_edgar_filings(self, symbol: str, json_str: str) -> None:
        self._set_edgar("edgar_filings", symbol, json_str)

    def get_news(self, symbol: str) -> tuple[datetime, str] | None:
        return self._get_edgar("news", symbol)

    def set_news(self, symbol: str, text: str) -> None:
        self._set_edgar("news", symbol, text)

    def _get_edgar(self, table: str, symbol: str) -> tuple[datetime, str] | None:
        row = self._con.execute(
            f"SELECT fetched_at, json FROM {table} WHERE symbol = ?", [symbol]
        ).fetchone()
        if row is None:
            return None
        return row[0], row[1]

    def _set_edgar(self, table: str, symbol: str, json_str: str) -> None:
        self._con.execute(
            f"INSERT OR REPLACE INTO {table} VALUES (?, ?, ?)",
            [symbol, datetime.now(), json_str],
        )

    def close(self) -> None:
        self._con.close()
