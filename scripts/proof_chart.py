"""Step-0 proof — render a sample candlestick IMAGE in your terminal.
Run in iTerm2:  .venv/bin/python scripts/proof_chart.py   (press q to quit)
You should see a CRISP candlestick chart, not blocky colored blocks."""
import io
import random
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("Agg")
import mplfinance as mpf
import pandas as pd
from textual.app import App, ComposeResult
from textual.widgets import Label
from textual_image.renderable import Image as _Auto, SixelImage, TGPImage
from textual_image.widget import Image


def _sample_png() -> bytes:
    random.seed(1)
    base = datetime(2026, 1, 2)
    rows = {"Open": [], "High": [], "Low": [], "Close": [], "Volume": []}
    idx = []
    price = 100.0
    for i in range(40):
        op = price
        cl = op + random.uniform(-3, 3)
        rows["Open"].append(op)
        rows["Close"].append(cl)
        rows["High"].append(max(op, cl) + random.uniform(0, 2))
        rows["Low"].append(min(op, cl) - random.uniform(0, 2))
        rows["Volume"].append(random.randint(1_000_000, 5_000_000))
        idx.append(base + timedelta(days=i))
        price = cl
    df = pd.DataFrame(rows, index=pd.DatetimeIndex(idx))
    buf = io.BytesIO()
    mpf.plot(df, type="candle", volume=True,
             style=mpf.make_mpf_style(base_mpf_style="nightclouds"),
             title="SAMPLE — candlestick proof",
             savefig=dict(fname=buf, format="png", dpi=100, bbox_inches="tight"))
    return buf.getvalue()


class Proof(App):
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        crisp = _Auto in (SixelImage, TGPImage)
        yield Label(
            f"Renderer: {_Auto.__name__}  "
            + ("(graphics protocol — should be crisp)" if crisp
               else "(NO graphics protocol — will look blocky)")
            + "   ·  press q to quit"
        )
        yield Image(io.BytesIO(_sample_png()))


if __name__ == "__main__":
    Proof().run()
