from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from watchfiles import Change

from diffui.server.events import (
    _apply_state_updates,
    _broadcast,
    _classify_changes,
    _sse_clients,
    _ws_clients,
    make_watch_filter,
)
from diffui.server.state import app_state

GIT_DIR = "/repo/.git"
COMMENTS = "/cfg/comments.json"


class TestClassifyChanges:
    @pytest.mark.parametrize(
        ("changes", "expected"),
        [
            pytest.param({(Change.modified, "/repo/src/main.py")}, {"files_changed"}, id="source-file"),
            pytest.param({(Change.modified, f"{GIT_DIR}/HEAD")}, {"git_changed"}, id="git-head"),
            pytest.param({(Change.modified, f"{GIT_DIR}/index")}, {"git_changed"}, id="git-index"),
            pytest.param({(Change.modified, f"{GIT_DIR}/refs/heads/main")}, {"git_changed"}, id="git-ref"),
            pytest.param({(Change.modified, COMMENTS)}, {"comments_changed"}, id="comments"),
            pytest.param({(Change.modified, "/repo/.gitignore")}, {"files_changed"}, id="gitignore-is-a-file-change"),
            pytest.param(
                {(Change.modified, "/repo/.github/workflows/ci.yml")},
                {"files_changed"},
                id="github-dir-is-a-file-change",
            ),
            pytest.param(
                {
                    (Change.modified, "/repo/file.py"),
                    (Change.modified, f"{GIT_DIR}/index"),
                    (Change.modified, COMMENTS),
                },
                {"files_changed", "git_changed", "comments_changed"},
                id="mixed",
            ),
            pytest.param(
                {(Change.modified, "/repo/a.py"), (Change.added, "/repo/b.py")}, {"files_changed"}, id="dedup"
            ),
            pytest.param(set(), set(), id="empty"),
        ],
    )
    def test_classify(self, changes, expected):
        events = _classify_changes(changes, GIT_DIR, COMMENTS)
        assert (len(events), set(events)) == (len(expected), expected)


class TestMakeWatchFilter:
    @pytest.mark.parametrize(
        ("path", "accepted"),
        [
            pytest.param("/repo/src/main.py", True, id="source-file"),
            pytest.param("/repo/module.pyc", False, id="pyc"),
            pytest.param("/repo/__pycache__/notes.txt", False, id="pycache"),
            pytest.param(f"{GIT_DIR}/HEAD", True, id="git-head"),
            pytest.param(f"{GIT_DIR}/index", True, id="git-index"),
            pytest.param(f"{GIT_DIR}/refs/heads/main", True, id="git-refs"),
            pytest.param(f"{GIT_DIR}/objects/ab/cdef1234", False, id="git-objects"),
            pytest.param(f"{GIT_DIR}/logs/HEAD", False, id="git-logs"),
            pytest.param("/other/repo/.git/HEAD", False, id="unrelated-git-dir"),
            pytest.param("/repo/.git", False, id="bare-git-dir"),
        ],
    )
    def test_filter(self, path, accepted):
        assert make_watch_filter(GIT_DIR)(Change.modified, path) is accepted


class _FakeWebSocket:
    def __init__(self):
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(text)


class TestBroadcast:
    def test_sse_clients_receive_the_events_as_data(self):
        q = asyncio.Queue(maxsize=8)
        _sse_clients.add(q)
        try:
            _broadcast(["files_changed"])
            assert q.get_nowait() == 'data: {"events": ["files_changed"]}\n\n'
        finally:
            _sse_clients.discard(q)

    def test_no_events_sends_nothing(self):
        q = asyncio.Queue(maxsize=8)
        _sse_clients.add(q)
        try:
            _broadcast([])
            assert q.empty()
        finally:
            _sse_clients.discard(q)

    def test_full_queue_is_skipped(self):
        q = asyncio.Queue(maxsize=1)
        q.put_nowait("filler")
        _sse_clients.add(q)
        try:
            _broadcast(["files_changed"])
            assert q.get_nowait() == "filler"
            assert q.empty()
        finally:
            _sse_clients.discard(q)

    def test_ws_clients_receive_the_events(self):
        async def broadcast_on_a_loop():
            _broadcast(["files_changed"])
            await asyncio.sleep(0)

        ws = _FakeWebSocket()
        _ws_clients.add(ws)
        try:
            asyncio.run(broadcast_on_a_loop())
            assert ws.sent == ['{"events": ["files_changed"]}']
        finally:
            _ws_clients.discard(ws)


@pytest.fixture
def git_reload():
    """The git-changed path with the repo reload and its side effects stubbed; the reload mock sets what it changes."""
    with (
        patch("diffui.server.state.app_state.reload_repo_state") as reload,
        patch("diffui.server.events.clear_diff_cache"),
        patch("diffui.server.events._invalidate_stale_reviews"),
    ):
        yield reload


class TestApplyStateUpdates:
    @pytest.mark.parametrize("events", [["git_changed"], ["git_changed", "files_changed"]])
    def test_git_changed_announces_files_changed_once(self, git_reload, events):
        assert _apply_state_updates(events).count("files_changed") == 1

    def test_files_changed_refreshes_numstat_and_working_files(self, monkeypatch):
        monkeypatch.setattr(app_state, "numstat", {})
        monkeypatch.setattr(app_state, "working_files", [])
        with (
            patch("diffui.server.events.get_diff_numstat", return_value={"a.py": (1, 2)}),
            patch("diffui.server.events.get_working_changed_files", return_value=["a.py"]),
        ):
            result = _apply_state_updates(["files_changed"])

        assert app_state.numstat == {"a.py": (1, 2)}
        assert app_state.working_files == ["a.py"]
        assert result == ["files_changed"]

    def test_comments_changed_reloads_comments(self, monkeypatch):
        monkeypatch.setattr(app_state, "comments", {})
        with patch("diffui.server.events.load_comments", return_value={"a.py": [{"id": "1"}]}):
            result = _apply_state_updates(["comments_changed"])

        assert app_state.comments == {"a.py": [{"id": "1"}]}
        assert result == ["comments_changed"]

    @pytest.mark.parametrize(
        ("reloaded", "announced"),
        [
            pytest.param({"a.py": [{"id": "1", "comment": "from the new branch"}]}, True, id="new-branch-has-comments"),
            pytest.param({}, False, id="comments-unchanged"),
        ],
    )
    def test_git_changed_announces_comments_only_when_they_differ(self, git_reload, monkeypatch, reloaded, announced):
        monkeypatch.setattr(app_state, "comments", {})
        git_reload.side_effect = lambda: setattr(app_state, "comments", reloaded)
        assert ("comments_changed" in _apply_state_updates(["git_changed"])) is announced

    @pytest.mark.parametrize(("new_branch", "restarted"), [("new-branch", True), ("old-branch", False)])
    def test_watcher_restarts_only_on_a_branch_switch(self, git_reload, monkeypatch, new_branch, restarted):
        monkeypatch.setattr(app_state, "branch_name", "old-branch")
        git_reload.side_effect = lambda: setattr(app_state, "branch_name", new_branch)
        with patch("diffui.server.events.restart_watcher") as restart:
            _apply_state_updates(["git_changed"])

        assert restart.called is restarted


class TestAutoUnreview:
    def test_files_changed_unreviews_modified_files(self, monkeypatch):
        monkeypatch.setattr(app_state, "reviewed", {"changed.py": 1000.0, "untouched.py": 2000.0})
        monkeypatch.setattr(app_state, "numstat", {})
        monkeypatch.setattr(app_state, "working_files", [])
        with (
            patch("diffui.server.events.get_diff_numstat", return_value={}),
            patch("diffui.server.events.get_working_changed_files", return_value=[]),
            patch("diffui.server.events.get_file_mtime", side_effect=lambda p: 1500.0 if p == "changed.py" else 2000.0),
        ):
            _apply_state_updates(["files_changed"])

        assert app_state.reviewed == {"untouched.py": 2000.0}

    def test_git_changed_also_unreviews_modified_files(self, monkeypatch):
        monkeypatch.setattr(app_state, "reviewed", {"changed.py": 1000.0})
        with (
            patch("diffui.server.state.app_state.reload_repo_state"),
            patch("diffui.server.events.clear_diff_cache"),
            patch("diffui.server.events.get_file_mtime", return_value=2000.0),
        ):
            _apply_state_updates(["git_changed"])

        assert app_state.reviewed == {}
