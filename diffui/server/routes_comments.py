from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter

from diffui.git_utils import get_repo_root, save_comments
from diffui.server.state import app_state

router = APIRouter(prefix="/api")


def _find_comment(file_path: str, comment_id: str) -> dict | None:
    for c in app_state.comments.get(file_path, []):
        if c.get("id") == comment_id:
            return c
    return None


@router.get("/comments")
def get_comments():
    return app_state.comments


@router.post("/comments")
def add_comment(body: dict):
    file_path = body["file_path"]
    if file_path not in app_state.comments:
        app_state.comments[file_path] = []
    app_state.comments[file_path].append(
        {
            "id": str(uuid.uuid4()),
            "file_path": file_path,
            "line_text": body.get("line_text", ""),
            "line_index": body["line_index"],
            "file_line_num": body.get("file_line_num"),
            "comment": body["comment"],
            "author": body.get("author", app_state.user_name),
            "author_type": body.get("author_type", "user"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": body.get("status", "open"),
            "category": body.get("category", ""),
            "suggestion": body.get("suggestion", ""),
        }
    )
    save_comments(app_state.comments)
    return {"ok": True}


@router.put("/comments/{file_path:path}/{comment_id}")
def edit_comment(file_path: str, comment_id: str, body: dict):
    c = _find_comment(file_path, comment_id)
    if c:
        c["comment"] = body["comment"]
        save_comments(app_state.comments)
    return {"ok": True}


@router.delete("/comments/{file_path:path}/{comment_id}")
def delete_comment(file_path: str, comment_id: str):
    file_comments = app_state.comments.get(file_path, [])
    app_state.comments[file_path] = [c for c in file_comments if c.get("id") != comment_id]
    if not app_state.comments[file_path]:
        del app_state.comments[file_path]
    save_comments(app_state.comments)
    return {"ok": True}


@router.post("/comments/{file_path:path}/{comment_id}/resolve")
def resolve_comment(file_path: str, comment_id: str):
    c = _find_comment(file_path, comment_id)
    if c:
        current = c.get("status", "open")
        c["status"] = "open" if current == "resolved" else "resolved"
        save_comments(app_state.comments)
    return {"ok": True}


@router.post("/comments/{file_path:path}/{comment_id}/reply")
def reply_to_comment(file_path: str, comment_id: str, body: dict):
    c = _find_comment(file_path, comment_id)
    if c:
        if "replies" not in c:
            c["replies"] = []
        c["replies"].append(
            {
                "text": body["text"],
                "author": body.get("author", app_state.user_name),
                "author_type": body.get("author_type", "user"),
            }
        )
        save_comments(app_state.comments)
    return {"ok": True}


@router.post("/comments/{file_path:path}/{comment_id}/apply")
def apply_suggestion(file_path: str, comment_id: str):

    c = _find_comment(file_path, comment_id)
    if not c or not c.get("suggestion"):
        return {"ok": False, "error": "No suggestion to apply"}
    line_num = c.get("file_line_num")
    if not line_num:
        return {"ok": False, "error": "No line number"}
    full_path = get_repo_root() / file_path
    if not full_path.exists():
        return {"ok": False, "error": "File not found"}
    lines = full_path.read_text().splitlines(keepends=True)
    idx = line_num - 1
    if idx < 0 or idx >= len(lines):
        return {"ok": False, "error": "Line out of range"}
    suggestion = c["suggestion"]
    if not suggestion.endswith("\n"):
        suggestion += "\n"
    lines[idx] = suggestion
    full_path.write_text("".join(lines))
    c["status"] = "resolved"
    save_comments(app_state.comments)
    return {"ok": True}
