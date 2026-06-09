from __future__ import annotations

from fastapi import APIRouter

from diffui.git_utils import (
    get_commit_diff,
    get_file_mtime,
    get_full_diff,
    get_repo_root,
    get_working_changed_files,
    get_working_diff,
    short_name,
)
from diffui.server.highlight import parse_diff_to_json
from diffui.server.state import app_state

router = APIRouter(prefix="/api")

_diff_cache: dict[tuple[str, str, str, str, float], str] = {}
_MAX_CACHE = 128


def clear_diff_cache() -> None:
    _diff_cache.clear()


def _get_diff(path: str, view: str, context: int = 3) -> str:
    repo_id = str(get_repo_root())
    merge_base = app_state.merge_base
    mtime = get_file_mtime(path)
    cache_key = (repo_id, merge_base, path, f"{view}:c{context}", mtime)
    if cache_key in _diff_cache:
        return _diff_cache[cache_key]
    if view == "all":
        result = get_full_diff(merge_base, path, context)
    elif view == "working":
        result = get_working_diff(path, context)
    else:
        result = get_commit_diff(view, path, context)
    stale = next((k for k in _diff_cache if k[2] == path and k[3] == f"{view}:c{context}"), None)
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


def _score_risk(path: str, adds: int, dels: int) -> tuple[int, str]:
    score = 0
    reasons = []
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

    if score >= 5:
        return score, "high"
    if score >= 3:
        return score, "medium"
    return score, "low"


@router.get("/files")
def list_files(view: str = "all"):
    if view == "all":
        working = get_working_changed_files()
        files = sorted(set(app_state.all_files) | set(working))
    elif view == "working":
        files = get_working_changed_files()
    else:
        commit = next((c for c in app_state.commits if c.sha == view), None)
        files = commit.files if commit else []

    numstat = app_state.numstat if view == "all" else {}

    result = []
    for f in files:
        adds = numstat.get(f, (0, 0))[0]
        dels = numstat.get(f, (0, 0))[1]
        risk_score, risk_level = _score_risk(f, adds, dels)
        result.append(
            {
                "path": f,
                "short_name": short_name(f),
                "reviewed": f in app_state.reviewed,
                "review_mtime": app_state.reviewed.get(f),
                "file_mtime": get_file_mtime(f),
                "has_comments": f in app_state.comments,
                "comment_count": len(app_state.comments.get(f, [])),
                "adds": adds,
                "dels": dels,
                "risk_score": risk_score,
                "risk_level": risk_level,
            }
        )
    return result


@router.get("/diff/{path:path}")
def get_diff(path: str, view: str = "all", context: int = 3):
    diff_text = _get_diff(path, view, context)
    return parse_diff_to_json(diff_text, path, app_state.theme)


@router.get("/file/{path:path}")
def get_file(path: str, view: str = "all"):
    from diffui.git_utils import get_file_content
    from diffui.server.highlight import highlight_file_to_json

    content = get_file_content(path)
    diff_text = _get_diff(path, view)
    return highlight_file_to_json(content, diff_text, path, app_state.theme)


@router.get("/blame/{path:path}")
def get_blame_data(path: str):
    from diffui.git_utils import get_blame

    return get_blame(path)


@router.get("/preview/{path:path}")
def get_preview(path: str):
    import mimetypes

    from diffui.git_utils import get_file_content, get_repo_root

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
