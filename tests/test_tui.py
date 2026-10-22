from __future__ import annotations

import asyncio
import json
import time

import pytest

from diffui.git_utils import _comments_path, save_comments, save_reviewed, set_active_repo
from diffui.server.routes_diff import _order_files
from diffui.tui.app import DiffuiApp
from diffui.tui.client import ApiClient, LocalServer
from diffui.tui.diffview import DiffView


@pytest.fixture
def server(temp_repo):
    set_active_repo(temp_repo)
    save_comments({})
    save_reviewed({})
    srv = LocalServer([temp_repo])
    srv.start()
    yield srv
    srv.stop()
    save_comments({})
    save_reviewed({})


async def until(pilot, condition, timeout: float = 10):
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out waiting for the TUI"
        await pilot.pause(0.05)


def run_tui(server, scenario) -> None:
    async def main():
        app = DiffuiApp(ApiClient(server.url))
        async with app.run_test(size=(120, 50)) as pilot:
            view = app.query_one(DiffView)
            await until(pilot, lambda: app.active and view.path == app.active)
            await scenario(app, view, pilot)

    asyncio.run(main())


async def open_next(app, view, pilot, key: str) -> None:
    before = app.active
    await pilot.press(key)
    await until(pilot, lambda: app.active != before and view.path == app.active)


def test_file_keys_follow_tree_order(server):
    async def scenario(app, view, pilot):
        order = [f["path"] for f in app.files]
        assert order == ["app.py", "extra.py", "untracked.txt"]
        assert app.active == order[0]

        first_line = view.cursor
        await pilot.press("j")
        assert view.cursor > first_line
        await pilot.press("k")
        assert view.cursor == first_line

        visited = []
        for _ in order:
            await open_next(app, view, pilot, "l")
            visited.append(app.active)
        assert visited == [*order[1:], order[0]]
        await open_next(app, view, pilot, "h")
        assert app.active == order[-1]

    run_tui(server, scenario)


def test_comment_from_tui_is_stored_at_the_line(server):
    async def scenario(app, view, pilot):
        target = next(r.line for r in view.rows if r.line and r.line["text"] == "+line five")
        while view.current.line is None or view.current.line["index"] != target["index"]:
            await pilot.press("down")
        await pilot.press("c")
        await pilot.press(*("space" if ch == " " else ch for ch in "needs a test"))
        await pilot.press("ctrl+s")
        await until(pilot, lambda: any(r.thread for r in view.rows))

        (comment,) = (await app.client.comments())["app.py"]
        assert comment["comment"] == "needs a test"
        assert comment["line_index"] == target["index"]
        assert comment["file_line_num"] == 5
        assert comment["line_text"] == "+line five"

    run_tui(server, scenario)


def test_mark_reviewed_advances_to_next_unreviewed(server):
    async def scenario(app, view, pilot):
        await app.client.toggle_reviewed("extra.py")
        await pilot.press("r")
        await until(pilot, lambda: app.active == "untracked.txt" and view.path == app.active)
        assert [f["path"] for f in app.files if f["reviewed"]] == ["app.py", "extra.py"]

    run_tui(server, scenario)


def test_external_comment_write_refreshes_the_view(server):
    async def scenario(app, view, pilot):
        await app.client.add_comment("app.py", next(r.line for r in view.rows if r.line), "please rename")
        await until(pilot, lambda: any(r.thread for r in view.rows) and app.files[0]["open_comment_count"] == 1)

        path = _comments_path()
        stored = json.loads(path.read_text())
        stored["app.py"][0].update(
            status="resolved", replies=[{"text": "Renamed", "author": "claude", "author_type": "agent"}]
        )
        path.write_text(json.dumps(stored))

        await until(pilot, lambda: any(r.thread and r.thread.get("replies") for r in view.rows))
        thread = next(r.thread for r in view.rows if r.thread)
        assert thread["status"] == "resolved"
        assert app.files[0]["open_comment_count"] == 0

    run_tui(server, scenario)


def _entry(path: str, risk: int = 0) -> dict:
    return {"path": path, "dir": path.rpartition("/")[0] or ".", "risk_score": risk}


def test_order_files_mirrors_the_web_tree():
    files = [_entry("a/z.py"), _entry("b/y.py", 5), _entry("top.py", 3), _entry("a/b/x.py")]
    assert [f["path"] for f in _order_files(files, "tree")] == ["top.py", "a/z.py", "a/b/x.py", "b/y.py"]
    assert [f["path"] for f in _order_files(files, "risk")] == ["b/y.py", "top.py", "a/z.py", "a/b/x.py"]


def test_escape_sequences_in_the_diff_never_reach_the_terminal(server, temp_repo):
    app_py = temp_repo / "app.py"
    original = app_py.read_text()
    app_py.write_text(original + "title \x1b]0;pwned\x07 end\n")

    async def fetch():
        client = ApiClient(server.url)
        try:
            return await client.diff("app.py")
        finally:
            await client.aclose()

    try:
        data = asyncio.run(fetch())
    finally:
        app_py.write_text(original)
    texts = [line["text"] for hunk in data["hunks"] for line in hunk["lines"]]
    assert any("pwned" in t for t in texts)
    assert not any("\x1b" in t or "\x07" in t for t in texts)
