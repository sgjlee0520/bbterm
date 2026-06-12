import yfinance as yf
import pandas as pd
from dataclasses import dataclass
from typing import Optional


@dataclass
class Quote:
    ticker: str
    price: float
    prev_close: float
    change: float
    pct_change: float
    volume: int
    name: str

    @property
    def change_str(self) -> str:
        sign = "+" if self.change >= 0 else ""
        return f"{sign}{self.change:.2f} ({sign}{self.pct_change:.2f}%)"

    @property
    def is_up(self) -> bool:
        return self.change >= 0


def get_quote(ticker: str) -> Optional[Quote]:
    try:
        t = yf.Ticker(ticker)
        fi = t.fast_info
        price = fi.last_price
        prev = fi.previous_close
        if price is None or prev is None:
            return None
        change = price - prev
        pct = change / prev * 100
        name = t.info.get("shortName", ticker) if hasattr(t, "info") else ticker
        return Quote(
            ticker=ticker,
            price=price,
            prev_close=prev,
            change=change,
            pct_change=pct,
            volume=int(fi.three_month_average_volume or 0),
            name=name,
        )
    except Exception:
        return None


def get_history(ticker: str, period: str = "1mo") -> Optional[pd.DataFrame]:
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period)
        if df.empty:
            return None
        return df
    except Exception:
        return None


PERIODS = {
    "1": ("1d", "1 Day"),
    "2": ("5d", "5 Days"),
    "3": ("1mo", "1 Month"),
    "4": ("6mo", "6 Months"),
    "5": ("1y", "1 Year"),
    "6": ("5y", "5 Years"),
}

DEFAULT_WATCHLIST = [
    "SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "BTC-USD", "ETH-USD",
]
