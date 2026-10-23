from __future__ import annotations

from typing import TYPE_CHECKING

from rich.segment import Segment
from textual.strip import Strip

from diffui.tui.rows import Row
from diffui.tui.style import code_segments, marker, prefix_fg, style, tint

if TYPE_CHECKING:
    from diffui.tui.diffview import DiffView


def split_strip(view: DiffView, index: int, row: Row, active: bool) -> tuple[Strip, str]:
    p = view.palette
    lit = active or view.is_selected(index)
    left_w, right_w = view.split_widths()
    hover = view.side_of(row, view.hover_side) if index == view.hover else None
    target = view.side_of(row, view.side) if active and row.paired() else None
    left = _cell(view, index, row, "old", left_w, lit, hover == "old", target == "old")
    right = _cell(view, index, row, "new", right_w, lit, hover == "new", target == "new")
    left_base = tint(p, row.old["type"], lit) if row.old else p.bg_dark
    mark = Strip([Segment(marker(active, lit), style(p.gutter_fg, left_base))])
    divider = Strip([Segment("│", style(p.gutter_sep, p.bg))])
    return Strip.join([mark, left, divider, right]), p.bg


def _cell(view: DiffView, index: int, row: Row, side: str, width: int, lit: bool, hover: bool, target: bool) -> Strip:
    p = view.palette
    line = row.old if side == "old" else row.new
    if line is None:
        return Strip.blank(width, style(None, p.bg_dark))
    kind = line["type"]
    base = tint(p, kind, lit)
    nw = view.number_width
    number = "[+]" if hover else line["old_num" if side == "old" else "new_num"] or ""
    number_fg = p.accent if hover or target else p.gutter_fg
    segments = [
        Segment(f"{number:>{nw}} ", style(number_fg, base, bold=hover or target)),
        Segment(line["text"][:1], style(prefix_fg(p, kind), base, bold=True)),
        *code_segments(row.tokens_of(line, view.lexer, p.syntax), view.find.spans(index, side), p, base),
    ]
    return Strip(segments).adjust_cell_length(width, style(None, base))
