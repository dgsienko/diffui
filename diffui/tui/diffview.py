from __future__ import annotations

import textwrap
from bisect import bisect_right
from typing import ClassVar

from rich.segment import Segment
from textual import events
from textual.binding import Binding, BindingType
from textual.geometry import Region, Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from diffui.diff import get_lexer
from diffui.git_utils import is_comment_open
from diffui.themes import DEFAULT_THEME
from diffui.themes.theme import Theme
from diffui.tui.find import Find
from diffui.tui.rows import MAX_CODE_COLS, Row, build_rows
from diffui.tui.split import split_strip
from diffui.tui.style import add_fg, span, style
from diffui.tui.unified import unified_strip

# Each side of the split view keeps about 45 columns of code at this width.
SPLIT_MIN_WIDTH = 100


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
        Binding("shift+down", "extend(1)", show=False),
        Binding("shift+up", "extend(-1)", show=False),
        Binding("tab", "swap_side", show=False),
        # ScrollView binds the arrows to horizontal scroll, which swallows them once a scrollbar shows.
        Binding("left", "app.file(-1)", show=False),
        Binding("right", "app.file(1)", show=False),
    ]

    class Activated(Message):
        """A gutter was clicked or dragged, or the row under the cursor was clicked again."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.palette: Theme = DEFAULT_THEME
        self.rows: list[Row] = []
        self.cursor = 0
        self.range_start: int | None = None
        self.hover: int | None = None
        # Split view: which side of a remove and add pair the cursor, the pointer and a range follow.
        self.side: str | None = None
        self.hover_side: str | None = None
        self.split_wanted = False
        self.find = Find()
        self.path = ""
        # A file shown whole because it is not in the diff: nothing to comment on, no split.
        self.readonly = False
        self.lexer = None
        self.digits = 1
        self._split = False
        self._data: dict = {}
        self._comments: list[dict] = []
        self._tops: list[int] = []
        self._gutter_w = 5
        self._wrap_w = 0
        self._code_w = 0
        self._nums: dict[int, str] = {}
        self._press: int | None = None
        self._swallow_click = False
        self._hints: tuple[str, int] = ("none", 0)

    @property
    def current(self) -> Row | None:
        return self.rows[self.cursor] if self.rows else None

    @property
    def split_active(self) -> bool:
        return self.split_wanted and not self.readonly and self.size.width >= SPLIT_MIN_WIDTH

    @property
    def number_width(self) -> int:
        return max(self.digits, 3)

    def split_widths(self) -> tuple[int, int]:
        left = (self.size.width - 2) // 2
        return left, self.size.width - 2 - left

    def set_diff(self, path: str, data: dict, comments: list[dict], readonly: bool = False) -> None:
        same_file = path == self.path and readonly == self.readonly
        self.path, self._data, self.readonly = path, data, readonly
        self.lexer = get_lexer(path)
        lines = [ln for h in data.get("hunks", []) for ln in h["lines"]]
        self.digits = max((len(str(n)) for ln in lines for n in (ln["old_num"], ln["new_num"]) if n), default=1)
        self._gutter_w = 2 * self.digits + 4
        self._code_w = max((len(ln["text"]) for ln in lines), default=0)
        self._nums = {ln["index"]: str(ln["new_num"] or ln["old_num"] or "") for ln in lines}
        if not same_file:
            self.range_start = None
        self._rebuild(comments, keep=same_file)

    def set_comments(self, comments: list[dict]) -> None:
        self._rebuild(comments, keep=True)

    def _row_for(self, key: tuple | None) -> int | None:
        """The row holding a key's line. A split row holds two lines, so the key may be the other one's."""
        if key is None:
            return None
        for i, row in enumerate(self.rows):
            if row.key() == key or (key[0] == "line" and any(ln["index"] == key[1] for ln in row.lines())):
                return i
        return None

    def _rebuild(self, comments: list[dict], keep: bool) -> None:
        old_key = self.current.key() if keep and self.current else None
        range_start_key = (
            self.rows[self.range_start].key()
            if self.range_start is not None and self.range_start < len(self.rows)
            else None
        )
        old_cursor, old_scroll = self.cursor, self.scroll_offset.y
        found = self.find.identity(self.rows)
        self._comments, self._split = comments, self.split_active
        self.rows = build_rows(self._data, comments, self._split)
        self.range_start = self._row_for(range_start_key)
        self.hover = None
        self._wrap_w = 0
        self._layout()
        self.cursor = self._find_cursor(old_key, old_cursor)
        self.find.search(self.rows, self.find.query, near=self.cursor, keep=found)
        self.scroll_to(y=min(old_scroll, max(self._tops[-1] if self._tops else 0, 0)) if keep else 0, animate=False)
        self._reveal(self.cursor)
        self.refresh()
        self._sync_hints()

    def _find_cursor(self, key: tuple | None, fallback: int) -> int:
        found = self._row_for(key)
        if found is not None:
            return found
        if key is not None:
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
        width = self.size.width
        if not self._split:
            width = max(self._gutter_w + min(self._code_w, MAX_CODE_COLS) + 2, width)
        self.virtual_size = Size(width, top)

    def on_resize(self, event: events.Resize) -> None:
        if not self.rows:
            return
        if self.split_active != self._split:
            self._rebuild(self._comments, keep=True)
            if self.split_wanted:
                self.app.notify(f"Pane too narrow for split view (needs {SPLIT_MIN_WIDTH} columns), showing unified")
        elif self._split:
            self._layout()
        elif max(event.size.width - self._gutter_w - 4, 24) != self._wrap_w:
            self._layout()
            self._reveal(self.cursor)

    def toggle_split(self) -> str:
        """Flips unified and split. Returns a notice when the pane is too narrow to show split."""
        if self.readonly:
            return "Split view is for diff files"
        self.split_wanted = not self.split_wanted
        self.side = None
        if self.split_active != self._split:
            self._rebuild(self._comments, keep=True)
        if self.split_wanted and not self.split_active:
            return f"Pane too narrow for split view (needs {SPLIT_MIN_WIDTH} columns), staying unified"
        return "Split view" if self.split_wanted else "Unified view"

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

    def _set_cursor(self, index: int, top: bool = False, side: str | None = None) -> None:
        if not self.rows:
            return
        self.cursor = max(0, min(index, len(self.rows) - 1))
        self.side = side
        if top:
            self.scroll_to(y=max(self.rows[self.cursor].top - 1, 0), animate=False)
        self._reveal(self.cursor)
        self.refresh()
        self._sync_hints()

    def action_move(self, delta: int) -> None:
        self._set_cursor(self.cursor + delta)

    def action_page(self, fraction: float) -> None:
        y = self.rows[self.cursor].top + int(self.size.height * fraction) if self.rows else 0
        self._set_cursor(self._row_at(max(y, 0)))

    def action_goto_edge(self, end: int) -> None:
        self._set_cursor(len(self.rows) - 1 if end else 0)

    def action_extend(self, delta: int) -> None:
        if self.range_start is None and not self.readonly and self.current and self.current.kind == "line":
            self.range_start = self.cursor
        self._set_cursor(self.cursor + delta, side=self.side)

    def action_swap_side(self) -> None:
        """Split view: moves the cursor between the old and new line of a replaced pair."""
        if self.current and self.current.paired():
            self.side = "old" if self.side_of(self.current, self.side) == "new" else "new"
            self.refresh()

    def side_of(self, row: Row, wanted: str | None) -> str:
        if row.old is None:
            return "new"
        if row.new is None:
            return "old"
        return wanted if wanted and row.paired() else "new"

    def target(self, row: Row) -> dict | None:
        """The line a comment on this row is stored against."""
        if row.old is None and row.new is None:
            return row.line
        return row.old if self.side_of(row, self.side) == "old" else row.new

    def start_selection(self) -> None:
        if self.current and self.current.kind == "line":
            self.range_start = self.cursor
            self.refresh()
            self._sync_hints()

    def clear_selection(self) -> None:
        if self.range_start is not None:
            self.range_start = None
            self.refresh()
            self._sync_hints()

    def is_selected(self, index: int) -> bool:
        return self.range_start is not None and min(self.range_start, self.cursor) <= index <= max(
            self.range_start, self.cursor
        )

    def selected_lines(self) -> list[dict]:
        """The diff lines between the range start and the cursor, or none without a selection."""
        if self.range_start is None:
            return []
        lo, hi = sorted((self.range_start, self.cursor))
        lines = [self.target(r) for r in self.rows[lo : hi + 1] if r.kind == "line"]
        # Split rows pair a remove with an add, so row order is not diff order.
        return sorted(lines, key=lambda ln: ln["index"])

    @property
    def context(self) -> str:
        """What the user can do next: range, thread, line, none, or readonly for a file outside the diff."""
        if self.readonly:
            return "readonly"
        if self.range_start is not None:
            return "range"
        return {"line": "line", "thread": "thread"}.get(self.current.kind if self.current else "", "none")

    def _sync_hints(self) -> None:
        state = (self.context, len(self.selected_lines()))
        if state != self._hints:
            self._hints = state
            self.refresh_bindings()

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

    def goto_line(self, number: int) -> bool:
        """Puts the cursor on a line of the new file. Returns False when the diff does not show it."""
        shown = [
            (abs(int(ln["new_num"]) - number), i)
            for i, row in enumerate(self.rows)
            for ln in [row.new or row.line]
            if row.kind == "line" and ln and ln["new_num"]
        ]
        if not shown:
            return False
        distance, index = min(shown)
        self._set_cursor(index, top=True)
        return distance == 0

    def set_find(self, query: str) -> None:
        self.find.search(self.rows, query, near=self.cursor)
        self.refresh()
        self._show_match()

    def step_find(self, direction: int) -> None:
        if self.find.step(direction):
            self._show_match()

    def _show_match(self) -> None:
        if not 0 <= self.find.current < len(self.find.matches):
            return
        row, side, start, end = self.find.matches[self.find.current]
        self._set_cursor(row, side=side if side == "old" else None)
        if not self._split:
            left, right = self._gutter_w + start, self._gutter_w + end
            x, width = self.scroll_offset.x, self.size.width
            if left < x or right > x + width:
                self.scroll_to(x=max(left - width // 3, 0), animate=False)

    def _side_at(self, x: int) -> str | None:
        if not self._split:
            return None
        return "old" if x < 1 + self.split_widths()[0] else "new"

    def _in_gutter(self, x: int) -> bool:
        if not self._split:
            return x + self.scroll_offset.x < self._gutter_w - 1
        left, nw = self.split_widths()[0], self.number_width
        return x < nw + 2 or 1 + left <= x < 3 + left + nw

    def _row_under(self, y: int) -> int | None:
        """The row at a widget-relative y, or None below the last row."""
        y += self.scroll_offset.y
        return self._row_at(y) if self.rows and 0 <= y < self.virtual_size.height else None

    def _refresh_rows(self, *indexes: int | None) -> None:
        view = Region(0, 0, self.size.width, self.size.height)
        shown = (self.rows[i] for i in indexes if i is not None and i < len(self.rows))
        regions = [view.intersection(Region(0, r.top - self.scroll_offset.y, view.width, r.height)) for r in shown]
        self.refresh(*[r for r in regions if r])

    def _hoverable(self, index: int | None) -> int | None:
        return index if index is not None and not self.readonly and self.rows[index].kind == "line" else None

    def _set_hover(self, index: int | None, side: str | None = None) -> None:
        index = self._hoverable(index)
        if index != self.hover or side != self.hover_side:
            old, self.hover, self.hover_side = self.hover, index, side
            self._refresh_rows(old, index)

    def clear_hover(self) -> None:
        self._set_hover(None)

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        """Scrolling moves rows under a still pointer, so the hover follows it."""
        super().watch_scroll_y(old_value, new_value)
        if self.hover is not None:
            pointer = self.app.mouse_position
            inside = self.content_region.contains_point(pointer)
            self.hover = self._hoverable(self._row_under(pointer.y - self.content_region.y)) if inside else None

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self._press is not None:
            index = self._row_under(max(0, min(event.y, self.size.height - 1)))
            index = len(self.rows) - 1 if index is None else index
            self.range_start = self._press if index != self._press else None
            self._set_cursor(index, side=self._side_at(event.x))
        else:
            self._set_hover(self._row_under(event.y), self._side_at(event.x))

    def on_leave(self, _event: events.Leave) -> None:
        self.clear_hover()

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._swallow_click = False
        index = self._row_under(event.y)
        if (
            event.button == 1
            and not self.readonly
            and index is not None
            and self.rows[index].kind == "line"
            and self._in_gutter(event.x)
        ):
            self._press = index
            self.side = self._side_at(event.x)
            self.capture_mouse()
            event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        press, self._press = self._press, None
        if press is None:
            return
        self.release_mouse()
        self._swallow_click = True
        if self.range_start is None:
            self._set_cursor(press, side=self.side)
        self.post_message(self.Activated())

    def on_click(self, event: events.Click) -> None:
        if self._swallow_click or not self.rows:
            self._swallow_click = False
            return
        index = self._row_at(event.y + self.scroll_offset.y)
        again = index == self.cursor
        self._set_cursor(index, side=self._side_at(event.x))
        if again and not self.readonly and self.rows[index].kind in ("line", "thread"):
            self.post_message(self.Activated())

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        width = self.size.width
        bg = self.palette.bg
        y += scroll_y
        if not self.rows or y >= self.virtual_size.height:
            return Strip.blank(width, style(None, bg))
        index = self._row_at(y)
        row = self.rows[index]
        active = index == self.cursor
        if row.kind == "thread":
            strips = self._thread_strips(row, active, self._wrap_w)
            strip = strips[min(y - row.top, len(strips) - 1)]
            base = self.palette.comment_header_bg if active else self.palette.comment_bg
        elif row.kind == "line":
            strip, base = (split_strip if self._split else unified_strip)(self, index, row, active)
        else:
            strip, base = self._flat_strip(index, row, active)
        total = max(self.virtual_size.width, width)
        return strip.extend_cell_length(total, style(None, base)).crop(scroll_x, scroll_x + width)

    def _flat_strip(self, index: int, row: Row, active: bool) -> tuple[Strip, str]:
        p = self.palette
        lit = active or self.is_selected(index)
        mark = "▸" if active else "▌" if row.kind == "line" and lit else " "
        base = p.hover_bg if lit else p.hunk_bg if row.kind == "hunk" else p.bg
        fg = p.hunk_fg if row.kind == "hunk" else p.fg_muted
        return Strip([Segment(f"{mark}{row.text}", style(fg, base))]), base

    def _thread_strips(self, row: Row, active: bool, wrap_w: int) -> list[Strip]:
        cached = row.strips.get(active)
        if cached is not None:
            return cached
        p = self.palette
        c = row.thread
        bg = p.comment_header_bg if active else p.comment_bg
        resolved = not is_comment_open(c)
        pad = " " * (self._gutter_w - 1)
        bar = ("▌", style(p.comment_accent, bg))
        out: list[Strip] = []

        def emit(text: str, fg: str, bold: bool = False) -> None:
            out.append(Strip([Segment(pad), Segment(*bar), Segment(f" {text}", style(fg, bg, bold=bold))]))

        def emit_wrapped(text: str, fg: str, first: str = "", rest: str = "") -> None:
            lines = [ln for part in text.split("\n") for ln in (textwrap.wrap(part, wrap_w - len(first)) or [""])]
            for i, ln in enumerate(lines):
                emit((first if i == 0 else rest) + ln, fg)

        who = c.get("author") or "user"
        head = f"{who}" + (f" [{c['category']}]" if c.get("category") else "")
        end = c.get("sel_end_index")
        if end not in (None, c.get("line_index")) and self._nums.get(end):
            head += f"  lines {span(self._nums.get(c['line_index'], '?'), self._nums[end])}"
        head += "  ✓ resolved" if resolved else ""
        emit(head, p.fg_muted if resolved else p.accent, bold=True)
        emit_wrapped(c.get("comment", ""), p.fg_muted if resolved else p.fg)
        if c.get("suggestion"):
            emit("suggestion:", p.fg_muted)
            emit_wrapped(c["suggestion"], add_fg(p), first="+ ", rest="+ ")
        for r in c.get("replies", []):
            who = r.get("author") or r.get("author_type", "agent")
            emit_wrapped(f"{who}: {r.get('text', '')}", p.fg_muted if resolved else p.fg, first="↳ ", rest="  ")
        row.strips[active] = out
        return out
