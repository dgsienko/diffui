from __future__ import annotations

import textwrap
from bisect import bisect_right
from dataclasses import dataclass, field
from functools import lru_cache
from typing import ClassVar

from pygments import lex
from pygments.token import Token
from rich.color import Color
from rich.segment import Segment
from rich.style import Style
from textual import events
from textual.binding import Binding, BindingType
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from diffui.diff import get_lexer, token_color
from diffui.git_utils import is_comment_open
from diffui.themes import DEFAULT_THEME
from diffui.themes.theme import Theme

_MAX_CODE_COLS = 1000


@lru_cache(maxsize=512)
def _style(fg: str | None, bg: str, bold: bool = False, dim: bool = False) -> Style:
    return Style(color=Color.parse(fg) if fg else None, bgcolor=Color.parse(bg), bold=bold or None, dim=dim or None)


def add_fg(theme: Theme) -> str:
    return token_color(Token.Literal.String, theme.syntax) or theme.fg


@dataclass(slots=True)
class Row:
    kind: str  # note, hunk, line or thread
    text: str = ""
    line: dict | None = None
    thread: dict | None = None
    top: int = 0
    height: int = 1
    tokens: list[tuple[str, str | None]] | None = None
    strips: dict[bool, list[Strip]] = field(default_factory=dict)

    def key(self) -> tuple:
        if self.line:
            return ("line", self.line["index"])
        if self.thread:
            return ("thread", self.thread.get("id"))
        return (self.kind, self.text)


def build_rows(data: dict, comments: list[dict]) -> list[Row]:
    by_line: dict[int, list[dict]] = {}
    for c in comments:
        by_line.setdefault(c.get("line_index", -1), []).append(c)
    placed: set[int] = set()
    rows: list[Row] = []
    if data.get("file_note"):
        rows.append(Row("note", text=data["file_note"]))
    for hunk in data.get("hunks", []):
        rows.append(Row("hunk", text=hunk["header"]))
        for line in hunk["lines"]:
            rows.append(Row("line", line=line))
            for c in by_line.get(line["index"], []):
                rows.append(Row("thread", thread=c))
                placed.add(id(c))
    if not rows:
        rows.append(Row("note", text="No changes in this file."))
    loose = [c for c in comments if id(c) not in placed]
    if loose:
        rows.append(Row("note", text="Comments on lines that are no longer in the diff"))
        rows.extend(Row("thread", thread=c) for c in loose)
    return rows


class DiffView(ScrollView, can_focus=True):
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("down", "move(1)", show=False),
        Binding("up", "move(-1)", show=False),
        Binding("pagedown", "page(1)", show=False),
        Binding("pageup", "page(-1)", show=False),
        Binding("ctrl+d", "page(0.5)", show=False),
        Binding("ctrl+u", "page(-0.5)", show=False),
        Binding("home,g", "goto_edge(0)", show=False),
        Binding("end,G", "goto_edge(1)", show=False),
    ]

    class Activated(Message):
        """The row under the cursor was clicked again."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.palette: Theme = DEFAULT_THEME
        self.rows: list[Row] = []
        self.cursor = 0
        self.path = ""
        self._data: dict = {}
        self._tops: list[int] = []
        self._digits = 1
        self._gutter_w = 5
        self._wrap_w = 0
        self._lexer = None
        self._code_w = 0

    @property
    def current(self) -> Row | None:
        return self.rows[self.cursor] if self.rows else None

    def set_diff(self, path: str, data: dict, comments: list[dict]) -> None:
        same_file = path == self.path
        self.path, self._data = path, data
        self._lexer = get_lexer(path)
        digits = max(
            (
                len(str(n))
                for h in data.get("hunks", [])
                for ln in h["lines"]
                for n in (ln["old_num"], ln["new_num"])
                if n
            ),
            default=1,
        )
        self._digits = digits
        self._gutter_w = 2 * digits + 4
        self._code_w = max(
            (len(ln["text"]) for h in data.get("hunks", []) for ln in h["lines"]),
            default=0,
        )
        self._rebuild(comments, keep=same_file)

    def set_comments(self, comments: list[dict]) -> None:
        self._rebuild(comments, keep=True)

    def _rebuild(self, comments: list[dict], keep: bool) -> None:
        old_key = self.current.key() if keep and self.current else None
        old_cursor, old_scroll = self.cursor, self.scroll_offset.y
        self.rows = build_rows(self._data, comments)
        self._wrap_w = 0
        self._layout()
        self.cursor = self._find_cursor(old_key, old_cursor)
        self.scroll_to(y=min(old_scroll, max(self._tops[-1] if self._tops else 0, 0)) if keep else 0, animate=False)
        self._reveal(self.cursor)
        self.refresh()

    def _find_cursor(self, key: tuple | None, fallback: int) -> int:
        if key is not None:
            for i, row in enumerate(self.rows):
                if row.key() == key:
                    return i
            return min(fallback, len(self.rows) - 1)
        return next((i for i, r in enumerate(self.rows) if r.kind == "line"), 0)

    def _layout(self) -> None:
        wrap_w = max(self.size.width - self._gutter_w - 4, 24)
        top = 0
        tops = []
        for row in self.rows:
            if row.kind == "thread" and wrap_w != self._wrap_w:
                row.strips.clear()
                row.height = len(self._thread_strips(row, False, wrap_w))
            row.top = top
            tops.append(top)
            top += row.height
        self._wrap_w = wrap_w
        self._tops = tops
        self.virtual_size = Size(max(self._gutter_w + min(self._code_w, _MAX_CODE_COLS) + 2, self.size.width), top)

    def on_resize(self, event: events.Resize) -> None:
        if self.rows and max(event.size.width - self._gutter_w - 4, 24) != self._wrap_w:
            self._layout()
            self._reveal(self.cursor)

    def _reveal(self, index: int) -> None:
        if not self.rows:
            return
        row = self.rows[index]
        view_h = self.size.height
        y = self.scroll_offset.y
        if row.top < y:
            self.scroll_to(y=row.top, animate=False)
        elif row.top + row.height > y + view_h:
            self.scroll_to(y=row.top if row.height >= view_h else row.top + row.height - view_h, animate=False)

    def _set_cursor(self, index: int, top: bool = False) -> None:
        if not self.rows:
            return
        self.cursor = max(0, min(index, len(self.rows) - 1))
        if top:
            self.scroll_to(y=max(self.rows[self.cursor].top - 1, 0), animate=False)
        self._reveal(self.cursor)
        self.refresh()

    def action_move(self, delta: int) -> None:
        self._set_cursor(self.cursor + delta)

    def action_page(self, fraction: float) -> None:
        y = self.rows[self.cursor].top + int(self.size.height * fraction) if self.rows else 0
        self._set_cursor(self._row_at(max(y, 0)))

    def action_goto_edge(self, end: int) -> None:
        self._set_cursor(len(self.rows) - 1 if end else 0)

    def _row_at(self, y: int) -> int:
        return max(bisect_right(self._tops, y) - 1, 0)

    def jump_hunk(self, direction: int) -> bool:
        starts = [i + 1 for i, r in enumerate(self.rows) if r.kind == "hunk" and i + 1 < len(self.rows)]
        targets = [s for s in starts if s > self.cursor] if direction > 0 else [s for s in starts if s < self.cursor]
        if not targets:
            return False
        target = targets[0] if direction > 0 else targets[-1]
        self._set_cursor(target, top=True)
        return True

    def jump_thread(self, direction: int) -> bool:
        threads = [i for i, r in enumerate(self.rows) if r.kind == "thread"]
        if not threads:
            return False
        ahead = [i for i in threads if i > self.cursor] if direction > 0 else [i for i in threads if i < self.cursor]
        target = (ahead[0] if direction > 0 else ahead[-1]) if ahead else (threads[0] if direction > 0 else threads[-1])
        self._set_cursor(target)
        return True

    def on_click(self, event: events.Click) -> None:
        if not self.rows:
            return
        index = self._row_at(event.y + self.scroll_offset.y)
        again = index == self.cursor
        self._set_cursor(index)
        if again and self.rows[index].kind in ("line", "thread"):
            self.post_message(self.Activated())

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        width = self.size.width
        bg = self.palette.bg
        y += scroll_y
        if not self.rows or y >= self.virtual_size.height:
            return Strip.blank(width, _style(None, bg))
        index = self._row_at(y)
        row = self.rows[index]
        active = index == self.cursor
        if row.kind == "thread":
            strips = self._thread_strips(row, active, self._wrap_w)
            strip = strips[min(y - row.top, len(strips) - 1)]
            base = self.palette.comment_header_bg if active else self.palette.comment_bg
        else:
            strip, base = self._flat_strip(row, active)
        total = max(self.virtual_size.width, width)
        return strip.extend_cell_length(total, _style(None, base)).crop(scroll_x, scroll_x + width)

    def _flat_strip(self, row: Row, active: bool) -> tuple[Strip, str]:
        p = self.palette
        mark = "▸" if active else " "
        if row.kind == "hunk":
            base = p.hover_bg if active else p.hunk_bg
            return Strip([Segment(f"{mark}{row.text}", _style(p.hunk_fg, base))]), base
        if row.kind == "note":
            base = p.hover_bg if active else p.bg
            return Strip([Segment(f"{mark}{row.text}", _style(p.fg_muted, base))]), base
        line = row.line
        kind = line["type"]
        if kind == "add":
            base = p.add_hover if active else p.add_bg
        elif kind == "remove":
            base = p.remove_hover if active else p.remove_bg
        else:
            base = p.hover_bg if active else p.bg
        d = self._digits
        gutter = f"{mark}{line['old_num'] or '':>{d}} {line['new_num'] or '':>{d}} "
        prefix_fg = {"add": add_fg(self.palette), "remove": p.delete_fg}.get(kind, p.gutter_fg)
        segments = [
            Segment(gutter, _style(p.gutter_fg, base)),
            Segment(line["text"][:1], _style(prefix_fg, base, bold=True)),
        ]
        for text, color in self._tokens(row):
            segments.append(Segment(text, _style(color or p.fg, base)))
        return Strip(segments), base

    def _tokens(self, row: Row) -> list[tuple[str, str | None]]:
        if row.tokens is None:
            code = row.line["text"][1:].expandtabs(4)[:_MAX_CODE_COLS]
            tokens = [
                (value, token_color(token_type, self.palette.syntax)) for token_type, value in lex(code, self._lexer)
            ]
            if tokens and tokens[-1][0].endswith("\n"):
                last, color = tokens.pop()
                if last != "\n":
                    tokens.append((last[:-1], color))
            row.tokens = tokens
        return row.tokens

    def _thread_strips(self, row: Row, active: bool, wrap_w: int) -> list[Strip]:
        cached = row.strips.get(active)
        if cached is not None:
            return cached
        p = self.palette
        c = row.thread
        bg = p.comment_header_bg if active else p.comment_bg
        resolved = not is_comment_open(c)
        pad = " " * (self._gutter_w - 1)
        bar = ("▌", _style(p.comment_accent, bg))
        out: list[Strip] = []

        def emit(text: str, fg: str, bold: bool = False) -> None:
            out.append(Strip([Segment(pad), Segment(*bar), Segment(f" {text}", _style(fg, bg, bold=bold))]))

        def emit_wrapped(text: str, fg: str, first: str = "", rest: str = "") -> None:
            lines = [ln for part in text.split("\n") for ln in (textwrap.wrap(part, wrap_w - len(first)) or [""])]
            for i, ln in enumerate(lines):
                emit((first if i == 0 else rest) + ln, fg)

        who = c.get("author") or "user"
        head = f"{who}" + (f" [{c['category']}]" if c.get("category") else "") + ("  ✓ resolved" if resolved else "")
        emit(head, p.fg_muted if resolved else p.accent, bold=True)
        emit_wrapped(c.get("comment", ""), p.fg_muted if resolved else p.fg)
        if c.get("suggestion"):
            emit("suggestion:", p.fg_muted)
            emit_wrapped(c["suggestion"], add_fg(self.palette), first="+ ", rest="+ ")
        for r in c.get("replies", []):
            who = r.get("author") or r.get("author_type", "agent")
            emit_wrapped(f"{who}: {r.get('text', '')}", p.fg_muted if resolved else p.fg, first="↳ ", rest="  ")
        row.strips[active] = out
        return out
