from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from watchfiles import Change

from diffui.server.events import _apply_state_updates, _broadcast, _ws_clients
from diffui.server.state import app_state


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
        from diffui.server.events import _sse_clients as _clients

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
        from diffui.server.events import _sse_clients as _clients

        q = asyncio.Queue(maxsize=8)
        _clients.add(q)
        try:
            _broadcast([])
            assert q.empty()
        finally:
            _clients.discard(q)

    def test_broadcast_no_clients_is_noop(self):
        from diffui.server.events import _sse_clients as _clients

        _clients.clear()
        _broadcast(["files_changed"])

    def test_broadcast_full_queue_skipped(self):
        from diffui.server.events import _sse_clients as _clients

        q = asyncio.Queue(maxsize=1)
        q.put_nowait("filler")
        _clients.add(q)
        try:
            _broadcast(["files_changed"])
            assert q.qsize() == 1
        finally:
            _clients.discard(q)


class TestWsBroadcast:
    def test_broadcast_delivers_to_ws_clients(self):

        ws = AsyncMock()
        _ws_clients.add(ws)
        try:
            _broadcast(["files_changed"])
            ws.send_text.assert_called_once()
            import json

            payload = json.loads(ws.send_text.call_args[0][0])
            assert "files_changed" in payload["events"]
        finally:
            _ws_clients.discard(ws)

    def test_broadcast_sends_to_both_sse_and_ws(self):

        from diffui.server.events import _sse_clients as _clients

        q = asyncio.Queue(maxsize=8)
        _clients.add(q)
        ws = AsyncMock()
        _ws_clients.add(ws)
        try:
            _broadcast(["git_changed"])
            assert not q.empty()
            ws.send_text.assert_called_once()
        finally:
            _clients.discard(q)
            _ws_clients.discard(ws)


class TestApplyStateUpdates:
    def test_git_changed_reloads_and_clears_cache(self):

        with (
            patch("diffui.server.state.app_state.reload_repo_state") as reload,
            patch("diffui.server.routes_diff.clear_diff_cache") as clear_cache,
        ):
            result = _apply_state_updates(["git_changed"])

        reload.assert_called_once()
        clear_cache.assert_called_once()
        assert "files_changed" in result

    def test_git_changed_does_not_duplicate_files_changed(self):

        with (
            patch("diffui.server.state.app_state.reload_repo_state"),
            patch("diffui.server.routes_diff.clear_diff_cache"),
        ):
            result = _apply_state_updates(["git_changed", "files_changed"])

        assert result.count("files_changed") == 1

    def test_files_changed_refreshes_numstat_and_working_files(self):

        prev_numstat = app_state.numstat
        prev_working = app_state.working_files
        try:
            with (
                patch("diffui.git_utils.get_diff_numstat", return_value={"a.py": (1, 2)}) as numstat,
                patch("diffui.git_utils.get_working_changed_files", return_value=["a.py"]) as working,
            ):
                result = _apply_state_updates(["files_changed"])

            numstat.assert_called_once_with(app_state.merge_base)
            working.assert_called_once()
            assert app_state.numstat == {"a.py": (1, 2)}
            assert app_state.working_files == ["a.py"]
            assert result == ["files_changed"]
        finally:
            app_state.numstat = prev_numstat
            app_state.working_files = prev_working

    def test_files_changed_skipped_when_git_changed_present(self):

        with (
            patch("diffui.server.state.app_state.reload_repo_state"),
            patch("diffui.server.routes_diff.clear_diff_cache"),
            patch("diffui.git_utils.get_diff_numstat") as numstat,
            patch("diffui.git_utils.get_working_changed_files") as working,
        ):
            _apply_state_updates(["git_changed"])

        numstat.assert_not_called()
        working.assert_not_called()

    def test_comments_changed_reloads_comments(self):

        prev_comments = app_state.comments
        try:
            with patch("diffui.server.events.load_comments", return_value={"a.py": [{"id": "1"}]}) as load:
                result = _apply_state_updates(["comments_changed"])

            load.assert_called_once()
            assert app_state.comments == {"a.py": [{"id": "1"}]}
            assert result == ["comments_changed"]
        finally:
            app_state.comments = prev_comments

    def test_git_and_comments_changed_reload_comments_once(self):

        with (
            patch("diffui.server.state.app_state.reload_repo_state") as reload,
            patch("diffui.server.routes_diff.clear_diff_cache") as clear_cache,
            patch("diffui.server.events.load_comments") as load,
        ):
            result = _apply_state_updates(["git_changed", "comments_changed"])

        reload.assert_called_once()
        clear_cache.assert_called_once()
        # reload_repo_state() already re-read them — no second trip to disk.
        load.assert_not_called()
        assert "files_changed" in result
        assert "comments_changed" in result

    def test_git_changed_announces_reloaded_comments(self):
        prev_comments = app_state.comments
        reloaded = {"a.py": [{"id": "1", "comment": "from the new branch"}]}
        try:
            app_state.comments = {}
            with (
                patch(
                    "diffui.server.state.app_state.reload_repo_state",
                    side_effect=lambda: setattr(app_state, "comments", reloaded),
                ),
                patch("diffui.server.routes_diff.clear_diff_cache"),
                patch("diffui.server.events._invalidate_stale_reviews"),
                patch("diffui.server.events.load_comments", return_value=reloaded),
            ):
                result = _apply_state_updates(["git_changed"])

            assert "comments_changed" in result
        finally:
            app_state.comments = prev_comments

    def test_git_changed_stays_quiet_when_comments_unchanged(self):
        with (
            patch("diffui.server.state.app_state.reload_repo_state"),
            patch("diffui.server.routes_diff.clear_diff_cache"),
            patch("diffui.server.events._invalidate_stale_reviews"),
        ):
            result = _apply_state_updates(["git_changed"])

        assert "comments_changed" not in result

    def test_branch_switch_restarts_watcher(self):
        prev_branch = app_state.branch_name
        try:
            app_state.branch_name = "old-branch"
            with (
                patch(
                    "diffui.server.state.app_state.reload_repo_state",
                    side_effect=lambda: setattr(app_state, "branch_name", "new-branch"),
                ),
                patch("diffui.server.routes_diff.clear_diff_cache"),
                patch("diffui.server.events._invalidate_stale_reviews"),
                patch("diffui.server.events.restart_watcher") as restart,
            ):
                _apply_state_updates(["git_changed"])

            restart.assert_called_once()
        finally:
            app_state.branch_name = prev_branch

    def test_same_branch_leaves_watcher_alone(self):
        with (
            patch("diffui.server.state.app_state.reload_repo_state"),
            patch("diffui.server.routes_diff.clear_diff_cache"),
            patch("diffui.server.events._invalidate_stale_reviews"),
            patch("diffui.server.events.restart_watcher") as restart,
        ):
            _apply_state_updates(["git_changed"])

        restart.assert_not_called()


class TestAutoUnreview:
    def test_files_changed_unreviews_modified_files(self):
        prev_reviewed = app_state.reviewed.copy()
        prev_numstat = app_state.numstat
        prev_working = app_state.working_files
        try:
            app_state.reviewed = {"changed.py": 1000.0, "untouched.py": 2000.0}
            with (
                patch("diffui.git_utils.get_diff_numstat", return_value={}),
                patch("diffui.git_utils.get_working_changed_files", return_value=[]),
                patch("diffui.git_utils.get_file_mtime", side_effect=lambda p: 1500.0 if p == "changed.py" else 2000.0),
            ):
                _apply_state_updates(["files_changed"])

            assert "changed.py" not in app_state.reviewed
            assert "untouched.py" in app_state.reviewed
        finally:
            app_state.reviewed = prev_reviewed
            app_state.numstat = prev_numstat
            app_state.working_files = prev_working

    def test_git_changed_also_unreviews_modified_files(self):
        prev_reviewed = app_state.reviewed.copy()
        try:
            app_state.reviewed = {"changed.py": 1000.0}
            with (
                patch("diffui.server.state.app_state.reload_repo_state"),
                patch("diffui.server.routes_diff.clear_diff_cache"),
                patch("diffui.git_utils.get_file_mtime", return_value=2000.0),
                patch("diffui.git_utils.save_reviewed"),
            ):
                _apply_state_updates(["git_changed"])

            assert "changed.py" not in app_state.reviewed
        finally:
            app_state.reviewed = prev_reviewed

    def test_files_changed_keeps_reviewed_when_mtime_matches(self):
        prev_reviewed = app_state.reviewed.copy()
        prev_numstat = app_state.numstat
        prev_working = app_state.working_files
        try:
            app_state.reviewed = {"stable.py": 3000.0}
            with (
                patch("diffui.git_utils.get_diff_numstat", return_value={}),
                patch("diffui.git_utils.get_working_changed_files", return_value=[]),
                patch("diffui.git_utils.get_file_mtime", return_value=3000.0),
            ):
                _apply_state_updates(["files_changed"])

            assert "stable.py" in app_state.reviewed
        finally:
            app_state.reviewed = prev_reviewed
            app_state.numstat = prev_numstat
            app_state.working_files = prev_working


class TestWatcherLifecycle:
    def test_do_restart_sets_cancel_event(self):

        import diffui.server.events as events

        prev_cancel = events._watch_cancel
        old_event = MagicMock()
        events._watch_cancel = old_event
        try:
            with (
                patch.object(events.asyncio, "get_event_loop") as get_loop,
                patch.object(events, "_watch_loop", return_value=MagicMock()),
            ):
                events._do_restart()

            old_event.set.assert_called_once()
            assert events._watch_cancel is not old_event
            assert isinstance(events._watch_cancel, asyncio.Event)
            get_loop.return_value.create_task.assert_called_once()
        finally:
            events._watch_cancel = prev_cancel

    def test_do_restart_handles_no_prior_cancel(self):

        import diffui.server.events as events

        prev_cancel = events._watch_cancel
        events._watch_cancel = None
        try:
            with (
                patch.object(events.asyncio, "get_event_loop") as get_loop,
                patch.object(events, "_watch_loop", return_value=MagicMock()),
            ):
                events._do_restart()

            assert isinstance(events._watch_cancel, asyncio.Event)
            get_loop.return_value.create_task.assert_called_once()
        finally:
            events._watch_cancel = prev_cancel

    def test_restart_watcher_noop_without_loop(self):

        import diffui.server.events as events

        with patch.object(events, "_loop", None), patch.object(events, "_do_restart") as do_restart:
            events.restart_watcher()

        do_restart.assert_not_called()

    def test_restart_watcher_schedules_threadsafe(self):

        import diffui.server.events as events

        loop = MagicMock()
        with patch.object(events, "_loop", loop):
            events.restart_watcher()

        loop.call_soon_threadsafe.assert_called_once_with(events._do_restart)

    def test_start_poller_sets_loop_and_restarts(self):

        import diffui.server.events as events

        prev_loop = events._loop
        loop = MagicMock()
        try:
            with (
                patch.object(events.asyncio, "get_event_loop", return_value=loop),
                patch.object(events, "_do_restart") as do_restart,
            ):
                events.start_poller()

            assert events._loop is loop
            do_restart.assert_called_once()
        finally:
            events._loop = prev_loop
