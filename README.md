# bbterm

<img width="4128" height="1024" alt="Gemini_Generated_Image_8zz0hr8zz0hr8zz0" src="https://github.com/user-attachments/assets/1021302c-5323-4265-a2be-3c1f78cd30fc" />

A local, keyboard-driven market terminal — a Bloomberg-style TUI you run in your
own terminal. Price charts, a watchlist, statistics, and SEC EDGAR fundamentals
and filings, all backed by a local cache so it's fast, works offline once data is
fetched, and costs almost nothing to run.

Built with [Textual](https://textual.textualize.io/) (TUI),
[plotext](https://github.com/piccolomo/plotext) (terminal charts),
[DuckDB](https://duckdb.org/) (local cache), and
[Databento](https://databento.com/) for market data.

## Features

- **Hybrid command bar** — press `:` to type a command. A bare ticker loads a
  symbol (`AAPL`); verbs run actions (`ADD`, `DEL`, `GP`, `DES`, `FA`, `FIL`, `?`).
- **Candlestick + volume chart** (`GP`), with `c` to toggle a line view and
  `1`–`6` for time ranges (1D / 5D / 1M / 6M / 1Y / 5Y).
- **Statistics panel** (`DES`) — last, 52-week high/low, 1M and YTD returns,
  average volume, and day range, all computed from cached price bars.
- **Fundamentals** (`FA`) — revenue, net income, EPS, assets, cash flow and more
  from **SEC EDGAR**, each with its fiscal year and year-over-year change.
- **Recent filings** (`FIL`) — the company's latest 10-K / 10-Q / 8-K filings
  with dates and links, from SEC EDGAR.
- **Persisted watchlist** — `ADD`/`DEL` edit it and the change is saved.
- **Local cache** — market bars and EDGAR data are cached in DuckDB; each paid
  record is bought once, and EDGAR data is reused for 24 hours.

## Architecture

UI widgets never fetch data — they render what the `DataService` returns. The
service is an async, cache-through layer over a DuckDB store, fetching only the
date ranges it's missing. Data providers sit behind small Protocols:

- **Databento** — primary historical bars (when `DATABENTO_API_KEY` is set).
- **yfinance** — free fallback for bars/quotes when no Databento key is present.
- **SEC EDGAR** — fundamentals and filings (free, official, no API key), accessed
  with the standard library only.

All parsing and number-crunching lives in pure, unit-tested modules
(`commands.py`, `data/stats.py`, `data/fundamentals.py`); widgets stay dumb.

## Requirements

- Python ≥ 3.11
- A [Databento](https://databento.com/) API key is optional — without it, bbterm
  runs on the free yfinance fallback. EDGAR needs no key.

## Install

From PyPI (recommended):

```bash
pipx install bbterm-tui     # or: pip install bbterm-tui
```

The installed command and import name are `bbterm` (only the PyPI package is
named `bbterm-tui`). To enable the Databento provider: `pipx install "bbterm-tui[databento]"`.

To install the latest unreleased `main` instead, via
[pipx](https://pipx.pypa.io/):

```bash
pipx install git+https://github.com/sgjlee0520/bbterm.git
```

The core install runs on the free yfinance + SEC EDGAR path. To enable the
Databento provider (requires a `DATABENTO_API_KEY`):

```bash
pipx install "git+https://github.com/sgjlee0520/bbterm.git#egg=bbterm[databento]"
```

Contributors (editable, from a clone):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"          # add ,databento to work on the Databento provider
```

## Configure

Settings come from environment variables or a `.env` file in the project root:

| Variable | Default | Purpose |
|---|---|---|
| `DATABENTO_API_KEY` | _(unset)_ | Enables Databento as the bar provider |
| `BBTERM_DB_PATH` | `data/market.duckdb` | Local cache database path |
| `BBTERM_COST_CAP_USD` | `1.0` | Per-request Databento cost ceiling |
| `BBTERM_DATASET` | `EQUS.MINI` | Databento dataset |

## Run

```bash
bbterm-sync     # optional: pre-cache recent daily bars for your watchlist
bbterm          # launch the terminal
```

### Keys & commands

| Input | Action |
|---|---|
| `:` | Focus the command bar (`Esc` / `Enter` to leave) |
| `<ticker>` | Load a symbol |
| `ADD <sym>` / `DEL <sym>` | Edit the watchlist (saved) |
| `GP` / `DES` | Candlestick chart (crisp image in iTerm2) / statistics |
| `FA` / `FIL` | Fundamentals / SEC filings (↑↓ select, Enter opens in browser) |
| `N` | News headlines |
| `1`–`6` | Time range (1D / 5D / 1M / 6M / 1Y / 5Y) |
| `r` | Refresh · `q` Quit · `?` Help |

Image charts use Sixel/Kitty terminal graphics; on terminals without image
support, bbterm falls back to text charts automatically.

A beginner-friendly guide is in `docs/manual/bbterm-guide.tex`
(build the PDF with `pdflatex bbterm-guide.tex`).

## Tests

```bash
python -m pytest
```

Tests make no network calls and spend no Databento credits; live API access is
exercised only by the manual scripts under `scripts/`.

## Notes

- yfinance is an unofficial data source intended here as a free development
  fallback only.
- SEC EDGAR requests send a declared `User-Agent` with a contact address, as the
  SEC requires.

## License

bbterm is licensed under the **GNU Affero General Public License v3.0 or later**
(AGPL-3.0-or-later). See [`LICENSE`](LICENSE). Copyright © 2026 sgjlee0520.
