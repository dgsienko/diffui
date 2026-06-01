from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from watchfiles import Change


@pytest.fixture()
def _setup_repo():
    from diffui.git_utils import resolve_repo_root, set_active_repo

    root = resolve_repo_root(Path(__file__).parent.parent)
    set_active_repo(root)


class TestClassifyChanges:
    @pytest.fixture(autouse=True)
    def setup(self, _setup_repo):
        from diffui.git_utils import _comments_path, get_git_dir
        from diffui.server.events import _classify_changes

        self._classify_fn = _classify_changes
        self.git_dir = str(get_git_dir())
        self.comments_path = str(_comments_path())

    def classify(self, changes):
        return self._classify_fn(changes, self.git_dir, self.comments_path)

    def test_source_file_change(self):
        changes = {(Change.modified, "/some/repo/src/main.py")}
        events = self.classify(changes)
        assert "files_changed" in events

    def test_git_head_change(self):
        changes = {(Change.modified, f"{self.git_dir}/HEAD")}
        events = self.classify(changes)
        assert "git_changed" in events

    def test_git_index_change(self):
        changes = {(Change.modified, f"{self.git_dir}/index")}
        events = self.classify(changes)
        assert "git_changed" in events

    def test_git_ref_change(self):
        changes = {(Change.modified, f"{self.git_dir}/refs/heads/main")}
        events = self.classify(changes)
        assert "git_changed" in events

    def test_comments_change(self):
        changes = {(Change.modified, self.comments_path)}
        events = self.classify(changes)
        assert "comments_changed" in events

    def test_mixed_changes(self):
        changes = {
            (Change.modified, "/some/repo/file.py"),
            (Change.modified, f"{self.git_dir}/index"),
            (Change.modified, self.comments_path),
        }
        events = self.classify(changes)
        assert set(events) == {"files_changed", "git_changed", "comments_changed"}

    def test_empty_changes(self):
        assert self.classify(set()) == []

    def test_multiple_source_files_deduplicated(self):
        changes = {
            (Change.modified, "/some/repo/a.py"),
            (Change.added, "/some/repo/b.py"),
        }
        events = self.classify(changes)
        assert events.count("files_changed") == 1


class TestMakeWatchFilter:
    @pytest.fixture(autouse=True)
    def setup(self, _setup_repo):
        from diffui.git_utils import get_git_dir
        from diffui.server.events import make_watch_filter

        self.git_dir = str(get_git_dir())
        self.filt = make_watch_filter(self.git_dir)

    def test_accepts_source_file(self):
        assert self.filt(Change.modified, "/some/repo/src/main.py") is True

    def test_rejects_pyc(self):
        assert self.filt(Change.modified, "/some/repo/module.pyc") is False

    def test_rejects_pycache(self):
        assert self.filt(Change.modified, "/some/repo/__pycache__/module.cpython-311.pyc") is False

    def test_accepts_git_head(self):
        assert self.filt(Change.modified, f"{self.git_dir}/HEAD") is True

    def test_accepts_git_index(self):
        assert self.filt(Change.modified, f"{self.git_dir}/index") is True

    def test_accepts_git_refs(self):
        assert self.filt(Change.modified, f"{self.git_dir}/refs/heads/main") is True

    def test_rejects_git_objects(self):
        assert self.filt(Change.modified, f"{self.git_dir}/objects/ab/cdef1234") is False

    def test_rejects_git_logs(self):
        assert self.filt(Change.modified, f"{self.git_dir}/logs/HEAD") is False

    def test_rejects_unrelated_git_dir(self):
        assert self.filt(Change.modified, "/other/repo/.git/HEAD") is False

    def test_rejects_bare_git_dir(self):
        assert self.filt(Change.modified, "/some/repo/.git") is False


class TestBroadcast:
    def test_broadcast_to_clients(self):
        from diffui.server.events import _broadcast, _clients

        q = asyncio.Queue(maxsize=8)
        _clients.add(q)
        try:
            _broadcast(["files_changed"])
            msg = q.get_nowait()
            assert '"files_changed"' in msg
            assert msg.startswith("data: ")
            assert msg.endswith("\n\n")
        finally:
            _clients.discard(q)

    def test_broadcast_empty_events_is_noop(self):
        from diffui.server.events import _broadcast, _clients

        q = asyncio.Queue(maxsize=8)
        _clients.add(q)
        try:
            _broadcast([])
            assert q.empty()
        finally:
            _clients.discard(q)

    def test_broadcast_no_clients_is_noop(self):
        from diffui.server.events import _broadcast, _clients

        _clients.clear()
        _broadcast(["files_changed"])

    def test_broadcast_full_queue_skipped(self):
        from diffui.server.events import _broadcast, _clients

        q = asyncio.Queue(maxsize=1)
        q.put_nowait("filler")
        _clients.add(q)
        try:
            _broadcast(["files_changed"])
            assert q.qsize() == 1
        finally:
            _clients.discard(q)
