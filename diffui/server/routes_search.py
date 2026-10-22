from __future__ import annotations

from fastapi import APIRouter

from diffui.git_utils import PathOutsideRepo, repo_path
from diffui.server.routes_diff import _is_ignored, view_files

router = APIRouter(prefix="/api")

MAX_HITS = 200
_MAX_FILE_BYTES = 1_000_000
_MAX_TEXT = 300


def _name_rank(query: str, path: str) -> int | None:
    """0 for a match in the file name, 1 in the path, 2 for the query's letters in order, None for none."""
    path = path.lower()
    if query in path.rsplit("/", 1)[-1]:
        return 0
    if query in path:
        return 1
    letters = iter(path)
    return 2 if all(c in letters for c in query) else None


def _read_lines(path: str) -> list[str]:
    try:
        raw = repo_path(path).read_bytes()[:_MAX_FILE_BYTES]
    except (OSError, PathOutsideRepo):
        return []
    if b"\0" in raw:
        return []
    return raw.decode("utf-8", errors="replace").splitlines()


@router.get("/search")
def search(q: str = "", view: str = "all"):
    """File names and file content matching `q`, case-insensitively, among the files `view` lists."""
    query = q.lower()
    if not query:
        return {"files": [], "hits": [], "truncated": False}
    paths = [p for p in view_files(view)[0] if not _is_ignored(p)]
    ranked = sorted((r, p) for p in paths if (r := _name_rank(query, p)) is not None)
    hits: list[dict] = []
    truncated = False
    for path in paths:
        for number, line in enumerate(_read_lines(path), 1):
            if query in line.lower():
                if len(hits) == MAX_HITS:
                    truncated = True
                    break
                hits.append({"path": path, "line": number, "text": line[:_MAX_TEXT]})
        if truncated:
            break
    return {"files": [p for _, p in ranked], "hits": hits, "truncated": truncated}
