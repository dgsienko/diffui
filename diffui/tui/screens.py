from __future__ import annotations

from typing import ClassVar

from rich.table import Table
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea

KEYS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Navigate",
        [
            ("up / down", "Move the cursor one row"),
            ("pgup / pgdn", "Move a page"),
            ("ctrl+u / ctrl+d", "Move half a page"),
            ("g / G", "First / last row"),
            ("left, h / right, l", "Previous / next file"),
            ("k / j", "Previous / next hunk"),
            ("p / n", "Previous / next comment thread"),
            ("]", "Next unreviewed file"),
            ("b", "Show or hide the file list"),
        ],
    ),
    (
        "Review",
        [
            ("r", "Mark the file reviewed or unreviewed"),
            ("s", "Sort files by risk"),
            ("c, enter", "Comment on the line or range, or reply to the thread"),
            ("v", "Start a range at the cursor"),
            ("shift+up / shift+down", "Start or extend a range"),
            ("esc", "Clear the range"),
            ("x", "Resolve or reopen the thread"),
            ("A", "Send open comments to the agent"),
            ("o", "Open this file in the browser"),
        ],
    ),
    ("Other", [("?", "This help"), ("q", "Quit")]),
]


class HelpScreen(ModalScreen[None]):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape,q,question_mark", "dismiss", show=False)]

    def compose(self) -> ComposeResult:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold", no_wrap=True)
        table.add_column()
        for title, keys in KEYS:
            table.add_row(f"\n{title}", "")
            for key, what in keys:
                table.add_row(key, what)
        with Vertical(classes="dialog"):
            yield Static("Keys", classes="dialog-title")
            yield VerticalScroll(Static(table))
            yield Static(
                "Click a file to open it. Click a line number, or drag across several, to comment. Esc closes.",
                classes="hint",
            )


class ComposeScreen(ModalScreen[str | None]):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+s", "submit", show=False),
    ]

    def __init__(self, title: str, context: str = "") -> None:
        super().__init__()
        self._heading = title
        self._quote = context

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(self._heading, classes="dialog-title", markup=False)
            if self._quote:
                yield Static(self._quote, classes="hint", markup=False)
            yield TextArea(id="compose-text")
            with Horizontal(classes="buttons"):
                yield Button("Save (ctrl+s)", id="save", variant="primary")
                yield Button("Cancel (esc)", id="cancel")

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.action_submit()
        else:
            self.action_cancel()

    def action_submit(self) -> None:
        text = self.query_one(TextArea).text.strip()
        self.dismiss(text or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class AgentScreen(ModalScreen[bool]):
    """The prompt the server built. Inside herdr, enter pastes it into the workspace's agent pane."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape,q", "cancel", show=False),
        Binding("enter,y", "paste", show=False),
        Binding("c", "copy", show=False),
    ]

    def __init__(self, data: dict) -> None:
        super().__init__()
        self._data = data

    def compose(self) -> ComposeResult:
        agent = self._data.get("herdr_agent")
        count = self._data["comment_count"]
        if agent:
            title = f"Paste {count} open comment(s) into {agent}"
            hint = (
                "enter pastes the prompt into the agent pane. Press Enter there to send it. c copies it, esc cancels."
            )
        else:
            title = f"{count} open comment(s) for the agent"
            hint = (
                "Not inside herdr, so nothing is pasted. Copy this prompt into your agent with c. "
                f"Context file: {self._data.get('context_path', '')}. Esc closes."
            )
        with Vertical(classes="dialog"):
            yield Static(title, classes="dialog-title", markup=False)
            yield VerticalScroll(Static(self._data["prompt"], markup=False))
            yield Static(hint, classes="hint", markup=False)

    def action_paste(self) -> None:
        self.dismiss(bool(self._data.get("herdr_agent")))

    def action_copy(self) -> None:
        self.app.copy_to_clipboard(self._data["prompt"])
        self.app.notify("Prompt copied")

    def action_cancel(self) -> None:
        self.dismiss(False)
