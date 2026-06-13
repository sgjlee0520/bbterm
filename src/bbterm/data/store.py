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

    def close(self) -> None:
        self._con.close()
