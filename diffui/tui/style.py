from __future__ import annotations

from functools import lru_cache

from pygments.token import Token
from rich.color import Color
from rich.segment import Segment
from rich.style import Style

from diffui.diff import token_color
from diffui.themes.theme import Theme

Tokens = list[tuple[str, str | None]]
Span = tuple[int, int, bool]


@lru_cache(maxsize=512)
def style(fg: str | None, bg: str, bold: bool = False) -> Style:
    return Style(color=Color.parse(fg) if fg else None, bgcolor=Color.parse(bg), bold=bold or None)


def span(first: str, last: str) -> str:
    return f"{first}\N{EN DASH}{last}"


def add_fg(theme: Theme) -> str:
    return token_color(Token.Literal.String, theme.syntax) or theme.fg


def marker(active: bool, selected: bool) -> str:
    return "▸" if active else "▌" if selected else " "


def prefix_fg(p: Theme, kind: str) -> str:
    return {"add": add_fg(p), "remove": p.delete_fg}.get(kind, p.gutter_fg)


def tint(p: Theme, kind: str, lit: bool) -> str:
    if kind == "add":
        return p.add_hover if lit else p.add_bg
    if kind == "remove":
        return p.remove_hover if lit else p.remove_bg
    return p.hover_bg if lit else p.bg


def code_segments(tokens: Tokens, spans: list[Span], p: Theme, base: str) -> list[Segment]:
    """Token segments with the find matches drawn over them. `spans` are sorted, non-overlapping column ranges."""
    if not spans:
        return [Segment(text, style(color or p.fg, base)) for text, color in tokens]
    out: list[Segment] = []
    pos = next_span = 0
    for text, color in tokens:
        start, end = pos, pos + len(text)
        pos = end
        plain = style(color or p.fg, base)
        cur = start
        while cur < end:
            while next_span < len(spans) and spans[next_span][1] <= cur:
                next_span += 1
            if next_span == len(spans) or spans[next_span][0] >= end:
                out.append(Segment(text[cur - start :], plain))
                break
            lo, hi, current = spans[next_span]
            if lo > cur:
                out.append(Segment(text[cur - start : lo - start], plain))
                cur = lo
            stop = min(hi, end)
            found = style(p.bg, p.warn_fg, bold=True) if current else style(p.warn_fg, p.warn_hover, bold=True)
            out.append(Segment(text[cur - start : stop - start], found))
            cur = stop
    return out
