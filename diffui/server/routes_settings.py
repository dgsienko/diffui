from __future__ import annotations

import subprocess

from fastapi import APIRouter

from diffui.git_utils import get_repo_root, save_settings
from diffui.server.state import app_state
from diffui.server.theme_css import generate_css_vars
from diffui.themes import ALL_THEMES, set_current_theme

router = APIRouter(prefix="/api")


@router.get("/settings")
def get_settings():
    return {
        "theme": ALL_THEMES[app_state.theme_index].name,
        "theme_index": app_state.theme_index,
        "editor": app_state.editor,
        "view_mode": app_state.view_mode,
        "user_name": app_state.user_name,
    }


@router.put("/settings")
def update_settings(body: dict):
    if "theme_index" in body:
        idx = body["theme_index"]
        if 0 <= idx < len(ALL_THEMES):
            app_state.theme_index = idx
            set_current_theme(ALL_THEMES[idx])
    if "editor" in body:
        app_state.editor = body["editor"]
    if "view_mode" in body:
        app_state.view_mode = body["view_mode"]
    if "user_name" in body:
        app_state.user_name = body["user_name"]

    save_settings(
        {
            "theme": ALL_THEMES[app_state.theme_index].name,
            "editor": app_state.editor,
            "view_mode": app_state.view_mode,
            "user_name": app_state.user_name,
        }
    )
    return {"ok": True, "css": generate_css_vars(app_state.theme)}


@router.post("/editor/open")
def open_in_editor(body: dict):
    file_path = body["file_path"]
    line_num = body.get("line_num", 1)
    full_path = get_repo_root() / file_path
    editor = app_state.editor

    if editor in ("code", "cursor"):
        cmd = [editor, "--goto", f"{full_path}:{line_num}"]
    elif editor in ("vim", "nvim"):
        cmd = [editor, f"+{line_num}", str(full_path)]
    else:
        cmd = [editor, str(full_path)]

    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True}
