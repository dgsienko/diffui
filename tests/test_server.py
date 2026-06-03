from __future__ import annotations

from pathlib import Path

import pytest

from diffui.server.theme_css import generate_css_vars
from diffui.themes.definitions import ALL_THEMES, CATPPUCCIN_MOCHA, GITHUB_DARK


class TestGenerateCssVars:
    def test_contains_root(self):
        result = generate_css_vars(CATPPUCCIN_MOCHA)
        assert result.startswith(":root {")
        assert result.endswith("}")

    def test_contains_bg(self):
        result = generate_css_vars(CATPPUCCIN_MOCHA)
        assert f"--bg: {CATPPUCCIN_MOCHA.bg};" in result

    def test_skips_name(self):
        result = generate_css_vars(CATPPUCCIN_MOCHA)
        assert "--name:" not in result

    def test_skips_syntax(self):
        result = generate_css_vars(CATPPUCCIN_MOCHA)
        assert "--syntax:" not in result

    def test_underscores_become_hyphens(self):
        result = generate_css_vars(CATPPUCCIN_MOCHA)
        assert "--bg-dark:" in result
        assert "--bg_dark:" not in result

    def test_different_themes_produce_different_css(self):
        mocha = generate_css_vars(CATPPUCCIN_MOCHA)
        github = generate_css_vars(GITHUB_DARK)
        assert mocha != github


@pytest.fixture(scope="class")
def _server_app():
    from diffui.git_utils import resolve_repo_root, set_active_repo
    from diffui.server.app import create_app

    root = resolve_repo_root(Path(__file__).parent.parent)
    set_active_repo(root)
    app = create_app([root])

    from fastapi.testclient import TestClient

    return TestClient(app)


class TestServerRoutes:
    def test_index_returns_html(self, _server_app):
        r = _server_app.get("/")
        assert r.status_code == 200
        assert "diffui" in r.text

    def test_repos(self, _server_app):
        r = _server_app.get("/api/repos")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "name" in data[0]
        assert "has_changes" in data[0]

    def test_branch(self, _server_app):
        r = _server_app.get("/api/branch")
        assert r.status_code == 200
        data = r.json()
        assert "name" in data
        assert "main_branch" in data

    def test_commits(self, _server_app):
        r = _server_app.get("/api/commits")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_files(self, _server_app):
        r = _server_app.get("/api/files?view=all")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "path" in data[0]
            assert "short_name" in data[0]
            assert "reviewed" in data[0]

    def test_diff(self, _server_app):
        files = _server_app.get("/api/files?view=all").json()
        if not files:
            pytest.skip("No changed files")
        path = files[0]["path"]
        r = _server_app.get(f"/api/diff/{path}?view=all")
        assert r.status_code == 200
        data = r.json()
        assert "file_path" in data
        assert "hunks" in data
        assert "adds" in data
        assert "dels" in data

    def test_themes(self, _server_app):
        r = _server_app.get("/api/themes")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == len(ALL_THEMES)
        assert all("name" in t for t in data)

    def test_theme_css(self, _server_app):
        r = _server_app.get("/api/theme/css")
        assert r.status_code == 200
        assert ":root {" in r.json()["css"]

    def test_settings_roundtrip(self, _server_app):
        r = _server_app.get("/api/settings")
        assert r.status_code == 200
        original = r.json()
        assert "editor" in original

        try:
            r = _server_app.put("/api/settings", json={"editor": "nvim"})
            assert r.status_code == 200

            r = _server_app.get("/api/settings")
            assert r.json()["editor"] == "nvim"
        finally:
            _server_app.put("/api/settings", json={"editor": original["editor"]})

    def test_comment_crud(self, _server_app):
        r = _server_app.post(
            "/api/comments",
            json={
                "file_path": "_test_.py",
                "line_index": 1,
                "comment": "test comment",
            },
        )
        assert r.status_code == 200

        try:
            comments = _server_app.get("/api/comments").json()
            assert "_test_.py" in comments
            comment = comments["_test_.py"][0]
            assert comment["comment"] == "test comment"
            assert comment["status"] == "open"
            assert "id" in comment
            assert "timestamp" in comment
            cid = comment["id"]

            r = _server_app.put(f"/api/comments/_test_.py/{cid}", json={"comment": "edited"})
            assert r.status_code == 200
            assert _server_app.get("/api/comments").json()["_test_.py"][0]["comment"] == "edited"

            r = _server_app.post(f"/api/comments/_test_.py/{cid}/reply", json={"text": "reply"})
            assert r.status_code == 200
            replies = _server_app.get("/api/comments").json()["_test_.py"][0]["replies"]
            assert len(replies) == 1
            assert replies[0]["text"] == "reply"

            r = _server_app.delete(f"/api/comments/_test_.py/{cid}")
            assert r.status_code == 200
            comments = _server_app.get("/api/comments").json()
            assert "_test_.py" not in comments or len(comments["_test_.py"]) == 0
        finally:
            comments = _server_app.get("/api/comments").json()
            for c in comments.get("_test_.py", []):
                _server_app.delete(f"/api/comments/_test_.py/{c['id']}")

    def test_comment_resolve_toggle(self, _server_app):
        r = _server_app.post(
            "/api/comments",
            json={
                "file_path": "_test_resolve_.py",
                "line_index": 1,
                "comment": "needs fix",
            },
        )
        assert r.status_code == 200
        try:
            comments = _server_app.get("/api/comments").json()
            c = comments["_test_resolve_.py"][0]
            assert c.get("status") == "open"

            r = _server_app.post(f"/api/comments/_test_resolve_.py/{c['id']}/resolve")
            assert r.status_code == 200
            comments = _server_app.get("/api/comments").json()
            assert comments["_test_resolve_.py"][0]["status"] == "resolved"

            r = _server_app.post(f"/api/comments/_test_resolve_.py/{c['id']}/resolve")
            assert r.status_code == 200
            comments = _server_app.get("/api/comments").json()
            assert comments["_test_resolve_.py"][0]["status"] == "open"
        finally:
            comments = _server_app.get("/api/comments").json()
            for c in comments.get("_test_resolve_.py", []):
                _server_app.delete(f"/api/comments/_test_resolve_.py/{c['id']}")

    def test_review_toggle(self, _server_app):
        files = _server_app.get("/api/files?view=all").json()
        if not files:
            pytest.skip("No changed files")
        path = files[0]["path"]

        r = _server_app.post(f"/api/reviewed/{path}")
        assert r.status_code == 200
        assert r.json()["reviewed"] is True

        r = _server_app.post(f"/api/reviewed/{path}")
        assert r.status_code == 200
        assert r.json()["reviewed"] is False

    def test_static_files(self, _server_app):
        r = _server_app.get("/static/app.js")
        assert r.status_code == 200
        r = _server_app.get("/static/style.css")
        assert r.status_code == 200

    def test_comment_category_stored(self, _server_app):
        r = _server_app.post(
            "/api/comments",
            json={
                "file_path": "_test_cat_.py",
                "line_index": 1,
                "comment": "bug here",
                "category": "bug",
            },
        )
        assert r.status_code == 200
        try:
            c = _server_app.get("/api/comments").json()["_test_cat_.py"][0]
            assert c["category"] == "bug"
        finally:
            for c in _server_app.get("/api/comments").json().get("_test_cat_.py", []):
                _server_app.delete(f"/api/comments/_test_cat_.py/{c['id']}")

    def test_comment_category_defaults_empty(self, _server_app):
        r = _server_app.post(
            "/api/comments",
            json={
                "file_path": "_test_cat2_.py",
                "line_index": 1,
                "comment": "no cat",
            },
        )
        assert r.status_code == 200
        try:
            c = _server_app.get("/api/comments").json()["_test_cat2_.py"][0]
            assert c["category"] == ""
        finally:
            for c in _server_app.get("/api/comments").json().get("_test_cat2_.py", []):
                _server_app.delete(f"/api/comments/_test_cat2_.py/{c['id']}")

    def test_comment_suggestion_stored(self, _server_app):
        r = _server_app.post(
            "/api/comments",
            json={
                "file_path": "_test_sug_.py",
                "line_index": 1,
                "comment": "fix this",
                "suggestion": "x = 1\n",
            },
        )
        assert r.status_code == 200
        try:
            c = _server_app.get("/api/comments").json()["_test_sug_.py"][0]
            assert c["suggestion"] == "x = 1\n"
        finally:
            for c in _server_app.get("/api/comments").json().get("_test_sug_.py", []):
                _server_app.delete(f"/api/comments/_test_sug_.py/{c['id']}")

    def test_apply_suggestion_no_suggestion(self, _server_app):
        _server_app.post(
            "/api/comments",
            json={
                "file_path": "_test_apply1_.py",
                "line_index": 1,
                "comment": "no suggestion",
            },
        )
        try:
            cid = _server_app.get("/api/comments").json()["_test_apply1_.py"][0]["id"]
            r = _server_app.post(f"/api/comments/_test_apply1_.py/{cid}/apply")
            assert r.json()["ok"] is False
        finally:
            for c in _server_app.get("/api/comments").json().get("_test_apply1_.py", []):
                _server_app.delete(f"/api/comments/_test_apply1_.py/{c['id']}")

    def test_apply_suggestion_no_line_num(self, _server_app):
        _server_app.post(
            "/api/comments",
            json={
                "file_path": "_test_apply2_.py",
                "line_index": 1,
                "comment": "fix",
                "suggestion": "x = 1\n",
            },
        )
        try:
            cid = _server_app.get("/api/comments").json()["_test_apply2_.py"][0]["id"]
            r = _server_app.post(f"/api/comments/_test_apply2_.py/{cid}/apply")
            assert r.json()["ok"] is False
            assert "line number" in r.json()["error"].lower()
        finally:
            for c in _server_app.get("/api/comments").json().get("_test_apply2_.py", []):
                _server_app.delete(f"/api/comments/_test_apply2_.py/{c['id']}")

    def test_apply_suggestion_missing_comment(self, _server_app):
        r = _server_app.post("/api/comments/_test_apply3_.py/nonexistent-id/apply")
        assert r.json()["ok"] is False

    def test_blame_returns_list(self, _server_app):
        r = _server_app.get("/api/blame/diffui/__init__.py")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_blame_unknown_file(self, _server_app):
        r = _server_app.get("/api/blame/_nonexistent_path_.py")
        assert r.status_code == 200
        assert r.json() == []

    def test_preview_text_file(self, _server_app):
        r = _server_app.get("/api/preview/diffui/__init__.py")
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "text"
        assert "content" in data

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
        assert "**Files:**" in md

    def test_session_get_returns_dict(self, _server_app):
        r = _server_app.get("/api/session")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_session_put_and_get_roundtrip(self, _server_app):
        _server_app.put("/api/session", json={"test_key": "test_val"})
        r = _server_app.get("/api/session")
        assert r.json().get("test_key") == "test_val"

    def test_session_put_is_additive(self, _server_app):
        _server_app.put("/api/session", json={"key_a": 1})
        _server_app.put("/api/session", json={"key_b": 2})
        session = _server_app.get("/api/session").json()
        assert session.get("key_a") == 1
        assert session.get("key_b") == 2

    def test_websocket_connected_event(self, _server_app):
        import json

        with _server_app.websocket_connect("/api/ws") as ws:
            data = json.loads(ws.receive_text())
            assert data == {"events": ["connected"]}

    def test_websocket_ping_pong(self, _server_app):
        import json

        with _server_app.websocket_connect("/api/ws") as ws:
            ws.receive_text()  # consume connected
            ws.send_text(json.dumps({"type": "ping"}))
            data = json.loads(ws.receive_text())
            assert data == {"type": "pong"}


class TestExportJson:
    def test_output_structure(self):
        import json
        from io import StringIO
        from pathlib import Path
        from unittest.mock import patch

        from diffui.git_utils import resolve_repo_root, set_active_repo

        root = resolve_repo_root(Path(__file__).parent.parent)
        set_active_repo(root)

        buf = StringIO()
        with patch("builtins.print", side_effect=lambda *a, **kw: buf.write(a[0] if a else "")):
            from diffui.cli import export_json

            export_json()

        data = json.loads(buf.getvalue())
        assert "branch" in data
        assert "main_branch" in data
        assert "merge_base" in data
        assert "summary" in data
        assert "files" in data

        summary = data["summary"]
        assert "total_files" in summary
        assert "reviewed_files" in summary
        assert "total_comments" in summary
        assert "open_comments" in summary
        assert "resolved_comments" in summary
        assert summary["resolved_comments"] == summary["total_comments"] - summary["open_comments"]

        assert isinstance(data["files"], list)
        for f in data["files"]:
            assert "path" in f
            assert "reviewed" in f
            assert "comments" in f
            assert "open_comment_count" in f
