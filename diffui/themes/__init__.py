from diffui.themes.definitions import ALL_THEMES
from diffui.themes.theme import Theme

DEFAULT_THEME: Theme = ALL_THEMES[0]
_current_theme: Theme = DEFAULT_THEME


def get_current_theme() -> Theme:
    return _current_theme


def set_current_theme(theme: Theme) -> None:
    global _current_theme
    _current_theme = theme


__all__ = [
    "ALL_THEMES",
    "DEFAULT_THEME",
    "Theme",
    "get_current_theme",
    "set_current_theme",
]
