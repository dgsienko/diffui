from __future__ import annotations

import pytest

from tests.conftest import post_comment


class TestComments:
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
