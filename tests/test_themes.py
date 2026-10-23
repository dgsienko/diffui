from __future__ import annotations

from diffui.themes import ALL_THEMES, DEFAULT_THEME


class TestThemeDefinitions:
    def test_unique_names(self):
        names = [t.name for t in ALL_THEMES]
        assert len(names) == len(set(names))

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


class TestDefaultTheme:
    def test_no_saved_theme_uses_default_and_saved_theme_wins(self, monkeypatch):
        from diffui.server import state

        monkeypatch.setattr(state, "load_settings", lambda: {})
        assert state.AppState().theme is DEFAULT_THEME
        monkeypatch.setattr(state, "load_settings", lambda: {"theme": "Dracula"})
        assert state.AppState().theme.name == "Dracula"
