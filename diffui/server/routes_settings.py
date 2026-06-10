from __future__ import annotations

import subprocess

from fastapi import APIRouter

from diffui.git_utils import get_repo_root, load_session, save_session, save_settings
from diffui.server.models import EditorOpen, SessionUpdate, SettingsUpdate
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
        "agent_cli": app_state.agent_cli,
        "font_size": app_state.font_size,
        "word_wrap": app_state.word_wrap,
        "keybindings": app_state.keybindings,
    }


@router.put("/settings")
def update_settings(body: SettingsUpdate):
    if body.theme_index is not None:
        idx = body.theme_index
        if 0 <= idx < len(ALL_THEMES):
            app_state.theme_index = idx
            set_current_theme(ALL_THEMES[idx])
    if body.editor is not None:
        app_state.editor = body.editor
    if body.view_mode is not None:
        app_state.view_mode = body.view_mode
    if body.user_name is not None:
        app_state.user_name = body.user_name
    if body.agent_cli is not None:
        app_state.agent_cli = body.agent_cli
    if body.font_size is not None:
        app_state.font_size = body.font_size
    if body.word_wrap is not None:
        app_state.word_wrap = body.word_wrap
    if body.keybindings is not None:
        app_state.keybindings = body.keybindings

    save_settings(
        {
            "theme": ALL_THEMES[app_state.theme_index].name,
            "editor": app_state.editor,
            "view_mode": app_state.view_mode,
            "user_name": app_state.user_name,
            "agent_cli": app_state.agent_cli,
            "font_size": app_state.font_size,
            "word_wrap": app_state.word_wrap,
            "keybindings": app_state.keybindings,
        }
    )
    return {"ok": True, "css": generate_css_vars(app_state.theme)}


@router.post("/editor/open")
def open_in_editor(body: EditorOpen):
    full_path = get_repo_root() / body.file_path
    editor = app_state.editor

    if editor in ("code", "cursor"):
        cmd = [editor, "--goto", f"{full_path}:{body.line_num}"]
    elif editor in ("vim", "nvim"):
        cmd = [editor, f"+{body.line_num}", str(full_path)]
    else:
        cmd = [editor, str(full_path)]

    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"ok": True}


@router.get("/session")
def get_session():
    return load_session()


@router.put("/session")
def update_session(body: SessionUpdate):
    session = load_session()
    session.update(body.model_dump(exclude_none=True))
    save_session(session)
    return {"ok": True}
