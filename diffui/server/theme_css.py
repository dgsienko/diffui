from __future__ import annotations

from dataclasses import fields

from diffui.themes.theme import Theme

_SKIP_FIELDS = {"name", "syntax"}


def generate_css_vars(theme: Theme) -> str:
    lines = [":root {"]
    for f in fields(theme):
        if f.name in _SKIP_FIELDS:
            continue
        value = getattr(theme, f.name)
        css_name = f.name.replace("_", "-")
        lines.append(f"  --{css_name}: {value};")
    lines.append("}")
    return "\n".join(lines)
