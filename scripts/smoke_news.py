"""Manual news smoke check — hits live Google News RSS once. Run by hand:
    .venv/bin/python scripts/smoke_news.py AAPL
Not part of the pytest suite (no network in tests)."""
import sys

from bbterm.data.news import parse_news
from bbterm.data.providers.news import NewsProvider


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    for n in parse_news(NewsProvider().get_news(symbol), limit=10):
        print(f"  {str(n.published):<28}{n.source:<18}{n.title}")
        print(f"      {n.url}")


if __name__ == "__main__":
    main()
