from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import diffui.git_utils

_APP_V1 = "\n".join(f"line {i}" for i in range(1, 21)) + "\n"
_APP_V2 = _APP_V1.replace("line 5", "line five").replace("line 12", "line twelve")
_APP_DIRTY = _APP_V2 + "uncommitted tail\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=test@diffui", "-c", "user.name=diffui test", "-C", str(repo), *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session", autouse=True)
def diffui_config_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("diffui-config")
    mp = pytest.MonkeyPatch()
    mp.setattr(diffui.git_utils, "_CONFIG_ROOT", root)
    # A suite run from a herdr pane would otherwise write to the live sidebar.
    mp.delenv("HERDR_WORKSPACE_ID", raising=False)
    # A pre-push hook in a linked worktree exports GIT_DIR, which points the temp repos' git calls at the checkout.
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        mp.delenv(var, raising=False)
    yield root
    mp.undo()


@pytest.fixture(autouse=True)
def _isolate_repo_state():
    """Comments, reviewed marks and the active repo are process-wide, so one test's leftovers would reach the next."""
    from diffui.server.state import app_state

    active = diffui.git_utils._active_repo_root
    yield
    if active is not None:
        diffui.git_utils.set_active_repo(active)
    app_state.comments = {}
    app_state.reviewed = {}
    diffui.git_utils.save_comments({})
    diffui.git_utils.save_reviewed({})


@pytest.fixture(scope="session")
def temp_repo(tmp_path_factory) -> Path:
    repo = tmp_path_factory.mktemp("diffui-repo")
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("# fixture repo\n")
    (repo / "app.py").write_text(_APP_V1)
    (repo / "renderer.py").write_text("".join(f"def render_{i}(): ...\n" for i in range(1, 41)))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "initial commit")

    _git(repo, "checkout", "-qb", "feature")
    (repo / "app.py").write_text(_APP_V2)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "reword two lines")
    (repo / "extra.py").write_text("VALUE = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "add extra module")

    (repo / "app.py").write_text(_APP_DIRTY)
    (repo / "untracked.txt").write_text("never committed\n")
    return repo
