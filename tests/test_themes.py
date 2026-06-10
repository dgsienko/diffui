from __future__ import annotations

from diffui.themes import (
    ALL_THEMES,
    CATPPUCCIN_MOCHA,
    get_current_theme,
    set_current_theme,
)


class TestThemeDefinitions:
    def test_all_themes_count(self):
        assert len(ALL_THEMES) == 15

    def test_all_themes_have_names(self):
        for theme in ALL_THEMES:
            assert theme.name
            assert isinstance(theme.name, str)

    def test_all_themes_have_syntax(self):
        for theme in ALL_THEMES:
            assert theme.syntax
            assert isinstance(theme.syntax, dict)

    def test_unique_names(self):
        names = [t.name for t in ALL_THEMES]
        assert len(names) == len(set(names))

    def test_catppuccin_is_first(self):
        assert ALL_THEMES[0] is CATPPUCCIN_MOCHA

    def test_all_color_fields_are_hex(self):
        color_fields = [
            "bg",
            "bg_dark",
            "fg",
            "fg_muted",
            "border",
            "accent",
            "add_bg",
            "add_hover",
            "remove_bg",
            "remove_hover",
            "hunk_bg",
            "hunk_fg",
            "gutter_fg",
            "gutter_sep",
            "hover_bg",
            "comment_bg",
            "comment_header_bg",
            "comment_accent",
            "delete_bg",
            "delete_hover",
            "delete_fg",
            "warn_bg",
            "warn_hover",
            "warn_fg",
        ]
        for theme in ALL_THEMES:
            for field_name in color_fields:
                value = getattr(theme, field_name)
                assert value.startswith("#"), f"{theme.name}.{field_name} = {value!r}"
                assert len(value) == 7, f"{theme.name}.{field_name} = {value!r}"


class TestThemeState:
    def test_current_theme_has_valid_name(self):
        theme = get_current_theme()
        assert theme.name in [t.name for t in ALL_THEMES]

    def test_set_and_get(self):
        original = get_current_theme()
        try:
            new_theme = ALL_THEMES[-1]
            set_current_theme(new_theme)
            assert get_current_theme() is new_theme
        finally:
            set_current_theme(original)
