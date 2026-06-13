"""End-of-day sync: pull daily bars for the whole watchlist into DuckDB.

Run after market close (or any time): `bbterm-sync`
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from bbterm.config import load_config
from bbterm.data import build_service
from bbterm.data.providers.base import CostCapExceeded
from bbterm.data.service import DataService


async def sync_watchlist(service: DataService, days: int = 365) -> dict[str, int]:
    end = datetime.now()
    start = end - timedelta(days=days)
    counts: dict[str, int] = {}
    for symbol in service.store.get_watchlist():
        bars = await service.get_bars(symbol, "1d", start, end)
        counts[symbol] = len(bars)
    return counts


def main() -> None:
    service = build_service(load_config())
    try:
        counts = asyncio.run(sync_watchlist(service))
    except CostCapExceeded as err:
        raise SystemExit(f"aborted: {err}")
    for symbol, n in counts.items():
        print(f"{symbol}: {n} daily bars cached")


if __name__ == "__main__":
    main()
