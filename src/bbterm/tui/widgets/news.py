from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from bbterm.data.models import NewsItem


def _relative_age(published: datetime | None, now: datetime) -> str:
    if published is None:
        return "—"
    secs = (now - published).total_seconds()
    if secs < 0:
        return "now"
    mins = int(secs // 60)
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def render_news_text(items: list[NewsItem], now: datetime | None = None) -> str:
    if not items:
        return "  No news."
    now = now or datetime.now(timezone.utc)
    lines = ["  Recent headlines", ""]
    for n in items:
        lines.append(f"  {_relative_age(n.published, now):<8}{(n.source or '—'):<16}{n.title}")
        lines.append(f"          {n.url}")
    return "\n".join(lines)


class NewsView(Widget):
    DEFAULT_CSS = """
    NewsView { height: 1fr; }
    NewsView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    NewsView > Static.body { width: 100%; height: 1fr; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        yield Label("NEWS", classes="header")
        yield Static("  Select a symbol.", classes="body")

    def show(self, items: list[NewsItem]) -> None:
        self.query_one(".body", Static).update(Text(render_news_text(items)))
