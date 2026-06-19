from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, Static

from bbterm.data.models import Filing


def render_filings_text(filings: list[Filing]) -> str:
    if not filings:
        return "  No filings available."
    lines = ["  Recent SEC filings", ""]
    for f in filings:
        date_str = f.filed_date.isoformat()
        lines.append(f"  {f.form:<8}{date_str:<12}{f.period:<12}{f.url}")
    return "\n".join(lines)


class FilingsView(Widget):
    DEFAULT_CSS = """
    FilingsView { height: 1fr; }
    FilingsView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    FilingsView > Static.body { width: 100%; height: 1fr; padding: 1 0; }
    """

    def compose(self) -> ComposeResult:
        yield Label("FILINGS", classes="header")
        yield Static("  Select a symbol.", classes="body")

    def show(self, filings: list[Filing]) -> None:
        self.query_one(".body", Static).update(Text(render_filings_text(filings)))
