"""The terminal host: the multiplexer diffui runs inside, which owns the agent panes and the sidebar.

Only this module knows the host is herdr. Callers get agent names and status strings (`idle`, `working`,
`done`, `blocked`), never the host's agent dicts.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from diffui.server.state import app_state

NAME = "herdr"  # for user-facing copy that has to say what is required
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


def available() -> bool:
    return bool(_workspace()) and shutil.which("herdr") is not None


def repo_agent_statuses(repo_root: Path) -> list[str] | None:
    """Status of every agent working inside the repo, in any workspace. None when the host could not answer."""
    listing = _herdr("agent", "list")
    if listing is None:
        return None
    root = repo_root.resolve()
    agents = listing.get("result", {}).get("agents", [])
    # foreground_cwd is where the agent is now. cwd is where its pane started.
    return [
        a.get("agent_status", "unknown")
        for a in agents
        if Path(a.get("foreground_cwd") or a.get("cwd") or "/").resolve().is_relative_to(root)
    ]


def _find_agent(repo_root: Path) -> dict | None:
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


def paste_to_agent_pane(text: str, repo_root: Path) -> dict:
    agent = _find_agent(repo_root)
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


def agent_pane_name(repo_root: Path) -> str | None:
    """Name of the agent a paste would reach, or None when there is no pane to paste into."""
    agent = _find_agent(repo_root)
    return agent["agent"] if agent else None


def _report_metadata(*flags: str) -> None:
    workspace = _workspace()
    if workspace:
        _herdr("workspace", "report-metadata", workspace, "--source", _SOURCE, *flags)


def report_status() -> None:
    open_count = len(app_state.open_comments())
    files = app_state.review_files
    reviewed = app_state.reviewed_count
    # An empty token value clears it, which hides it from the sidebar row.
    _report_metadata(
        "--token",
        f"comments={open_count} open" if open_count else "comments=",
        "--token",
        f"reviewed=☑ {reviewed}/{len(files)}" if files else "reviewed=",
    )


def clear_status() -> None:
    _report_metadata("--clear-token", "comments", "--clear-token", "reviewed")
