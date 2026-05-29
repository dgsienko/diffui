from __future__ import annotations

from pathlib import Path

import pytest

from diffui.server.theme_css import generate_css_vars
from diffui.themes.definitions import CATPPUCCIN_MOCHA, GITHUB_DARK


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


@pytest.fixture
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
        assert len(data) == 10
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

        r = _server_app.put("/api/settings", json={"editor": "nvim"})
        assert r.status_code == 200

        r = _server_app.get("/api/settings")
        assert r.json()["editor"] == "nvim"

        _server_app.put("/api/settings", json={"editor": original["editor"]})

    def test_comments(self, _server_app):
        r = _server_app.get("/api/comments")
        assert r.status_code == 200

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

        comments = _server_app.get("/api/comments").json()
        assert "_test_.py" in comments
        comment = comments["_test_.py"][0]
        assert comment["comment"] == "test comment"
        assert "id" in comment
        cid = comment["id"]

        r = _server_app.put(f"/api/comments/_test_.py/{cid}", json={"comment": "edited"})
        assert r.status_code == 200
        assert _server_app.get("/api/comments").json()["_test_.py"][0]["comment"] == "edited"

        r = _server_app.post(f"/api/comments/_test_.py/{cid}/reply", json={"text": "reply"})
        assert r.status_code == 200
        assert len(_server_app.get("/api/comments").json()["_test_.py"][0]["replies"]) == 1

        r = _server_app.delete(f"/api/comments/_test_.py/{cid}")
        assert r.status_code == 200
        comments = _server_app.get("/api/comments").json()
        assert "_test_.py" not in comments

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
