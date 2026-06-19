"""Manual EDGAR smoke check — hits the live SEC API once. Run by hand:
    .venv/bin/python scripts/smoke_edgar.py AAPL
Not part of the pytest suite (no network in tests)."""
import sys

from bbterm.data.fundamentals import extract_fundamentals, parse_filings
from bbterm.data.providers.edgar import EdgarProvider


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    provider = EdgarProvider(rate_limit_sleep=0.2)
    print(f"CIK({symbol}) = {provider._cik(symbol)}")
    metrics = extract_fundamentals(provider.get_facts(symbol))
    for m in metrics:
        print(f"  {m.label:<22}{m.value:>18,.0f}  FY{m.fy}  yoy={m.yoy_pct}")
    print("--- filings ---")
    for f in parse_filings(provider.get_submissions(symbol), limit=5):
        print(f"  {f.form:<8}{f.filed_date}  {f.url}")


if __name__ == "__main__":
    main()
