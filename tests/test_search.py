from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from diffui.git_utils import set_active_repo
from diffui.server.app import create_app
from diffui.server.events import _apply_state_updates
from tests.conftest import _git


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
