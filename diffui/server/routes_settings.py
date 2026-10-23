from __future__ import annotations

import subprocess

from fastapi import APIRouter

from diffui.git_utils import load_session, repo_path, save_session, save_settings
from diffui.server.models import EditorOpen, SessionUpdate, SettingsUpdate
from diffui.server.state import app_state
from diffui.server.theme_css import generate_css_vars
from diffui.themes import ALL_THEMES

router = APIRouter(prefix="/api")


@router.get("/settings")
def get_settings():
    return {**app_state.settings(), "theme_index": app_state.theme_index}


@router.put("/settings")
def update_settings(body: SettingsUpdate):
    updates = body.model_dump(exclude_none=True)
    idx = updates.pop("theme_index", None)
    if idx is not None and 0 <= idx < len(ALL_THEMES):
        app_state.theme_index = idx
    for key, value in updates.items():
        setattr(app_state, key, value)

    save_settings(app_state.settings())
    return {"ok": True, "css": generate_css_vars(app_state.theme)}


@router.post("/editor/open")
def open_in_editor(body: EditorOpen):
    full_path = repo_path(body.file_path)
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
