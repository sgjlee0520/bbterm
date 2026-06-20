from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from bbterm.data.models import NewsItem

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_news(rss: bytes | str, limit: int = 20) -> list[NewsItem]:
    try:
        root = ET.fromstring(rss)
    except ET.ParseError:
        return []
    items: list[NewsItem] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        source = (item.findtext("source") or "").strip()
        suffix = f" - {source}"
        if source and title.endswith(suffix):
            title = title[: -len(suffix)].strip()
        items.append(
            NewsItem(
                title=title,
                source=source,
                published=_parse_date(item.findtext("pubDate")),
                url=(item.findtext("link") or "").strip(),
            )
        )
    items.sort(key=lambda n: n.published or _EPOCH, reverse=True)
    return items[:limit]
