from __future__ import annotations

import subprocess
import threading

from fastapi import APIRouter

from diffui.git_utils import get_file_mtime, save_reviewed
from diffui.server.state import app_state

_agent_process: subprocess.Popen | None = None
_explain_process: subprocess.Popen | None = None
_process_lock = threading.Lock()

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


def _process_status(proc: subprocess.Popen | None) -> dict:
    if not proc:
        return {"running": False}
    rc = proc.poll()
    if rc is None:
        return {"running": True, "pid": proc.pid}
    proc.wait()
    return {"running": False, "exit_code": rc}


_AGENT_CMDS = {
    "claude": lambda prompt, cwd: ["claude", "-p", prompt, "--allowedTools", "Edit,Read,Bash,Write"],
    "codex": lambda prompt, cwd: ["codex", "--prompt", prompt, "--auto-edit"],
    "opencode": lambda prompt, cwd: ["opencode", "-p", prompt],
    "cursor": lambda prompt, cwd: ["cursor-agent", "-p", prompt],
}


def _build_agent_prompt() -> tuple[str, str] | tuple[None, str]:
    from diffui.git_utils import _comments_path, get_repo_root

    open_comments = []
    for file_path, file_comments in app_state.comments.items():
        for c in file_comments:
            if c.get("status", "open") != "resolved":
                line_num = c.get("file_line_num", c.get("line_index", "?"))
                cat = c.get("category", "")
                prefix = f"[{cat}] " if cat else ""
                open_comments.append(f"{file_path}:{line_num} — {prefix}{c.get('comment', '')}")

    if not open_comments:
        return None, "No open comments"

    comments_path = str(_comments_path())
    repo_root = str(get_repo_root())
    comment_text = "\n".join(open_comments)

    prompt = (
        f"Address these diffui review comments in the repo at {repo_root}. "
        f"The comments file is at {comments_path}. "
        f"For each comment, make the fix, then add a reply to the comment in the JSON file "
        f"explaining what you did. Remove comments you've fully addressed.\n\n"
        f"{comment_text}"
    )
    return prompt, repo_root


@router.post("/agent/prompt")
def get_agent_prompt():
    result = _build_agent_prompt()
    if result[0] is None:
        return {"ok": False, "error": result[1]}
    return {"ok": True, "prompt": result[0]}


@router.post("/agent/run")
def run_agent():
    global _agent_process
    with _process_lock:
        if _agent_process and _agent_process.poll() is None:
            return {"ok": False, "error": "Agent already running"}

        result = _build_agent_prompt()
        if result[0] is None:
            return {"ok": False, "error": result[1]}
        prompt, repo_root = result

        agent = app_state.agent_cli
        cmd_builder = _AGENT_CMDS.get(agent)
        if not cmd_builder:
            return {"ok": False, "error": f"Unknown agent CLI: {agent}"}

        _agent_process = subprocess.Popen(
            cmd_builder(prompt, repo_root),
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return {"ok": True, "pid": _agent_process.pid, "agent": agent}


@router.get("/agent/status")
def agent_status():
    return _process_status(_agent_process)


@router.post("/explain")
def explain_changes():
    global _explain_process
    with _process_lock:
        if _explain_process and _explain_process.poll() is None:
            return {"ok": False, "error": "Explanation already generating"}

        import tempfile

        from diffui.git_utils import current_branch, get_repo_root

        repo_root = str(get_repo_root())
        branch_name = current_branch()
        output_path = f"{tempfile.gettempdir()}/diffui-explain-{branch_name.replace('/', '-')}.html"

        diff_summary = []
        for f in app_state.all_files:
            adds, dels = app_state.numstat.get(f, (0, 0))
            diff_summary.append(f"  {f} (+{adds}/-{dels})")

        file_list = "\n".join(diff_summary)

        prompt = (
            f"Generate an HTML walkthrough of the changes on branch '{branch_name}' in {repo_root}. "
            f"Read the full diff and changed files, then write a single self-contained HTML file to {output_path}.\n\n"
            f"The HTML should include:\n"
            f"1. A TL;DR summary (2-3 sentences)\n"
            f"2. A 'Why' section explaining the motivation\n"
            f"3. File-by-file analysis with key code snippets\n"
            f"4. Architecture notes if there are structural changes\n"
            f"5. Risk flags (migrations, config changes, security implications)\n"
            f"6. A 'Where to focus' section for reviewers\n\n"
            f"Style: dark theme, clean typography, self-contained (no CDN dependencies except optionally Mermaid). "
            f"Use syntax highlighting with inline styles. Make it look polished.\n\n"
            f"Changed files ({len(app_state.all_files)}):\n{file_list}"
        )

        agent = app_state.agent_cli
        cmd_builder = _AGENT_CMDS.get(agent)
        if not cmd_builder:
            return {"ok": False, "error": f"Unknown agent CLI: {agent}"}

        _explain_process = subprocess.Popen(
            cmd_builder(prompt, repo_root),
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return {"ok": True, "output_path": output_path}


@router.get("/explain/status")
def explain_status():
    return _process_status(_explain_process)
