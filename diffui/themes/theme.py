from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Theme:
    name: str
    bg: str
    bg_dark: str
    fg: str
    fg_muted: str
    border: str
    accent: str
    add_bg: str
    add_hover: str
    remove_bg: str
    remove_hover: str
    hunk_bg: str
    hunk_fg: str
    gutter_fg: str
    gutter_sep: str
    hover_bg: str
    comment_bg: str
    comment_header_bg: str
    comment_accent: str
    delete_bg: str
    delete_hover: str
    delete_fg: str
    warn_bg: str
    warn_hover: str
    warn_fg: str
    syntax: dict = field(default_factory=dict)
