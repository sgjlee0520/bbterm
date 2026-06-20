# News Feed — Per-Symbol Headlines (`N`)

**Date:** 2026-06-20
**Status:** Approved (brainstorming, 2026-06-20)
**Builds on:** Phase 4 (SEC EDGAR fundamentals & filings). This feature mirrors the
EDGAR provider/service/widget pattern exactly.

## Goal

Add a per-symbol **news headlines** view to bbterm, alongside the existing
filings view. A new `N` command shows recent headlines for the currently-loaded
ticker — *headline · source · relative time · link* — sourced from a free,
keyless RSS feed.

## Context & constraints

- This is a **free, open-source, personal-use** tool. Headlines + links out to
  the source is standard RSS-reader behavior; commercial-licensing concerns that
  shaped earlier phases do not constrain this feature. The provider sits behind a
  small interface, so a licensed feed could replace it later if ever needed.
- The existing **filings view (`FIL`) is unchanged**; news is an *additional*
  view, not a replacement.
- No new dependencies (stdlib `urllib` + `xml.etree.ElementTree`).
- Tests make no network calls.

## Source

**Google News RSS search**, per ticker, keyless:

```
https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en
```

where `{query}` is URL-encoded `"{SYMBOL}" stock` (e.g. `"AAPL" stock`). The feed
returns standard RSS 2.0 XML whose `<item>`s carry `<title>` (usually
`"Headline - Publisher"`), `<link>`, `<pubDate>` (RFC-822), and a `<source>`
element with the publisher name.

The feed URL template is overridable via the env var **`BBTERM_NEWS_FEED_URL`**
(a Python format string with a `{query}` placeholder); the default above is used
when unset. No API key, works out of the box.

## Data layer

### Model (`data/models.py`)

```python
@dataclass(frozen=True)
class NewsItem:
    title: str          # "Apple unveils ..."
    source: str         # "Reuters"  (may be "")
    published: datetime # parsed from pubDate; tz-aware UTC
    url: str            # link to the article
```

### Provider (`data/providers/news.py`)

`NewsProvider` mirrors `EdgarProvider`: stdlib HTTP with an **injectable fetcher**
so tests pass a fake and make no network calls.

- `get_news(symbol) -> bytes` returns the **raw RSS XML** (so the service caches
  it verbatim and the pure parser does the parsing — same split as EDGAR).
- A declared `User-Agent` (`bbterm/0.1 (yagurootajum@gmail.com)`), 30s timeout.
- `name = "news"`. The query is built by URL-encoding `"{symbol}" stock` into the
  feed template (default Google News, or `BBTERM_NEWS_FEED_URL` if set).

### Pure logic (`data/news.py`) — zero I/O, unit-tested

- `parse_news(rss_bytes, limit=20) -> list[NewsItem]`: parse with
  `xml.etree.ElementTree`; for each `<item>` (newest first, capped at `limit`):
  - `title` from `<title>`; if it ends with `" - {source}"` and `<source>` text
    matches, strip the trailing `" - {source}"` for a clean headline.
  - `source` from the `<source>` element's text (empty string if absent).
  - `published` parsed from `<pubDate>` via `email.utils.parsedate_to_datetime`,
    normalized to tz-aware UTC; items with an unparseable date sort last.
  - `url` from `<link>`.
  - Malformed XML → return `[]` (so the UI can show a "no news" notice).

### Store (`data/store.py`)

One cache table mirroring the EDGAR tables (raw RSS text cached so parsing can
evolve without re-fetching):

```sql
CREATE TABLE IF NOT EXISTS news (symbol VARCHAR PRIMARY KEY, fetched_at TIMESTAMP, json VARCHAR);
```

`get_news(symbol) -> tuple[datetime, str] | None` and
`set_news(symbol, text)` reuse the existing `_get_edgar`/`_set_edgar` helpers
(rename is unnecessary; they are table-generic — pass `"news"`).

### Service (`data/service.py`)

`get_news(symbol) -> list[NewsItem]`:

- Cache-through with a **15-minute TTL** (`NEWS_TTL_SECONDS = 900.0`) keyed on
  `fetched_at`, paralleling `EDGAR_TTL_SECONDS`/`_edgar_fresh`.
- On miss/stale: fetch via `asyncio.to_thread`, persist the raw RSS text, then run
  `parse_news`.
- On fetch failure: degrade to cached RSS if present; else return `[]`.
- Reuses the app's single DB connection.

## UI

### Command (`commands.py`)

Add a `ShowNews` dataclass; verb **`N`** → `ShowNews`. Unit-tested.

### Widget (`tui/widgets/news.py`)

- `NewsView(Widget)` with `.show(items: list[NewsItem])`.
- `render_news_text(items) -> str` pure helper: one row per item —
  headline · source · relative time (e.g. `3h ago`, `2d ago`) · url. A small
  `_relative_age(published, now)` helper formats the age. "No news." when empty.

### App (`tui/app.py`)

- Add `NewsView(id="news")` to the `ContentSwitcher`.
- `_dispatch` handles `ShowNews`: set `switcher.current = "news"`, launch a worker.
- Worker `load_news` (`@work(exclusive=True, group="news")`) calls
  `service.get_news(current_symbol)` and `.show(...)`; degrade-to-notice on error,
  mirroring `load_filings`.
- Footer/help text gains `N news`.

## Error handling

- Network/HTTP failure → degrade to cached RSS if present, else
  `notify("News unavailable")` and an empty panel.
- Empty/malformed feed → "No news." panel, no crash.
- No symbol loaded → same guard as the other per-symbol views.

## Testing (no network)

- `tests/fixtures/` — a trimmed real Google News RSS payload.
- `test_news.py` — `parse_news`: title/source extraction, the `" - Publisher"`
  stripping, `pubDate` parsing + ordering, limit, and malformed-XML → `[]`.
- `test_commands.py` — `N` parses to `ShowNews`.
- `test_app_commands.py` — `N` switches the `ContentSwitcher` to `NewsView`,
  using a `FakeNewsProvider` (no network).
- A `render_news_text` test for layout + relative-age formatting.

## Out of scope

Full article text (headlines + links only), sentiment/scoring, market-wide
(non-symbol) news, multiple feeds/aggregation, and any paid or keyed source.

## Non-goals / constraints carried forward

- Keep widgets dumb; all parsing/derivation in pure, tested modules
  (`data/news.py`), like `fundamentals.py`.
- Tests make no network calls and spend no credits.
- The filings view (`FIL`) is untouched.
