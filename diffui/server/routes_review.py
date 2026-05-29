from __future__ import annotations

from fastapi import APIRouter

from diffui.git_utils import get_file_mtime, save_reviewed
from diffui.server.state import app_state

router = APIRouter(prefix="/api")


@router.get("/reviewed")
def get_reviewed():
    return app_state.reviewed


@router.post("/reviewed/{path:path}")
def toggle_reviewed(path: str):
    if path in app_state.reviewed:
        del app_state.reviewed[path]
        save_reviewed(app_state.reviewed)
        return {"reviewed": False}
    app_state.reviewed[path] = get_file_mtime(path)
    save_reviewed(app_state.reviewed)
    return {"reviewed": True}
