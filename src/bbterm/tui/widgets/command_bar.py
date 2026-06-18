from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Input


class CommandBar(Input):
    """Single-line command input. Submits via Input.Submitted (.value)."""

    DEFAULT_CSS = """
    CommandBar { dock: top; height: 1; border: none; background: $boost; }
    CommandBar:focus { background: $accent 20%; }
    """

    # Note: do NOT name this "Blurred" — Input already defines Input.Blurred
    # and constructs it with positional args internally.
    class EscapePressed(Message):
        """Posted when the user presses Escape to leave the command bar."""

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self) -> None:
        super().__init__(
            placeholder="  : command (type a ticker, ADD, DEL, GP, DES, ?)",
            id="command-bar",
        )

    def action_cancel(self) -> None:
        self.post_message(self.EscapePressed())
