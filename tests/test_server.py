from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from diffui.cli import export_json
from diffui.git_utils import set_active_repo
from diffui.server import routes_review
from diffui.server.app import create_app
from diffui.server.events import _apply_state_updates
from diffui.server.routes_diff import _order_files, _score_risk
from diffui.server.routes_review import _process_status
from diffui.server.theme_css import generate_css_vars
from diffui.server.turns import TurnTracker, poll_once
from diffui.themes.definitions import ALL_THEMES
from tests.conftest import _git, post_comment


class TestServerRoutes:
    def test_index_returns_html(self, _server_app):
        r = _server_app.get("/")
        assert r.status_code == 200
        assert "diffui" in r.text

    def test_repos(self, _server_app, temp_repo):
        repos = _server_app.get("/api/repos").json()
        assert [(r["name"], r["has_changes"], r["active"]) for r in repos] == [(temp_repo.name, True, True)]

    def test_commits(self, _server_app):
        commits = _server_app.get("/api/commits").json()
        assert [(c["message"], c["files"]) for c in commits] == [
            ("reword two lines", ["app.py"]),
            ("add extra module", ["extra.py"]),
        ]

    def test_files(self, _server_app):
        files = _server_app.get("/api/files?view=all").json()
        assert [f["path"] for f in files] == ["app.py", "extra.py", "untracked.txt"]
        assert {k: files[0][k] for k in ("short_name", "reviewed", "adds", "dels", "risk_level", "ignored")} == {
            "short_name": "app.py",
            "reviewed": False,
            "adds": 3,
            "dels": 2,
            "risk_level": "low",
            "ignored": False,
        }

    def test_diff(self, _server_app):
        data = _server_app.get("/api/diff/app.py?view=all").json()
        assert (data["file_path"], data["adds"], data["dels"]) == ("app.py", 3, 2)
        assert data["hunks"]

    def test_themes(self, _server_app):
        r = _server_app.get("/api/themes")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == len(ALL_THEMES)
        assert all("name" in t for t in data)

    @pytest.mark.parametrize("requested, expected", [(1, 1), (len(ALL_THEMES), 0)])
    def test_settings_switches_theme(self, _server_app, requested, expected):
        _server_app.put("/api/settings", json={"theme_index": 0})
        try:
            _server_app.put("/api/settings", json={"theme_index": requested})
            active = [t["index"] for t in _server_app.get("/api/themes").json() if t["active"]]
            assert active == [expected]
            css = _server_app.get("/api/theme/css").json()["css"]
            assert css == generate_css_vars(ALL_THEMES[expected])
        finally:
            _server_app.put("/api/settings", json={"theme_index": 0})

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("editor", "nvim"),
            ("agent_cli", "codex"),
            ("font_size", 16),
            ("word_wrap", True),
            ("keybindings", {"toggle-review": "R", "sort-risk": "x"}),
        ],
    )
    def test_settings_roundtrip(self, _server_app, key, value):
        original = _server_app.get("/api/settings").json()[key]
        try:
            assert _server_app.put("/api/settings", json={key: value}).status_code == 200
            assert _server_app.get("/api/settings").json()[key] == value
        finally:
            _server_app.put("/api/settings", json={key: original})

    def test_comment_crud(self, _server_app):
        cid = post_comment(_server_app, comment="test comment")
        comment = _server_app.get("/api/comments").json()["app.py"][0]
        assert (comment["id"], comment["comment"], comment["status"]) == (cid, "test comment", "open")
        assert comment["timestamp"]

        assert _server_app.put(f"/api/comments/app.py/{cid}", json={"comment": "edited"}).status_code == 200
        assert _server_app.get("/api/comments").json()["app.py"][0]["comment"] == "edited"

        assert _server_app.post(f"/api/comments/app.py/{cid}/reply", json={"text": "reply"}).status_code == 200
        replies = _server_app.get("/api/comments").json()["app.py"][0]["replies"]
        assert [r["text"] for r in replies] == ["reply"]

        assert _server_app.delete(f"/api/comments/app.py/{cid}").status_code == 200
        assert _server_app.get("/api/comments").json() == {}

    def test_comment_resolve_toggle(self, _server_app):
        cid = post_comment(_server_app)

        def status():
            return _server_app.get("/api/comments").json()["app.py"][0]["status"]

        assert status() == "open"
        _server_app.post(f"/api/comments/app.py/{cid}/resolve")
        assert status() == "resolved"
        _server_app.post(f"/api/comments/app.py/{cid}/resolve")
        assert status() == "open"

    def test_review_toggle(self, _server_app):
        assert _server_app.post("/api/reviewed/app.py").json()["reviewed"] is True
        assert _server_app.post("/api/reviewed/app.py").json()["reviewed"] is False

    def test_static_files(self, _server_app):
        r = _server_app.get("/static/app.js")
        assert r.status_code == 200
        r = _server_app.get("/static/style.css")
        assert r.status_code == 200

    @pytest.mark.parametrize(
        ("fields", "stored"),
        [
            pytest.param(
                {},
                {"category": "", "suggestion": "", "selected_text": "", "sel_start": None, "sel_end": None},
                id="defaults",
            ),
            pytest.param({"category": "bug"}, {"category": "bug"}, id="category"),
            pytest.param({"suggestion": "x = 1\n"}, {"suggestion": "x = 1\n"}, id="suggestion"),
            pytest.param(
                {"selected_text": "bar.baz", "sel_start": 12, "sel_end": 19},
                {"selected_text": "bar.baz", "sel_start": 12, "sel_end": 19, "sel_end_index": None},
                id="selection",
            ),
            pytest.param(
                {
                    "line_index": 4,
                    "selected_text": "if x:\n    return y",
                    "sel_start": 4,
                    "sel_end": 12,
                    "sel_end_index": 6,
                },
                {"line_index": 4, "sel_start": 4, "sel_end": 12, "sel_end_index": 6},
                id="multiline-selection",
            ),
        ],
    )
    def test_comment_fields_are_stored(self, _server_app, fields, stored):
        post_comment(_server_app, **fields)
        comment = _server_app.get("/api/comments").json()["app.py"][0]
        assert {k: comment[k] for k in stored} == stored

    def test_blame_attributes_each_line_to_its_commit(self, _server_app):
        blame = _server_app.get("/api/blame/app.py").json()
        assert len(blame) == 21
        assert all(len(entry["sha"]) == 8 for entry in blame)
        assert blame[0]["author"] == "diffui test"
        assert blame[4]["sha"] != blame[0]["sha"]
        assert blame[20]["author"] == "Not Committed Yet"

    def test_blame_unknown_file(self, _server_app):
        r = _server_app.get("/api/blame/_nonexistent_path_.py")
        assert r.status_code == 200
        assert r.json() == []

    def test_preview_text_file(self, _server_app):
        data = _server_app.get("/api/preview/app.py").json()
        assert data["type"] == "text"
        assert data["content"].startswith("line 1\nline 2\n")

    def test_preview_image_not_found(self, _server_app):
        r = _server_app.get("/api/preview/_fake_.png")
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "image"
        assert data["exists"] is False

    def test_review_summary_returns_markdown(self, _server_app):
        r = _server_app.get("/api/review-summary")
        assert r.status_code == 200
        md = r.json()["markdown"]
        assert "# Review Summary:" in md
        total = len(_server_app.get("/api/files").json())
        assert f"/{total} reviewed" in md

    def test_session_put_is_additive(self, _server_app):
        _server_app.put("/api/session", json={"activeFile": "a.py"})
        _server_app.put("/api/session", json={"diffMode": "split"})
        session = _server_app.get("/api/session").json()
        assert session.get("activeFile") == "a.py"
        assert session.get("diffMode") == "split"

    def test_websocket_connected_event(self, _server_app):
        with _server_app.websocket_connect("ws://localhost/api/ws") as ws:
            data = json.loads(ws.receive_text())
            assert data == {"events": ["connected"]}

    def test_websocket_ping_pong(self, _server_app):
        with _server_app.websocket_connect("ws://localhost/api/ws") as ws:
            ws.receive_text()  # consume connected
            ws.send_text(json.dumps({"type": "ping"}))
            data = json.loads(ws.receive_text())
            assert data == {"type": "pong"}

    @pytest.mark.parametrize("route", ["agent", "explain"])
    def test_status_reports_nothing_running(self, _server_app, route):
        assert _server_app.get(f"/api/{route}/status").json()["running"] is False

    @pytest.mark.parametrize("route", ["run", "prompt"])
    def test_agent_routes_refuse_without_open_comments(self, _server_app, route):
        data = _server_app.post(f"/api/agent/{route}").json()
        assert data["ok"] is False
        assert "No open comments" in data["error"]

    def test_explain_view_placeholder(self, _server_app):
        r = _server_app.get("/api/explain/view")
        assert r.status_code == 200
        assert "No explanation generated yet" in r.text

    def test_bulk_resolve_and_reopen_one_file(self, _server_app):
        post_comment(_server_app, line_index=1)
        post_comment(_server_app, line_index=2)
        post_comment(_server_app, file_path="extra.py")

        def statuses(path):
            return [c["status"] for c in _server_app.get("/api/comments").json()[path]]

        r = _server_app.post("/api/comments/bulk-resolve", json={"file_path": "app.py", "action": "resolve"})
        assert r.json() == {"ok": True, "count": 2}
        assert statuses("app.py") == ["resolved", "resolved"]
        assert statuses("extra.py") == ["open"]

        r = _server_app.post("/api/comments/bulk-resolve", json={"file_path": "app.py", "action": "reopen"})
        assert r.json() == {"ok": True, "count": 2}
        assert statuses("app.py") == ["open", "open"]

    def test_bulk_resolve_without_a_file_covers_every_file(self, _server_app):
        post_comment(_server_app)
        post_comment(_server_app, file_path="extra.py")
        assert _server_app.post("/api/comments/bulk-resolve", json={"action": "resolve"}).json()["count"] == 2

    def test_diff_context_widens_the_hunks(self, _server_app):
        def context_lines(**params):
            hunks = _server_app.get("/api/diff/app.py", params={"view": "all", **params}).json()["hunks"]
            return [ln for h in hunks for ln in h["lines"] if ln["type"] == "context"]

        assert len(context_lines(context=10)) > len(context_lines())

    def test_diff_ignore_whitespace_drops_whitespace_only_changes(self, _server_app, temp_repo):
        app_py = temp_repo / "app.py"
        original = app_py.read_text()
        app_py.write_text(original.replace("line 1\n", "line 1  \n", 1))
        try:

            def stats(**params):
                data = _server_app.get("/api/diff/app.py", params={"view": "all", **params}).json()
                return data["adds"], data["dels"]

            assert stats() == (4, 3)
            assert stats(ignore_whitespace="true") == (3, 2)
        finally:
            app_py.write_text(original)

    def test_repo_switch_invalid_index(self, _server_app):
        r = _server_app.post("/api/repo/switch", json={"index": 999})
        assert r.status_code == 400

    def test_review_summary_lists_open_comments_by_category(self, _server_app):
        post_comment(_server_app, comment="fix this bug", file_line_num=10, category="bug")
        post_comment(_server_app, comment="a nit", file_line_num=2, category="nit")
        post_comment(_server_app, comment="already handled", status="resolved")
        md = _server_app.get("/api/review-summary").json()["markdown"]
        assert "3 total, 2 open, 1 resolved" in md
        assert "### Bug\n\n- **app.py:10** — fix this bug" in md
        assert "### Nit\n\n- **app.py:2** — a nit" in md
        assert "already handled" not in md

    def test_agent_prompt_with_comments(self, _server_app):
        post_comment(_server_app, comment="rename this variable", file_line_num=5, category="suggestion")
        data = _server_app.post("/api/agent/prompt").json()
        assert data["ok"] is True
        assert "rename this variable" in data["prompt"]
        assert data["comment_count"] == 1
        assert "context_path" in data
        assert "agent_cli" in data

    @pytest.mark.parametrize(
        ("editor", "args"),
        [("code", ["--goto", "{path}:3"]), ("nvim", ["+3", "{path}"])],
    )
    def test_editor_open_launches_the_editor_at_the_line(self, _server_app, temp_repo, editor, args):
        original = _server_app.get("/api/settings").json()["editor"]
        _server_app.put("/api/settings", json={"editor": editor})
        try:
            with patch("diffui.server.routes_settings.subprocess.Popen") as popen:
                r = _server_app.post("/api/editor/open", json={"file_path": "app.py", "line_num": 3})
        finally:
            _server_app.put("/api/settings", json={"editor": original})
        assert r.json() == {"ok": True}
        path = str((temp_repo / "app.py").resolve())
        assert popen.call_args.args[0] == [editor, *(a.format(path=path) for a in args)]

    def test_files_view_working(self, _server_app):
        files = _server_app.get("/api/files?view=working").json()
        assert [f["path"] for f in files] == ["app.py", "untracked.txt"]

    def test_files_view_commit_sha(self, _server_app):
        commits = _server_app.get("/api/commits").json()
        assert len(commits) == 2
        for commit in commits:
            files = _server_app.get(f"/api/files?view={commit['sha']}").json()
            assert [f["path"] for f in files] == commit["files"]

    def test_files_view_unknown_commit(self, _server_app):
        r = _server_app.get("/api/files?view=deadbeefdeadbeef")
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.parametrize("route", ["diff", "file"])
    def test_html_off_drops_only_the_html(self, _server_app, route):
        def lines(data):
            return data["lines"] if route == "file" else [ln for h in data["hunks"] for ln in h["lines"]]

        with_html = lines(_server_app.get(f"/api/{route}/app.py?view=all").json())
        without = lines(_server_app.get(f"/api/{route}/app.py?view=all&html=0").json())
        assert with_html and all("html" in ln for ln in with_html)
        assert not any("html" in ln for ln in without)
        assert [{k: v for k, v in ln.items() if k != "html"} for ln in with_html] == without

    def test_repo_switch_valid_index(self, _server_app):
        original = _server_app.get("/api/repos").json()
        active = next((r["index"] for r in original if r["active"]), 0)
        try:
            r = _server_app.post("/api/repo/switch", json={"index": 0})
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is True
            assert "branch" in data
        finally:
            _server_app.post("/api/repo/switch", json={"index": active})

    def test_branch(self, _server_app, temp_repo):
        data = _server_app.get("/api/branch").json()
        assert (data["name"], data["main_branch"], data["repo_name"]) == ("feature", "main", temp_repo.name)
        assert len(data["head_sha"]) == 40
        assert data["merge_base"] != data["head_sha"]
        assert data["remote_url"] == ""


class TestReviewModule:
    def test_build_agent_context_no_comments(self):

        with patch.object(routes_review.app_state, "comments", {}):
            result = routes_review._build_agent_context()
        assert result[0] is None
        assert result[1] == "No open comments"

    def test_build_agent_context_with_comments(self):

        comments = {
            "src/auth.py": [
                {
                    "id": "abc",
                    "comment": "this is wrong",
                    "category": "bug",
                    "file_line_num": 12,
                    "line_text": "x = bad()",
                    "suggestion": "x = good()",
                    "status": "open",
                    "replies": [{"author": "claude", "text": "looking into it"}],
                }
            ],
            "src/resolved.py": [{"id": "def", "comment": "old", "status": "resolved", "replies": []}],
        }
        with patch.object(routes_review.app_state, "comments", comments):
            prompt, repo_root, context_path, count = routes_review._build_agent_context()

        assert prompt is not None
        assert count == 1
        assert "this is wrong" in prompt
        assert repo_root
        assert context_path

        ctx = Path(context_path).read_text()
        assert "### src/auth.py" in ctx
        assert "this is wrong" in ctx
        assert "x = good()" in ctx
        assert "claude: looking into it" in ctx
        assert "src/resolved.py" not in ctx

    def test_process_status_none(self):

        assert _process_status(None) == {"running": False}

    def test_process_status_running(self):

        proc = MagicMock()
        proc.poll.return_value = None
        proc.pid = 4242
        assert _process_status(proc) == {"running": True, "pid": 4242}

    def test_process_status_finished(self):

        proc = MagicMock()
        proc.poll.return_value = 0
        assert _process_status(proc) == {"running": False, "exit_code": 0}

    def test_explain_already_running(self, _server_app):

        running = MagicMock()
        running.poll.return_value = None
        with patch.object(routes_review, "_explain_process", running):
            r = _server_app.post("/api/explain")
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is False
            assert "already generating" in data["error"]

    def test_explain_unknown_agent(self, _server_app):

        with (
            patch.object(routes_review, "_explain_process", None),
            patch.object(routes_review.app_state, "agent_cli", "bogus-cli"),
        ):
            r = _server_app.post("/api/explain")
            assert r.status_code == 200
            data = r.json()
            assert data["ok"] is False
            assert "Unknown agent CLI" in data["error"]

    def test_view_explanation_with_temp_file(self, _server_app):

        # Resolve gettempdir so the module's startswith() guard matches the
        # symlink-resolved path (macOS /var -> /private/var).
        tmp_dir = Path(tempfile.gettempdir()).resolve()
        tmp = tmp_dir / "diffui-explain-test-view.html"
        tmp.write_text("<html><body>generated walkthrough</body></html>")
        try:
            with (
                patch.object(routes_review, "_explain_output_path", str(tmp)),
                patch.object(routes_review.tempfile, "gettempdir", return_value=str(tmp_dir)),
            ):
                r = _server_app.get("/api/explain/view")
                assert r.status_code == 200
                assert "generated walkthrough" in r.text
        finally:
            tmp.unlink(missing_ok=True)

    def test_view_explanation_path_traversal_guard(self, _server_app):

        with patch.object(routes_review, "_explain_output_path", "/etc/passwd"):
            r = _server_app.get("/api/explain/view")
            assert r.status_code == 400
            assert "No explanation generated yet" in r.text

    def test_view_explanation_missing_file(self, _server_app):

        tmp_dir = Path(tempfile.gettempdir()).resolve()
        missing = str(tmp_dir / "diffui-explain-does-not-exist.html")
        with (
            patch.object(routes_review, "_explain_output_path", missing),
            patch.object(routes_review.tempfile, "gettempdir", return_value=str(tmp_dir)),
        ):
            r = _server_app.get("/api/explain/view")
            assert r.status_code == 200
            assert "No explanation generated yet" in r.text


@pytest.mark.parametrize(
    ("path", "adds", "dels", "expected"),
    [
        pytest.param("alembic/versions/001_init.py", 50, 0, (3, "medium", ["infra/migration"]), id="migration"),
        pytest.param("config/settings.yaml", 10, 5, (2, "low", ["config"]), id="config"),
        pytest.param("infra/values.yaml", 1, 1, (5, "high", ["infra/migration", "config"]), id="infra-config"),
        pytest.param("src/module.py", 0, 100, (3, "medium", ["large deletion"]), id="large-deletion"),
        pytest.param("tests/test_auth.py", 5, 30, (3, "medium", ["test removal"]), id="test-removal"),
        pytest.param("tests/test_auth.py", 30, 5, (0, "low", []), id="test-additions-are-not-removals"),
        pytest.param("src/big_refactor.py", 150, 100, (4, "medium", ["large deletion", "high churn"]), id="churn"),
        pytest.param("src/module.py", 0, 30, (1, "low", []), id="moderate-deletion-scores-without-a-reason"),
        pytest.param("src/module.py", 40, 20, (1, "low", []), id="moderate-churn-scores-without-a-reason"),
        pytest.param("src/utils.py", 10, 5, (0, "low", []), id="plain-source"),
        pytest.param("Makefile", 5, 5, (0, "low", []), id="no-extension"),
    ],
)
def test_score_risk(path, adds, dels, expected):
    assert _score_risk(path, adds, dels) == expected


class TestExportJson:
    def test_export_matches_the_files_comments_and_reviews_the_ui_shows(self, _server_app, capsys):
        post_comment(_server_app)
        post_comment(_server_app, file_path="extra.py", status="resolved")
        _server_app.post("/api/reviewed/extra.py")

        export_json()

        exported = json.loads(capsys.readouterr().out)
        assert (exported["branch"], exported["main_branch"]) == ("feature", "main")
        assert exported["summary"] == {
            "total_files": 3,
            "reviewed_files": 1,
            "total_comments": 2,
            "open_comments": 1,
            "resolved_comments": 1,
        }
        assert [f["path"] for f in exported["files"]] == [f["path"] for f in _server_app.get("/api/files").json()]


class TestPathContainment:
    def test_preview_rejects_absolute_path(self, _server_app, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("top secret\n")
        r = _server_app.get(f"/api/preview/{secret}")
        assert r.status_code == 400
        assert "top secret" not in r.text

    def test_file_rejects_absolute_path(self, _server_app, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("top secret\n")
        r = _server_app.get(f"/api/file/{secret}")
        assert r.status_code == 400

    def test_blame_rejects_absolute_path(self, _server_app, tmp_path):
        r = _server_app.get(f"/api/blame/{tmp_path / 'secret.txt'}")
        assert r.status_code == 400

    def test_diff_rejects_absolute_path(self, _server_app, tmp_path):
        r = _server_app.get(f"/api/diff/{tmp_path / 'secret.txt'}")
        assert r.status_code == 400

    def test_reviewed_rejects_absolute_path(self, _server_app, tmp_path):
        r = _server_app.post(f"/api/reviewed/{tmp_path / 'secret.txt'}")
        assert r.status_code == 400

    def test_editor_open_rejects_absolute_path(self, _server_app, tmp_path):
        r = _server_app.post("/api/editor/open", json={"file_path": str(tmp_path / "secret.txt")})
        assert r.status_code == 400

    def test_comment_rejects_absolute_path(self, _server_app, tmp_path):
        r = _server_app.post(
            "/api/comments",
            json={"file_path": str(tmp_path / "outside.py"), "line_index": 0, "comment": "x"},
        )
        assert r.status_code == 400

    def test_apply_suggestion_cannot_write_outside_repo(self, _server_app, temp_repo, tmp_path):
        outside = tmp_path / "outside.py"
        outside.write_text("original\n")
        link = temp_repo / "escape.py"
        link.symlink_to(outside)
        try:
            _server_app.post(
                "/api/comments",
                json={
                    "file_path": "escape.py",
                    "line_index": 0,
                    "file_line_num": 1,
                    "comment": "replace it",
                    "suggestion": "overwritten",
                },
            )
            comments = _server_app.get("/api/comments").json().get("escape.py", [])
            assert comments == []
            assert outside.read_text() == "original\n"
        finally:
            link.unlink()


class TestDiffViewValidation:
    def test_unknown_view_returns_empty_diff(self, _server_app):
        r = _server_app.get("/api/diff/app.py", params={"view": "deadbeefdeadbeef"})
        assert r.status_code == 200
        assert r.json()["hunks"] == []

    def test_option_shaped_view_does_not_reach_git(self, _server_app, tmp_path):
        target = tmp_path / "written-by-git.diff"
        r = _server_app.get("/api/diff/app.py", params={"view": f"--output={target}"})
        assert r.status_code == 200
        assert not target.exists()

    def test_known_commit_sha_still_works(self, _server_app):
        sha = _server_app.get("/api/commits").json()[0]["sha"]
        data = _server_app.get(f"/api/diff/app.py?view={sha}").json()
        assert (data["adds"], data["dels"]) == (2, 2)


class TestExplainViewGuard:
    def test_sibling_of_tempdir_is_rejected(self, _server_app, tmp_path):

        evil = Path(f"{tempfile.gettempdir()}-evil") / "payload.html"
        with patch("diffui.server.routes_review._explain_output_path", str(evil)):
            r = _server_app.get("/api/explain/view")
        assert r.status_code == 400


@pytest.fixture
def app_py(temp_repo):
    path = temp_repo / "app.py"
    original = path.read_text()
    yield path
    path.write_text(original)


class TestApplySuggestion:
    @pytest.mark.parametrize(
        ("fields", "status", "detail"),
        [
            pytest.param({"file_line_num": 1}, 400, "No suggestion", id="no-suggestion"),
            pytest.param({"suggestion": "x = 1\n"}, 400, "No line number", id="no-line-number"),
            pytest.param(
                {"file_line_num": 1, "line_text": "-this line is long gone", "suggestion": "replacement"},
                409,
                "changed since",
                id="stale-line-text",
            ),
            pytest.param(
                {"file_line_num": 1, "line_text": " line 1", "suggestion": "replacement", "sel_end_index": 4},
                400,
                "more than one line",
                id="multi-line-range",
            ),
        ],
    )
    def test_refusals_leave_the_file_and_comment_alone(self, _server_app, app_py, fields, status, detail):
        before = app_py.read_text()
        cid = post_comment(_server_app, **fields)
        r = _server_app.post(f"/api/comments/app.py/{cid}/apply")
        assert (r.status_code, detail in r.json()["detail"]) == (status, True)
        assert app_py.read_text() == before
        assert _server_app.get("/api/comments").json()["app.py"][0]["status"] == "open"

    @pytest.mark.parametrize(
        "fields",
        [
            pytest.param({"line_text": " line 1"}, id="matching-line-text"),
            pytest.param({}, id="no-line-text"),
        ],
    )
    def test_replaces_the_line_and_resolves_the_comment(self, _server_app, app_py, fields):
        before = app_py.read_text()
        cid = post_comment(_server_app, file_line_num=1, suggestion="line one", **fields)
        assert _server_app.post(f"/api/comments/app.py/{cid}/apply").json() == {"ok": True}
        assert app_py.read_text() == before.replace("line 1\n", "line one\n", 1)
        assert _server_app.get("/api/comments").json()["app.py"][0]["status"] == "resolved"

    def test_unknown_comment_is_refused(self, _server_app):
        assert _server_app.post("/api/comments/app.py/no-such-id/apply").status_code == 400


class TestSettingsValidation:
    def test_unknown_editor_is_rejected(self, _server_app):
        r = _server_app.put("/api/settings", json={"editor": "rm -rf /"})
        assert r.status_code == 422

    def test_unknown_agent_cli_is_rejected(self, _server_app):
        r = _server_app.put("/api/settings", json={"agent_cli": "curl"})
        assert r.status_code == 422


_FAKE_HERDR = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["HERDR_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:3] == ["agent", "list"]:
    print(json.dumps({"result": {"agents": json.loads(os.environ["HERDR_AGENTS"])}}))
"""


@pytest.fixture
def fake_herdr(tmp_path, monkeypatch):
    (tmp_path / "herdr").write_text(_FAKE_HERDR)
    (tmp_path / "herdr").chmod(0o755)
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    monkeypatch.setenv("HERDR_LOG", str(log))
    monkeypatch.setenv("HERDR_WORKSPACE_ID", "w1")

    def calls():
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    return calls


def _agent(pane_id, cwd, status="idle"):
    return {
        "pane_id": pane_id,
        "workspace_id": pane_id.split(":")[0],
        "agent": "claude",
        "agent_status": status,
        "cwd": str(cwd),
    }


class TestHerdr:
    def _paste(self, client, monkeypatch, agents):
        monkeypatch.setenv("HERDR_AGENTS", json.dumps(agents))
        post_comment(client, file_line_num=5, comment="end\x1b[201~\rrm -rf ~")
        return client.post("/api/agent/paste").json()

    @pytest.mark.parametrize(
        ("agents", "target"),
        [
            pytest.param(
                lambda repo: [_agent("w2:p1", repo), _agent("w1:p2", "/"), _agent("w1:p3", repo / "sub")],
                "w1:p3",
                id="prefers-repo-agent-in-own-workspace",
            ),
            pytest.param(
                lambda repo: [_agent("w2:p1", repo), _agent("w1:p2", "/", "working")],
                "w1:p2",
                id="falls-back-to-workspace-agent",
            ),
        ],
    )
    def test_paste_sends_one_bracketed_paste_to_the_right_agent(
        self, _server_app, temp_repo, fake_herdr, monkeypatch, agents, target
    ):
        (temp_repo / "sub").mkdir(exist_ok=True)
        assert self._paste(_server_app, monkeypatch, agents(temp_repo)) == {"ok": True, "agent": "claude"}
        [(_, _, pane, text)] = [c for c in fake_herdr() if c[:2] == ["pane", "send-text"]]
        assert pane == target
        assert text.startswith("\x1b[200~") and text.endswith("\x1b[201~")
        assert text.count("\x1b[201~") == 1
        assert ["agent", "focus", target] in fake_herdr()

    def test_prompt_names_the_pane_agent_only_inside_a_workspace(self, _server_app, temp_repo, fake_herdr, monkeypatch):
        monkeypatch.setenv("HERDR_AGENTS", json.dumps([_agent("w1:p1", temp_repo)]))
        post_comment(_server_app)
        assert _server_app.post("/api/agent/prompt").json()["pane_agent"] == "claude"
        monkeypatch.delenv("HERDR_WORKSPACE_ID")
        assert _server_app.post("/api/agent/prompt").json()["pane_agent"] is None

    def test_paste_refuses_blocked_agent(self, _server_app, temp_repo, fake_herdr, monkeypatch):
        r = self._paste(_server_app, monkeypatch, [_agent("w1:p1", temp_repo, "blocked")])
        assert r["ok"] is False
        assert not [c for c in fake_herdr() if c[:2] == ["pane", "send-text"]]

    def test_reviewing_a_file_reports_sidebar_counts(self, _server_app, fake_herdr):

        post_comment(_server_app)
        _server_app.post("/api/reviewed/app.py")
        # The watcher sees reviewed.json change and runs this; TestClient never starts the watcher.
        _apply_state_updates(["files_changed"])
        total = len(_server_app.get("/api/files").json())
        [*_, report] = [c for c in fake_herdr() if c[:2] == ["workspace", "report-metadata"]]
        assert report[2:] == [
            "w1",
            "--source",
            "diffui",
            "--token",
            "comments=1 open",
            "--token",
            f"reviewed=☑ 1/{total}",
        ]


def _entry(path: str, risk: int = 0) -> dict:
    return {"path": path, "dir": path.rpartition("/")[0] or ".", "risk_score": risk}


def test_order_files_mirrors_the_web_tree():
    files = [_entry("a/z.py"), _entry("b/y.py", 5), _entry("top.py", 3), _entry("a/b/x.py")]
    assert [f["path"] for f in _order_files(files, "tree")] == ["top.py", "a/z.py", "a/b/x.py", "b/y.py"]
    assert [f["path"] for f in _order_files(files, "risk")] == ["b/y.py", "top.py", "a/z.py", "a/b/x.py"]


class TestSearch:
    def test_matches_file_names_and_content_of_the_view(self, _server_app):
        r = _server_app.get("/api/search", params={"q": "EXTRA"}).json()
        assert r["files"] == [{"path": "extra.py", "changed": True}]
        assert r["hits"] == []

        r = _server_app.get("/api/search", params={"q": "line five"}).json()
        assert r["hits"] == [{"path": "app.py", "line": 5, "text": "line five", "changed": True}]

        # Content comes from the working tree, so an untracked file is searched too.
        r = _server_app.get("/api/search", params={"q": "never committed"}).json()
        assert [(h["path"], h["line"]) for h in r["hits"]] == [("untracked.txt", 1)]

    def test_search_is_scoped_to_the_view(self, _server_app):
        r = _server_app.get("/api/search", params={"q": "value", "view": "working"}).json()
        assert r["hits"] == []
        assert _server_app.get("/api/search", params={"q": "value"}).json()["hits"][0]["path"] == "extra.py"

    @pytest.mark.parametrize(("scope", "query"), [("changed", "line"), ("all", "render")])
    def test_hits_are_capped(self, _server_app, monkeypatch, scope, query):
        monkeypatch.setattr("diffui.server.routes_search.MAX_HITS", 3)
        r = _server_app.get("/api/search", params={"q": query, "scope": scope}).json()
        assert len(r["hits"]) == 3
        assert r["truncated"] is True

    def test_empty_query_finds_nothing(self, _server_app):
        assert _server_app.get("/api/search", params={"q": ""}).json() == {"files": [], "hits": [], "truncated": False}


class TestWholeRepoSearch:
    def test_all_scope_finds_files_outside_the_diff_and_marks_the_changed_ones(self, _server_app):
        def search(q, scope="all"):
            return _server_app.get("/api/search", params={"q": q, "scope": scope}).json()

        assert search("rendrer")["files"] == [{"path": "renderer.py", "changed": False}]
        assert search("RENDER_25")["hits"] == [
            {"path": "renderer.py", "line": 25, "text": "def render_25(): ...", "changed": False}
        ]
        assert search("extrra")["files"] == [{"path": "extra.py", "changed": True}]
        assert [(h["path"], h["changed"]) for h in search("line five")["hits"]] == [("app.py", True)]

        assert search("rendrer", scope="changed")["files"] == []
        assert search("extrra", scope="changed")["files"] == [{"path": "extra.py", "changed": True}]

    @pytest.fixture
    def own_repo(self, tmp_path, temp_repo):

        (tmp_path / ".gitignore").write_text("generated/\n")
        (tmp_path / "generated").mkdir()
        (tmp_path / "generated" / "out.py").write_text("needle\n")
        (tmp_path / "blob.bin").write_bytes(b"\0needle")
        (tmp_path / "keep.py").write_text("needle\n")
        for args in (("init", "-q", "-b", "main"), ("add", "-A"), ("commit", "-qm", "init")):
            _git(tmp_path, *args)
        set_active_repo(tmp_path)
        yield TestClient(create_app([tmp_path]), base_url="http://localhost"), tmp_path
        set_active_repo(temp_repo)
        create_app([temp_repo])

    def test_files_written_after_the_first_search_are_found(self, own_repo):

        client, repo = own_repo

        def search(q):
            return client.get("/api/search", params={"q": q, "scope": "all"}).json()

        assert [h["path"] for h in search("needle")["hits"]] == ["keep.py"]

        (repo / "later.py").write_text("needle again\n")
        _apply_state_updates(["files_changed"])
        assert [h["path"] for h in search("needle")["hits"]] == ["keep.py", "later.py"]
        assert [f["path"] for f in search("laterr")["files"]] == ["later.py"]

        (repo / "later.py").unlink()
        _apply_state_updates(["files_changed"])
        assert [h["path"] for h in search("needle")["hits"]] == ["keep.py"]


@pytest.mark.parametrize(
    ("samples", "starts"),
    [
        pytest.param([["idle"], ["working"]], [1], id="rest-to-work"),
        pytest.param([[], ["working"]], [1], id="no-agent-then-work"),
        pytest.param([["working"], ["working"], ["idle"], ["working"]], [3], id="already-working-when-first-seen"),
        pytest.param([["idle"], ["blocked"], ["working"]], [], id="work-after-a-prompt-is-the-same-turn"),
        pytest.param([["idle", "working"], ["idle", "working"]], [], id="two-agents-one-turn"),
    ],
)
def test_turn_tracker_starts_on_the_rest_to_work_edge(samples, starts):

    tracker = TurnTracker()
    assert [i for i, statuses in enumerate(samples) if tracker.observe(statuses)] == starts


class TestLastTurn:
    def _git(self, repo, *args):

        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout

    def test_lists_only_files_changed_since_the_turn_started(self, _server_app, temp_repo, fake_herdr, monkeypatch):

        reason = _server_app.get("/api/last-turn").json()["reason"]
        assert reason.startswith("No agent turn seen yet")
        assert _server_app.get("/api/files?view=last-turn").json() == []

        tracker = TurnTracker()
        index_before = self._git(temp_repo, "ls-files", "--stage")
        staged_before = self._git(temp_repo, "diff", "--cached")
        for status in ("idle", "working"):
            monkeypatch.setenv("HERDR_AGENTS", json.dumps([_agent("w1:p2", temp_repo, status)]))
            started = poll_once(tracker)
        assert started is True
        assert _server_app.get("/api/last-turn").json()["reason"] == "Nothing has changed since the last turn started"

        extra, fresh = temp_repo / "extra.py", temp_repo / "fresh.txt"
        try:
            extra.write_text("VALUE = 1\nVALUE = 2\n")
            fresh.write_text("brand new\n")
            _apply_state_updates(["files_changed"])

            files = _server_app.get("/api/files?view=last-turn").json()
            assert [(f["path"], f["adds"], f["dels"]) for f in files] == [("extra.py", 1, 0), ("fresh.txt", 1, 0)]
            assert _server_app.get("/api/last-turn").json()["reason"] is None
            diff = _server_app.get("/api/diff/extra.py?view=last-turn").json()
            assert [ln["text"] for h in diff["hunks"] for ln in h["lines"] if ln["type"] == "add"] == ["+VALUE = 2"]
            assert self._git(temp_repo, "ls-files", "--stage") == index_before
            assert self._git(temp_repo, "diff", "--cached") == staged_before
        finally:
            extra.write_text("VALUE = 1\n")
            fresh.unlink(missing_ok=True)
            self._git(temp_repo, "update-ref", "-d", "refs/worktree/diffui/last-turn")
            _apply_state_updates(["files_changed"])
        assert _server_app.get("/api/files?view=last-turn").json() == []


class TestLocalOriginOnly:
    @pytest.mark.parametrize(
        ("headers", "status"),
        [
            pytest.param({"origin": "https://evil.example"}, 403, id="foreign-origin"),
            pytest.param({"host": "evil.example"}, 403, id="rebound-host"),
            pytest.param({"origin": "http://localhost"}, 200, id="same-origin"),
        ],
    )
    def test_requests_from_other_sites_are_rejected(self, _server_app, headers, status):
        assert _server_app.get("/api/files", headers=headers).status_code == status

    def test_foreign_websocket_is_rejected(self, _server_app):

        with (
            pytest.raises(WebSocketDisconnect),
            _server_app.websocket_connect(
                "ws://localhost/api/agent/ws", headers={"origin": "https://evil.example"}
            ) as ws,
        ):
            ws.receive_json()
