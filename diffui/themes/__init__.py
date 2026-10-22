from diffui.themes.definitions import ALL_THEMES, CATPPUCCIN_MOCHA, GRAPHITE
from diffui.themes.theme import Theme

_current_theme: Theme = GRAPHITE


def get_current_theme() -> Theme:
    return _current_theme


def set_current_theme(theme: Theme) -> None:
    global _current_theme
    _current_theme = theme


__all__ = [
    "ALL_THEMES",
    "CATPPUCCIN_MOCHA",
    "GRAPHITE",
    "Theme",
    "get_current_theme",
    "set_current_theme",
]
