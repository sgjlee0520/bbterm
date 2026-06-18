from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import Input


class CommandBar(Input):
    """Single-line command input. Submits via Input.Submitted (.value)."""

    DEFAULT_CSS = """
    CommandBar { dock: top; height: 1; border: none; background: $boost; }
    CommandBar:focus { background: $accent 20%; }
    """

    class Blurred(Message):
        """Posted when the user presses Escape to leave the command bar."""

    def __init__(self) -> None:
        super().__init__(
            placeholder="  : command (type a ticker, ADD, DEL, GP, DES, ?)",
            id="command-bar",
        )

    def _on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            self.post_message(self.Blurred())
