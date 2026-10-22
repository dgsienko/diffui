from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from diffui.git_utils import is_comment_open
from diffui.server.state import app_state

_SOURCE = "diffui"
_PASTE_START = "\x1b[200~"
_PASTE_END = "\x1b[201~"


def _workspace() -> str | None:
    return os.environ.get("HERDR_WORKSPACE_ID")


def _herdr(*args: str) -> dict | None:
    try:
        result = subprocess.run(["herdr", *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return json.loads(result.stdout) if result.stdout.strip() else {}


def find_agent(repo_root: Path) -> dict | None:
    workspace = _workspace()
    if not workspace:
        return None
    listing = _herdr("agent", "list")
    if not listing:
        return None
    agents = [a for a in listing["result"]["agents"] if a.get("workspace_id") == workspace]
    root = repo_root.resolve()
    in_repo = [a for a in agents if Path(a.get("cwd", "/")).resolve().is_relative_to(root)]
    return (in_repo or agents or [None])[0]


def paste_to_agent(text: str, repo_root: Path) -> dict:
    agent = find_agent(repo_root)
    if agent is None:
        return {"ok": False, "error": "No agent found in this herdr workspace"}
    # Claude Code silently drops a paste while a permission prompt is open.
    if agent.get("agent_status") == "blocked":
        return {"ok": False, "error": f"{agent['agent']} is waiting on a prompt. Answer it, then send again."}
    # An end marker inside the text would end the paste early and submit the rest as keystrokes.
    while _PASTE_END in text:
        text = text.replace(_PASTE_END, "")
    if _herdr("pane", "send-text", agent["pane_id"], _PASTE_START + text + _PASTE_END) is None:
        return {"ok": False, "error": "herdr rejected the paste"}
    _herdr("agent", "focus", agent["pane_id"])
    return {"ok": True, "agent": agent["agent"]}


def _report_metadata(*flags: str) -> None:
    workspace = _workspace()
    if workspace:
        _herdr("workspace", "report-metadata", workspace, "--source", _SOURCE, *flags)


def report_status() -> None:
    open_count = sum(1 for cs in app_state.comments.values() for c in cs if is_comment_open(c))
    files = set(app_state.all_files) | set(app_state.working_files)
    reviewed = sum(1 for f in files if f in app_state.reviewed)
    # An empty token value clears it, which hides it from the sidebar row.
    _report_metadata(
        "--token",
        f"comments={open_count} open" if open_count else "comments=",
        "--token",
        f"reviewed={reviewed}/{len(files)} reviewed" if files else "reviewed=",
    )


def clear_status() -> None:
    _report_metadata("--clear-token", "comments", "--clear-token", "reviewed")
