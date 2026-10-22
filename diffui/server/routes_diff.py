from __future__ import annotations

import threading
from fnmatch import fnmatch

from fastapi import APIRouter

from diffui.git_utils import (
    get_commit_diff,
    get_file_mtime,
    get_full_diff,
    get_repo_root,
    get_tree_diff,
    get_working_diff,
    is_comment_open,
    repo_relative,
    short_name,
)
from diffui.server.highlight import parse_diff_to_json
from diffui.server.state import app_state

LAST_TURN = "last-turn"

router = APIRouter(prefix="/api")

_diff_cache: dict[tuple[str, str, str, str, float], str] = {}
_cache_lock = threading.Lock()
_MAX_CACHE = 128


def _find_commit(view: str):
    return next((c for c in app_state.commits if c.sha == view), None)


def clear_diff_cache() -> None:
    with _cache_lock:
        _diff_cache.clear()


def _get_diff(path: str, view: str, context: int = 3, ignore_whitespace: bool = False) -> str:
    repo_id = str(get_repo_root())
    merge_base = app_state.merge_base
    mtime = get_file_mtime(path)
    ws_flag = "w" if ignore_whitespace else ""
    turn = app_state.last_turn if view == LAST_TURN else None
    cache_view = f"{view}@{turn.base}" if turn else view
    cache_key = (repo_id, merge_base, path, f"{cache_view}:c{context}:{ws_flag}", mtime)

    with _cache_lock:
        if cache_key in _diff_cache:
            return _diff_cache[cache_key]

    if view == "all":
        result = get_full_diff(merge_base, path, context, ignore_whitespace=ignore_whitespace)
    elif view == "working":
        result = get_working_diff(path, context, ignore_whitespace=ignore_whitespace)
    elif view == LAST_TURN:
        result = get_tree_diff(turn.base, turn.now, path, context, ignore_whitespace=ignore_whitespace) if turn else ""
    elif (commit := _find_commit(view)) is not None:
        result = get_commit_diff(commit.sha, path, context, ignore_whitespace=ignore_whitespace)
    else:
        # An unknown view would reach git as a revision, where a leading "--" is an option.
        result = ""

    with _cache_lock:
        if cache_key in _diff_cache:
            return _diff_cache[cache_key]
        stale = next((k for k in _diff_cache if k[2] == path and k[3] == f"{cache_view}:c{context}:{ws_flag}"), None)
        if stale is not None:
            del _diff_cache[stale]
        if len(_diff_cache) >= _MAX_CACHE:
            try:
                del _diff_cache[next(iter(_diff_cache))]
            except StopIteration:
                pass
        _diff_cache[cache_key] = result

    return result


_HIGH_RISK_PATTERNS = {"migration", "alembic", "schema", "deploy", "infra", "terraform", ".env"}
_CONFIG_EXTS = {".yml", ".yaml", ".toml", ".json", ".cfg", ".ini", ".env"}


def _score_risk(path: str, adds: int, dels: int) -> tuple[int, str, list[str]]:
    score = 0
    reasons: list[str] = []
    name_lower = path.lower()
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""

    if any(p in name_lower for p in _HIGH_RISK_PATTERNS):
        score += 3
        reasons.append("infra/migration")
    if ext in _CONFIG_EXTS:
        score += 2
        reasons.append("config")
    if dels > 50:
        score += 2
        reasons.append("large deletion")
    elif dels > 20:
        score += 1
    if adds + dels > 200:
        score += 2
        reasons.append("high churn")
    elif adds + dels > 50:
        score += 1
    if "test" in name_lower and dels > adds:
        score += 2
        reasons.append("test removal")

    level = "high" if score >= 5 else "medium" if score >= 3 else "low"
    return score, level, reasons


def _is_ignored(path: str) -> bool:
    return any(fnmatch(path, p) or fnmatch(path.split("/")[-1], p) for p in app_state.ignore_patterns)


def _order_files(entries: list[dict], order: str) -> list[dict]:
    # Mirrors treeOrder() in FileTree.js: directories sorted by name, then the risk score for a flat list.
    if order == "risk":
        return sorted(entries, key=lambda f: -f["risk_score"])
    if order == "tree":
        return sorted(entries, key=lambda f: f["dir"])
    return entries


def view_files(view: str) -> tuple[list[str], dict[str, tuple[int, int]]]:
    """The paths a view lists, with the add and delete counts it has for them."""
    if view == "all":
        return app_state.review_files, app_state.numstat
    if view == "working":
        return list(app_state.working_files), {}
    if view == LAST_TURN:
        turn = app_state.last_turn
        return (sorted(turn.stats), turn.stats) if turn else ([], {})
    commit = _find_commit(view)
    return (commit.files if commit else []), {}


def _file_entries(view: str, order: str, hide_ignored: bool) -> list[dict]:
    files, numstat = view_files(view)
    result = []
    for f in files:
        adds, dels = numstat.get(f, (0, 0))
        risk_score, risk_level, risk_reasons = _score_risk(f, adds, dels)
        comments = app_state.comments.get(f, [])
        result.append(
            {
                "path": f,
                "short_name": short_name(f),
                "dir": f.rpartition("/")[0] or ".",
                "reviewed": f in app_state.reviewed,
                "review_mtime": app_state.reviewed.get(f),
                "file_mtime": get_file_mtime(f),
                "has_comments": f in app_state.comments,
                "comment_count": len(comments),
                "open_comment_count": sum(1 for c in comments if is_comment_open(c)),
                "adds": adds,
                "dels": dels,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "risk_reasons": risk_reasons,
                "ignored": _is_ignored(f),
            }
        )
    if hide_ignored:
        result = [f for f in result if not f["ignored"]]
    return _order_files(result, order)


@router.get("/files")
def list_files(view: str = "all", order: str = "", hide_ignored: bool = False):
    return _file_entries(view, order, hide_ignored)


@router.get("/files/next-unreviewed")
def next_unreviewed(order: str = "tree", view: str = "all"):
    entries = _file_entries(view, order, hide_ignored=True)
    return {"path": next((f["path"] for f in entries if not f["reviewed"]), None)}


@router.get("/diff/{path:path}")
def get_diff(path: str, view: str = "all", context: int = 3, ignore_whitespace: bool = False):
    path = repo_relative(path)
    diff_text = _get_diff(path, view, context, ignore_whitespace=ignore_whitespace)
    return parse_diff_to_json(diff_text, path, app_state.theme)


@router.get("/file/{path:path}")
def get_file(path: str, view: str = "all"):
    from diffui.git_utils import get_file_content
    from diffui.server.highlight import highlight_file_to_json

    path = repo_relative(path)
    content = get_file_content(path)
    diff_text = _get_diff(path, view)
    return highlight_file_to_json(content, diff_text, path, app_state.theme)


@router.get("/blame/{path:path}")
def get_blame_data(path: str):
    from diffui.git_utils import get_blame

    return get_blame(repo_relative(path))


@router.get("/preview/{path:path}")
def get_preview(path: str):
    import mimetypes

    from diffui.git_utils import get_file_content, get_repo_root

    path = repo_relative(path)
    mime, _ = mimetypes.guess_type(path)
    if mime and mime.startswith("image/"):
        full_path = get_repo_root() / path
        if not full_path.exists():
            return {"type": "image", "exists": False}
        size = full_path.stat().st_size
        if size > 10 * 1024 * 1024:
            return {"type": "image", "exists": True, "too_large": True}
        import base64

        data = base64.b64encode(full_path.read_bytes()).decode()
        return {"type": "image", "exists": True, "data_url": f"data:{mime};base64,{data}"}
    content = get_file_content(path)
    return {"type": "text", "content": content}
