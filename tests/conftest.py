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
    yield root
    mp.undo()


@pytest.fixture(scope="session")
def temp_repo(tmp_path_factory) -> Path:
    repo = tmp_path_factory.mktemp("diffui-repo")
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("# fixture repo\n")
    (repo / "app.py").write_text(_APP_V1)
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
