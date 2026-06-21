from __future__ import annotations

import webbrowser

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from bbterm.data.models import Filing


def _filing_label(f: Filing) -> str:
    return f"{f.form:<8}{f.filed_date.isoformat():<12}{f.period:<12}{f.url}"


class FilingsView(Widget):
    DEFAULT_CSS = """
    FilingsView { height: 1fr; }
    FilingsView > Label.header {
        background: $primary; color: $text; width: 100%;
        padding: 0 1; text-style: bold;
    }
    FilingsView > Label.hint { color: $text-muted; padding: 0 1; }
    FilingsView > OptionList { height: 1fr; }
    """

    def __init__(self, opener=webbrowser.open, **kwargs) -> None:
        super().__init__(**kwargs)
        self._opener = opener
        self._filings: list[Filing] = []

    def compose(self) -> ComposeResult:
        yield Label("FILINGS", classes="header")
        yield Label("  ↑↓ select · Enter opens in browser", classes="hint")
        yield OptionList()

    def show(self, filings: list[Filing]) -> None:
        self._filings = filings
        try:
            olist = self.query_one(OptionList)
        except Exception:
            return  # not mounted yet (e.g. unit test); filings stored for _open_index
        olist.clear_options()
        if not filings:
            olist.add_option(Option("  No filings available.", disabled=True))
            return
        for f in filings:
            olist.add_option(Option(_filing_label(f)))

    def _open_index(self, index: int) -> None:
        if 0 <= index < len(self._filings):
            try:
                self._opener(self._filings[index].url)
            except Exception:
                pass  # never crash the UI on a failed open

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._open_index(event.option_index)
