from __future__ import annotations

import re
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input, Static

from diffui.tui.rows import Row, code_of
from diffui.tui.style import Span


class Find:
    """Matches of a query over the code of a diff's rows, and which one is current."""

    def __init__(self) -> None:
        self.query = ""
        self.matches: list[tuple[int, str, int, int]] = []  # row, side, start, end
        self.current = -1
        self._cells: dict[tuple[int, str], list[tuple[int, int, int]]] = {}

    def search(self, rows: list[Row], query: str, near: int = 0, keep: tuple | None = None) -> None:
        """Rebuild the matches. The current one is `keep` if it survives, else the first at or after row `near`."""
        self.query, self.matches, self.current, self._cells = query, [], -1, {}
        if not query:
            return
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        for i, row in enumerate(rows):
            # A context line shows on both sides of a split row but counts once.
            mirrored = row.kind == "line" and row.old is not None and row.old is row.new
            for side, line in [("new", row.new)] if mirrored else row.sides():
                for m in pattern.finditer(code_of(line)):
                    self._cells.setdefault((i, side), []).append((m.start(), m.end(), len(self.matches)))
                    self.matches.append((i, side, m.start(), m.end()))
            if mirrored and (i, "new") in self._cells:
                self._cells[(i, "old")] = self._cells[(i, "new")]
        if keep is not None:
            self.current = next((n for n in range(len(self.matches)) if self.identity(rows, n) == keep), -1)
        if self.current < 0 and self.matches:
            self.current = next((n for n, m in enumerate(self.matches) if m[0] >= near), 0)

    def identity(self, rows: list[Row], n: int | None = None) -> tuple | None:
        """The current match by line, side and column, which survives the rows being rebuilt."""
        n = self.current if n is None else n
        if not 0 <= n < len(self.matches):
            return None
        row, side, start, _ = self.matches[n]
        return (rows[row].line["index"], side, start)

    def step(self, direction: int) -> tuple[int, str, int, int] | None:
        if not self.matches:
            return None
        self.current = (self.current + direction) % len(self.matches)
        return self.matches[self.current]

    def spans(self, row: int, side: str) -> list[Span]:
        return [(s, e, n == self.current) for s, e, n in self._cells.get((row, side), ())]

    def status(self) -> str:
        if not self.query:
            return ""
        return f"{self.current + 1}/{len(self.matches)}" if self.matches else "no matches"


class FindQuery(Message):
    def __init__(self, query: str) -> None:
        super().__init__()
        self.query = query


class FindStep(Message):
    def __init__(self, direction: int) -> None:
        super().__init__()
        self.direction = direction


class FindClose(Message):
    pass


class _FindInput(Input):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "close", "Close"),
        Binding("down", "step(1)", "Next", key_display="↓/enter"),
        Binding("up,shift+enter", "step(-1)", "Previous", key_display="↑"),
    ]

    def action_close(self) -> None:
        self.post_message(FindClose())

    def action_step(self, direction: int) -> None:
        self.post_message(FindStep(direction))


class FindBar(Horizontal):
    """The find-in-file bar under the diff. enter and shift+enter step through the matches, esc closes it."""

    def compose(self) -> ComposeResult:
        yield Static("Find", id="find-label")
        yield _FindInput(id="find-input", placeholder="text in this file")
        yield Static(id="find-count")

    @property
    def input(self) -> Input:
        return self.query_one(_FindInput)

    def open(self) -> None:
        self.add_class("-open")
        self.input.focus()
        self.input.select_all()

    def close(self) -> None:
        self.remove_class("-open")

    def set_status(self, text: str) -> None:
        self.query_one("#find-count", Static).update(text)

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self.post_message(FindQuery(event.value))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self.post_message(FindStep(1))
