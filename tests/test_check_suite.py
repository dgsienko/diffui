import io
import subprocess

import pytest

from scripts import check_suite


def _completed(returncode=0, stdout=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


BLOCK = _completed(stdout=":warning: Can't fail: ...\n`CHECK-SUITE: BLOCK`")


@pytest.fixture
def run(monkeypatch):
    state = {"git": _completed(stdout="diff"), "claude": _completed(stdout="CHECK-SUITE: PASS"), "git_calls": []}

    def fake_run(args, **kwargs):
        if args[0] == "git":
            state["git_calls"].append(args)
            return state["git"]
        if isinstance(state["claude"], Exception):
            raise state["claude"]
        return state["claude"]

    monkeypatch.setattr(check_suite.shutil, "which", lambda _: "claude")
    monkeypatch.setattr(check_suite.subprocess, "run", fake_run)
    monkeypatch.setattr(check_suite.sys, "stdin", io.StringIO(""))
    return state


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        pytest.param({"claude": BLOCK}, 1, id="block"),
        pytest.param(
            {"claude": _completed(stdout="Ends with `CHECK-SUITE: BLOCK` if...\nCHECK-SUITE: PASS")},
            0,
            id="last verdict wins",
        ),
        pytest.param({"git": _completed(), "claude": BLOCK}, 0, id="no changes"),
        pytest.param({"git": _completed(returncode=128, stdout="diff"), "claude": BLOCK}, 0, id="git diff fails"),
        pytest.param({"claude": subprocess.TimeoutExpired("claude", 1)}, 0, id="claude hangs"),
        pytest.param({"claude": _completed(returncode=1, stdout=BLOCK.stdout)}, 0, id="claude errors"),
        pytest.param({"claude": _completed(stdout="report")}, 0, id="no verdict"),
        pytest.param({"claude": BLOCK, "stdin": "(delete) 0000000 refs/heads/a def456\n"}, 0, id="delete-only push"),
    ],
)
def test_main_blocks_only_on_a_block_verdict(run, monkeypatch, setup, expected):
    stdin = setup.get("stdin", "")
    run.update({key: value for key, value in setup.items() if key != "stdin"})
    monkeypatch.setattr(check_suite.sys, "stdin", io.StringIO(stdin))
    assert check_suite.main() == expected


def test_main_skips_when_claude_is_missing(run, monkeypatch):
    monkeypatch.setattr(check_suite.shutil, "which", lambda _: None)
    run["claude"] = BLOCK
    assert check_suite.main() == 0


def test_main_diffs_the_first_pushed_sha_that_is_not_a_delete(run, monkeypatch):
    stdin = "(delete) 0000000 refs/heads/a def456\nrefs/heads/b 1234567 refs/heads/b 0000000\n"
    monkeypatch.setattr(check_suite.sys, "stdin", io.StringIO(stdin))
    check_suite.main()
    diffs = [call for call in run["git_calls"] if call[1] == "diff"]
    assert diffs
    assert all(call[-1] == "origin/main...1234567" for call in diffs)
