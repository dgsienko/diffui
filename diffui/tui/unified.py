from __future__ import annotations

from typing import TYPE_CHECKING

from rich.segment import Segment
from textual.strip import Strip

from diffui.tui.rows import Row
from diffui.tui.style import add_fg, code_segments, style, tint

if TYPE_CHECKING:
    from diffui.tui.diffview import DiffView


def unified_strip(view: DiffView, index: int, row: Row, active: bool) -> tuple[Strip, str]:
    p = view.palette
    selected = view.is_selected(index)
    mark = "▸" if active else "▌" if selected else " "
    line = row.line
    kind = line["type"]
    base = tint(p, kind, active or selected)
    d = view.digits
    prefix_fg = {"add": add_fg(p), "remove": p.delete_fg}.get(kind, p.gutter_fg)
    if index == view.hover:
        numbers = Segment(f"{'[+]':>{2 * d + 1}}", style(p.accent, base, bold=True))
    else:
        numbers = Segment(f"{line['old_num'] or '':>{d}} {line['new_num'] or '':>{d}}", style(p.gutter_fg, base))
    segments = [
        Segment(mark, style(p.gutter_fg, base)),
        numbers,
        Segment(" ", style(p.gutter_fg, base)),
        Segment(line["text"][:1], style(prefix_fg, base, bold=True)),
        *code_segments(row.tokens_of(line, view.lexer, p.syntax), view.find.spans(index, "u"), p, base),
    ]
    return Strip(segments), base
