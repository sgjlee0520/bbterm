"""Manual congress-trades smoke check — hits live Lambda Finance once. Run by hand:
    .venv/bin/python scripts/smoke_congress.py NVDA
Reads LAMBDA_API_KEY from .env. Not part of the pytest suite (no network in tests)."""
import sys
from pathlib import Path

from bbterm.config import _load_dotenv
from bbterm.data.congress import filter_to_roster, parse_congress_trades, summarize
from bbterm.data.providers.lambdafin_ import CongressProvider


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    key = _load_dotenv(Path(".env")).get("LAMBDA_API_KEY")
    if not key:
        print("No LAMBDA_API_KEY in .env"); return
    raw = CongressProvider(api_key=key).get_congress_trades(symbol)
    trades = filter_to_roster(parse_congress_trades(raw))
    print(f"{symbol}: {len(trades)} roster trades")
    for s in summarize(trades):
        print(f"  {s.politician}: {s.n_buys} buys, {s.n_sells} sells, net~{s.net_estimate:,.0f}")
    for t in trades:
        print(f"    {t.side:<5} ${t.amount_low:,.0f}-${t.amount_high:,.0f}  {t.date}  {t.politician}")


if __name__ == "__main__":
    main()
