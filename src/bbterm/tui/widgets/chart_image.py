from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # render without a display; must precede mplfinance import

import mplfinance as mpf  # noqa: E402
import pandas as pd  # noqa: E402

from bbterm.data.models import Bar  # noqa: E402

_STYLE = mpf.make_mpf_style(base_mpf_style="nightclouds")


def render_candles_png(bars: list[Bar], symbol: str, period_label: str) -> bytes:
    df = pd.DataFrame(
        {
            "Open": [b.open for b in bars],
            "High": [b.high for b in bars],
            "Low": [b.low for b in bars],
            "Close": [b.close for b in bars],
            "Volume": [b.volume for b in bars],
        },
        index=pd.DatetimeIndex([b.ts for b in bars]),
    )
    buf = io.BytesIO()
    mpf.plot(
        df,
        type="candle",
        volume=True,
        style=_STYLE,
        title=f"{symbol} — {period_label}",
        savefig=dict(fname=buf, format="png", dpi=100, bbox_inches="tight"),
    )
    return buf.getvalue()


def image_charts_available() -> bool:
    """True only when textual-image auto-selected a real graphics protocol
    (Sixel or Kitty TGP). In a non-tty (tests) or a plain terminal this is False,
    and the caller falls back to the text chart."""
    try:
        from textual_image.renderable import Image as _Auto, SixelImage, TGPImage

        return _Auto in (SixelImage, TGPImage)
    except Exception:
        return False
