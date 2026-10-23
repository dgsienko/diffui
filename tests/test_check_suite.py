import io
import subprocess

import pytest

from scripts import check_suite
from scripts.check_suite import pushed_sha, verdict


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        ("✅ Docs (check-docs): no changes needed.\nCHECK-SUITE: PASS", "PASS"),
        (":warning: Can't fail: ...\n`CHECK-SUITE: BLOCK`", "BLOCK"),
        ("**CHECK-SUITE: BLOCK**", "BLOCK"),
        ("Ends with `CHECK-SUITE: BLOCK` if...\nCHECK-SUITE: PASS", "PASS"),
        ("no verdict at all", None),
        ("CHECK-SUITE: maybe", None),
    ],
)
def test_verdict_reads_the_last_verdict_line(report, expected):
    assert verdict(report) == expected


@pytest.mark.parametrize(
    ("hook_input", "expected"),
    [
        ("refs/heads/a abc123 refs/heads/a def456\n", "abc123"),
        ("(delete) 0000000 refs/heads/a def456\nrefs/heads/b 1234567 refs/heads/b 0000000\n", "1234567"),
        ("(delete) 0000000 refs/heads/a def456\n", None),
        ("", None),
    ],
)
def test_pushed_sha_skips_deletes(hook_input, expected):
    assert pushed_sha(hook_input) == expected


def _completed(returncode=0, stdout=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


@pytest.fixture
def run(monkeypatch):
    """Patch subprocess so git and claude return canned results and calls are recorded."""
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
    ("case", "expected"),
    [
        ("pass", 0),
        ("block", 1),
        ("no changes", 0),
        ("git diff fails", 0),
        ("claude hangs", 0),
        ("claude errors", 0),
        ("no verdict", 0),
        ("delete-only push", 0),
    ],
)
def test_main_blocks_only_on_a_block_verdict(run, monkeypatch, case, expected):
    if case == "block":
        run["claude"] = _completed(stdout="CHECK-SUITE: BLOCK")
    elif case == "no changes":
        run["git"] = _completed()
    elif case == "git diff fails":
        run["git"] = _completed(returncode=128, stdout="diff")
        run["claude"] = _completed(stdout="CHECK-SUITE: BLOCK")
    elif case == "claude hangs":
        run["claude"] = subprocess.TimeoutExpired("claude", 1)
    elif case == "claude errors":
        run["claude"] = _completed(returncode=1, stdout="CHECK-SUITE: BLOCK")
    elif case == "no verdict":
        run["claude"] = _completed(stdout="report")
    elif case == "delete-only push":
        monkeypatch.setattr(check_suite.sys, "stdin", io.StringIO("(delete) 0000000 refs/heads/a def456\n"))
        run["claude"] = _completed(stdout="CHECK-SUITE: BLOCK")
    assert check_suite.main() == expected


def test_main_skips_when_claude_is_missing(run, monkeypatch):
    monkeypatch.setattr(check_suite.shutil, "which", lambda _: None)
    run["claude"] = _completed(stdout="CHECK-SUITE: BLOCK")
    assert check_suite.main() == 0


def test_main_diffs_the_pushed_sha(run, monkeypatch):
    monkeypatch.setattr(check_suite.sys, "stdin", io.StringIO("refs/heads/a abc123 refs/heads/a def456\n"))
    check_suite.main()
    diffs = [call for call in run["git_calls"] if call[1] == "diff"]
    assert diffs
    assert all(call[-1] == "origin/main...abc123" for call in diffs)
