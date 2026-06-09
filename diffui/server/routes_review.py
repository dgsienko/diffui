from __future__ import annotations

import subprocess
import threading

from fastapi import APIRouter

from diffui.git_utils import get_file_mtime, save_reviewed
from diffui.server.state import app_state

_agent_process: subprocess.Popen | None = None
_explain_process: subprocess.Popen | None = None
_explain_output_path: str | None = None
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
    return {"running": False, "exit_code": rc}


_AGENT_CMDS = {
    "claude": lambda prompt: ["claude", "-p", prompt, "--allowedTools", "Edit,Read,Bash,Write"],
    "codex": lambda prompt: ["codex", "--prompt", prompt, "--auto-edit"],
    "opencode": lambda prompt: ["opencode", "-p", prompt],
    "cursor": lambda prompt: ["cursor-agent", "-p", prompt],
}


def _build_agent_context() -> tuple[str, str, str, int] | tuple[None, str, str, int]:
    import tempfile

    from diffui.git_utils import (
        _comments_path,
        current_branch,
        get_full_diff,
        get_repo_root,
        short_name,
    )

    open_comments: list[dict] = []
    for file_path, file_comments in app_state.comments.items():
        for c in file_comments:
            if c.get("status", "open") != "resolved":
                open_comments.append({**c, "_file": file_path})

    if not open_comments:
        return None, "No open comments", "", 0

    comments_path = str(_comments_path())
    repo_root = str(get_repo_root())
    branch_name = current_branch()

    # Build rich context file
    ctx_lines = [
        f"# diffui Agent Context — {branch_name}",
        "",
        f"Repository: {repo_root}",
        f"Comments file: {comments_path}",
        f"Branch: {branch_name}",
        "",
        "## Review State",
        "",
        f"- {len(app_state.all_files)} files changed",
        f"- {sum(1 for f in app_state.all_files if f in app_state.reviewed)}/{len(app_state.all_files)} reviewed",
        f"- {len(open_comments)} open comments",
        "",
    ]

    # Group comments by file with diffs
    commented_files: dict[str, list[dict]] = {}
    for c in open_comments:
        commented_files.setdefault(c["_file"], []).append(c)

    ctx_lines.append("## Open Comments with Diffs")
    ctx_lines.append("")

    for file_path, comments_list in commented_files.items():
        ctx_lines.append(f"### {file_path}")
        ctx_lines.append("")

        # Include the diff for context
        try:
            diff = get_full_diff(app_state.merge_base, file_path)
            if diff:
                ctx_lines.append("```diff")
                ctx_lines.append(diff.rstrip())
                ctx_lines.append("```")
                ctx_lines.append("")
        except Exception:
            pass

        for c in comments_list:
            line_num = c.get("file_line_num", c.get("line_index", "?"))
            cat = c.get("category", "")
            cat_label = f" [{cat}]" if cat else ""
            ctx_lines.append(f"**Line {line_num}**{cat_label}: {c.get('comment', '')}")
            if c.get("line_text"):
                ctx_lines.append(f"> `{c['line_text'].strip()}`")
            if c.get("suggestion"):
                ctx_lines.append(f"Suggested replacement: `{c['suggestion'].strip()}`")
            replies = c.get("replies", [])
            for r in replies:
                ctx_lines.append(f"  ↳ {r.get('author', 'agent')}: {r.get('text', '')}")
            ctx_lines.append("")

    # Write context file
    context_path = f"{tempfile.gettempdir()}/diffui-agent-context-{branch_name.replace('/', '-')}.md"
    with open(context_path, "w") as f:
        f.write("\n".join(ctx_lines))

    # Build the prompt — explicit about conversation behavior
    comment_summary = []
    for c in open_comments:
        line_num = c.get("file_line_num", c.get("line_index", "?"))
        cat = c.get("category", "")
        prefix = f"[{cat}] " if cat else ""
        comment_summary.append(f"  {short_name(c['_file'])}:{line_num} — {prefix}{c.get('comment', '')}")

    prompt = (
        f"You are addressing review comments left in diffui for the repo at {repo_root}.\n\n"
        f"IMPORTANT — treat these comments as a conversation, not a task list:\n"
        f"- ALWAYS reply to a comment before removing it. Add a reply object to the comment's "
        f"'replies' array in {comments_path} explaining what you did.\n"
        f"- If a comment is unclear or you're unsure how to address it, reply with a question "
        f"and LEAVE the comment in place. Do not guess.\n"
        f"- If a comment has a code suggestion, apply it if it looks correct, or explain why not.\n"
        f"- Only remove a comment from the JSON after you've replied AND fully addressed it.\n"
        f"- Prioritize by category: bug > suggestion > question > nit.\n\n"
        f"Read the full context file at {context_path} for diffs, review state, and "
        f"existing thread replies.\n\n"
        f"Open comments ({len(open_comments)}):\n" + "\n".join(comment_summary)
    )
    return prompt, repo_root, context_path, len(open_comments)


@router.post("/agent/prompt")
def get_agent_prompt():
    result = _build_agent_context()
    if result[0] is None:
        return {"ok": False, "error": result[1]}
    prompt, _, context_path, open_count = result
    return {
        "ok": True,
        "prompt": prompt,
        "context_path": context_path,
        "agent_cli": app_state.agent_cli,
        "comment_count": open_count,
    }


@router.post("/agent/run")
def run_agent():
    global _agent_process
    with _process_lock:
        if _agent_process and _agent_process.poll() is None:
            return {"ok": False, "error": "Agent already running"}

        result = _build_agent_context()
        if result[0] is None:
            return {"ok": False, "error": result[1]}
        prompt, repo_root, _, _ = result

        agent = app_state.agent_cli
        cmd_builder = _AGENT_CMDS.get(agent)
        if not cmd_builder:
            return {"ok": False, "error": f"Unknown agent CLI: {agent}"}

        _agent_process = subprocess.Popen(
            cmd_builder(prompt),
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
    global _explain_process, _explain_output_path
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
            cmd_builder(prompt),
            cwd=repo_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _explain_output_path = output_path
    return {"ok": True, "output_path": output_path}


@router.get("/explain/status")
def explain_status():
    return _process_status(_explain_process)


@router.get("/explain/view")
def view_explanation():
    import tempfile
    from pathlib import Path

    from fastapi.responses import HTMLResponse

    _placeholder = "<html><body style='background:#1e1e2e;color:#cdd6f4;font-family:monospace;display:flex;align-items:center;justify-content:center;height:100vh'><p>No explanation generated yet. Click 'Explain changes' in diffui.</p></body></html>"
    if not _explain_output_path:
        return HTMLResponse(_placeholder)
    resolved = Path(_explain_output_path).resolve()
    if not str(resolved).startswith(tempfile.gettempdir()):
        return HTMLResponse(_placeholder, status_code=400)
    if not resolved.exists():
        return HTMLResponse(_placeholder)
    return HTMLResponse(resolved.read_text())
