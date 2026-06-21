from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from bbterm.data.models import CongressTrade

CONGRESS_ROSTER: list[str] = [
    "Nancy Pelosi", "Jim Justice", "Jefferson Shreve", "Rick Scott",
    "Mark Warner", "Pete Ricketts", "Darrell Issa", "Michael McCaul",
    "Ro Khanna", "Gil Cisneros", "JD Vance",
]


@dataclass(frozen=True)
class PoliticianSummary:
    politician: str
    n_buys: int
    n_sells: int
    net_estimate: float


def _parse_amount(s: str | None) -> tuple[float, float]:
    nums = [n.replace(",", "") for n in re.findall(r"[\d,]+", s or "")]
    vals = [float(n) for n in nums if n.isdigit()]
    if not vals:
        return (0.0, 0.0)
    if len(vals) == 1:
        return (vals[0], vals[0])
    return (vals[0], vals[1])


def parse_congress_trades(payload: dict) -> list[CongressTrade]:
    out: list[CongressTrade] = []
    for t in payload.get("trades", []):
        typ = (t.get("type") or "").strip()
        if typ == "Purchase":
            side = "BUY"
        elif typ.startswith("Sale"):
            side = "SELL"
        else:
            continue  # Exchange / other — not a buy or sell
        try:
            d = datetime.strptime(t.get("transactionDate", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        lo, hi = _parse_amount(t.get("amount"))
        out.append(CongressTrade(
            politician=(t.get("representative") or "").strip(),
            chamber=(t.get("chamber") or "").strip(),
            side=side, amount_low=lo, amount_high=hi, date=d,
        ))
    return out


def _tokens(name: str) -> list[str]:
    return name.lower().replace(",", " ").split()


def _matches(roster_name: str, trade_name: str) -> bool:
    r, t = _tokens(roster_name), _tokens(trade_name)
    if not r or not t or r[-1] != t[-1]:  # last names must match exactly
        return False
    rf, tf = r[0], t[0]                    # first-name prefix (either direction)
    return rf.startswith(tf) or tf.startswith(rf)


def filter_to_roster(
    trades: list[CongressTrade], roster: list[str] = CONGRESS_ROSTER
) -> list[CongressTrade]:
    kept = [t for t in trades if any(_matches(r, t.politician) for r in roster)]
    kept.sort(key=lambda t: t.date, reverse=True)
    return kept


def summarize(trades: list[CongressTrade]) -> list[PoliticianSummary]:
    by: dict[str, list[CongressTrade]] = {}
    for t in trades:
        by.setdefault(t.politician, []).append(t)
    out: list[PoliticianSummary] = []
    for name, ts in by.items():
        n_buys = sum(1 for t in ts if t.side == "BUY")
        n_sells = sum(1 for t in ts if t.side == "SELL")
        net = sum(
            (t.amount_low + t.amount_high) / 2 * (1 if t.side == "BUY" else -1)
            for t in ts
        )
        out.append(PoliticianSummary(name, n_buys, n_sells, net))
    return out
