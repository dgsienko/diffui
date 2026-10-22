from __future__ import annotations

from typing import Literal

from fastapi import APIRouter

from diffui.git_utils import PathOutsideRepo, repo_path
from diffui.server import fff_index
from diffui.server.routes_diff import _is_ignored, view_files

router = APIRouter(prefix="/api")

MAX_HITS = 200
FILE_CAP = 30
_MAX_FILE_BYTES = 1_000_000
_MAX_TEXT = 300
# fff's fuzzy match returns something for almost any query, so the weak tail is cut: a score must reach a
# share of the best one and this much per character of the longest word typed.
_KEEP_OF_BEST = 0.75
_MIN_PER_CHAR = 8


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


def _fuzzy_names(finder, query: str, only: set[str] | None = None) -> list[str]:
    """Paths fff ranks for `query`, best first, without the weak tail. `only` keeps just those paths."""
    size = finder.scan_progress.scanned_files_count if only is not None else FILE_CAP
    found = finder.search(query, page_size=size)
    scored = [
        (s.total, i.relative_path)
        for i, s in zip(found.items, found.scores, strict=True)
        if only is None or i.relative_path in only
    ]
    if not scored:
        return []
    floor = max(scored[0][0] * _KEEP_OF_BEST, _MIN_PER_CHAR * max(map(len, query.split()), default=0))
    return [path for score, path in scored if score >= floor][:FILE_CAP]


def _search_changed(query: str, view: str) -> dict:
    paths = [p for p in view_files(view)[0] if not _is_ignored(p)]
    ranked = sorted((r, p) for p in paths if (r := _name_rank(query, p)) is not None)
    with fff_index.finder() as finder:
        fuzzy = _fuzzy_names(finder, query, set(paths))
    names = [p for _, p in ranked]
    files = names + [p for p in fuzzy if p not in names]
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
    return {"files": files, "hits": hits, "truncated": truncated}


def _search_all(query: str, view: str) -> dict:
    changed = set(view_files(view)[0])
    with fff_index.finder() as finder:
        names = _fuzzy_names(finder, query)
        # A lowercase query matches case-insensitively (fff's smart case) and one pattern is searched as plain text.
        found = finder.multi_grep([query], max_file_size=_MAX_FILE_BYTES, page_limit=MAX_HITS + 1)
        matches = [m for m in found.items if not m.is_binary]
    hits = sorted(
        (
            {
                "path": m.relative_path,
                "line": m.line_number,
                "text": m.line_content[:_MAX_TEXT],
                "changed": m.relative_path in changed,
            }
            for m in matches[:MAX_HITS]
        ),
        key=lambda h: (h["path"], h["line"]),
    )
    return {
        "files": [{"path": p, "changed": p in changed} for p in names],
        "hits": hits,
        "truncated": found.has_more or len(matches) > MAX_HITS,
    }


@router.get("/search")
def search(q: str = "", view: str = "all", scope: Literal["changed", "all"] = "changed"):
    """File names and file content matching `q`, case-insensitively.

    `changed` covers the files `view` lists. `all` covers the whole repo through fff and marks each file and hit
    with whether the view lists it.
    """
    query = q.lower()
    if not query:
        return {"files": [], "hits": [], "truncated": False}
    return (_search_all if scope == "all" else _search_changed)(query, view)
