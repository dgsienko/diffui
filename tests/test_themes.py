from __future__ import annotations

import re
from dataclasses import MISSING, fields

from diffui.server.theme_css import generate_css_vars
from diffui.themes import ALL_THEMES, DEFAULT_THEME, Theme
from diffui.themes.definitions import CATPPUCCIN_MOCHA


class TestThemeDefinitions:
    def test_unique_names(self):
        names = [t.name for t in ALL_THEMES]
        assert len(names) == len(set(names))

    def test_required_color_fields_are_hex(self):
        required = [
            f.name for f in fields(Theme) if f.name != "name" and f.default is MISSING and f.default_factory is MISSING
        ]
        for theme in ALL_THEMES:
            for field_name in required:
                value = getattr(theme, field_name)
                assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), f"{theme.name}.{field_name} = {value!r}"


def test_css_vars_hyphenate_each_color_field_and_skip_name_and_syntax():
    css = generate_css_vars(CATPPUCCIN_MOCHA)
    assert css.startswith(":root {") and css.endswith("}")
    assert f"--bg: {CATPPUCCIN_MOCHA.bg};" in css
    assert f"--bg-dark: {CATPPUCCIN_MOCHA.bg_dark};" in css
    assert "--bg_dark" not in css
    assert "--name:" not in css
    assert "--syntax:" not in css


class TestDefaultTheme:
    def test_no_saved_theme_uses_default_and_saved_theme_wins(self, monkeypatch):
        from diffui.server import state

        monkeypatch.setattr(state, "load_settings", lambda: {})
        assert state.AppState().theme is DEFAULT_THEME
        monkeypatch.setattr(state, "load_settings", lambda: {"theme": "Dracula"})
        assert state.AppState().theme.name == "Dracula"
