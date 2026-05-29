from __future__ import annotations

from fastapi import APIRouter

from diffui.git_utils import (
    current_branch,
    get_main_branch,
    get_repo_root,
    repo_has_changes,
    set_active_repo,
)
from diffui.server.state import app_state

router = APIRouter(prefix="/api")


import time as _time

_repo_changes_cache: dict[str, tuple[bool, float]] = {}
_REPO_CACHE_TTL = 15


def _cached_repo_has_changes(repo_root) -> bool:
    key = str(repo_root)
    cached = _repo_changes_cache.get(key)
    now = _time.monotonic()
    if cached and now - cached[1] < _REPO_CACHE_TTL:
        return cached[0]
    result = repo_has_changes(repo_root)
    _repo_changes_cache[key] = (result, now)
    return result


@router.get("/repos")
def list_repos():
    return [
        {
            "index": i,
            "name": r.name,
            "path": str(r),
            "has_changes": _cached_repo_has_changes(r),
            "active": i == app_state.active_repo_index,
        }
        for i, r in enumerate(app_state.repos)
    ]


@router.post("/repo/switch")
async def switch_repo(body: dict):
    index = body.get("index", 0)
    if index < 0 or index >= len(app_state.repos):
        return {"error": "Invalid index"}
    app_state.active_repo_index = index
    set_active_repo(app_state.repos[index])
    app_state.reload_repo_state()
    from diffui.server.routes_diff import clear_diff_cache

    clear_diff_cache()
    return {"ok": True, "branch": current_branch()}


@router.get("/branch")
def get_branch():
    from diffui.git_utils import get_head_sha, get_remote_url

    return {
        "name": current_branch(),
        "main_branch": get_main_branch(),
        "merge_base": app_state.merge_base,
        "repo_name": get_repo_root().name,
        "remote_url": get_remote_url(),
        "head_sha": get_head_sha(),
    }


@router.get("/commits")
def list_commits():
    return [{"sha": c.sha, "message": c.message, "author": c.author, "files": c.files} for c in app_state.commits]
