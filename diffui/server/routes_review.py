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


@router.get("/review-summary")
def review_summary():
    from diffui.git_utils import current_branch, short_name

    branch_name = current_branch()
    total = len(app_state.all_files)
    reviewed_count = sum(1 for f in app_state.all_files if f in app_state.reviewed)
    all_comments = []
    for file_path, file_comments in app_state.comments.items():
        for c in file_comments:
            all_comments.append({**c, "_file": file_path})

    open_comments = [c for c in all_comments if c.get("status", "open") != "resolved"]
    resolved_comments = [c for c in all_comments if c.get("status", "open") == "resolved"]

    by_category: dict[str, list[dict]] = {}
    for c in open_comments:
        cat = c.get("category", "") or "general"
        by_category.setdefault(cat, []).append(c)

    lines = [f"# Review Summary: {branch_name}", ""]
    lines.append(f"**Files:** {reviewed_count}/{total} reviewed")
    lines.append(
        f"**Comments:** {len(all_comments)} total, {len(open_comments)} open, {len(resolved_comments)} resolved"
    )
    lines.append("")

    if open_comments:
        lines.append("## Open Comments")
        lines.append("")
        for cat, comments in sorted(by_category.items()):
            if len(by_category) > 1:
                lines.append(f"### {cat.title()}")
                lines.append("")
            for c in comments:
                fname = short_name(c["_file"])
                line_num = c.get("file_line_num", "?")
                lines.append(f"- **{fname}:{line_num}** — {c.get('comment', '')}")
            lines.append("")

    if app_state.all_files:
        lines.append("## Files")
        lines.append("")
        for f in app_state.all_files:
            status = "reviewed" if f in app_state.reviewed else "pending"
            comment_count = len(app_state.comments.get(f, []))
            suffix = f" ({comment_count} comments)" if comment_count else ""
            lines.append(f"- [{status}] `{f}`{suffix}")

    return {"markdown": "\n".join(lines)}
