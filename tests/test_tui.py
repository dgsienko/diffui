from __future__ import annotations

import asyncio
import json
import time

import pytest
from textual.widgets import Footer

from diffui.git_utils import _comments_path, save_comments, save_reviewed, set_active_repo
from diffui.server.routes_diff import _order_files
from diffui.tui.app import DiffuiApp
from diffui.tui.client import ApiClient, LocalServer
from diffui.tui.diffview import DiffView
from diffui.tui.filelist import FileList
from diffui.tui.screens import ComposeScreen


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


def row_y(view, row) -> int:
    return row.top - view.scroll_offset.y


def line_rows(view, count: int = 3):
    return [r for r in view.rows if r.kind == "line"][:count]


def heading(app) -> str:
    return str(app.screen.query_one(".dialog-title").content)


def hints(app) -> str:
    return " · ".join(f"{k.key_display} {k.description}" for k in app.query_one(Footer).query("FooterKey"))


async def type_and_save(pilot, text: str) -> None:
    await pilot.press(*("space" if ch == " " else ch for ch in text))
    await pilot.press("ctrl+s")


def test_hovering_a_line_shows_the_add_marker(server):
    async def scenario(app, view, pilot):
        hunk, line = view.rows[0], line_rows(view, 1)[0]
        assert hunk.kind == "hunk"
        y = row_y(view, line)

        await pilot.hover(view, offset=(30, y))
        assert "[+]" in view.render_line(y).text
        assert "[+]" not in view.render_line(y + 1).text

        await pilot.hover(view, offset=(30, row_y(view, hunk)))
        assert "[+]" not in view.render_line(y).text
        assert "[+]" not in view.render_line(row_y(view, hunk)).text

        await pilot.hover(view, offset=(30, y))
        await pilot.hover(app.query_one(FileList))
        assert "[+]" not in view.render_line(y).text

        await pilot.hover(view, offset=(30, y))
        await pilot.press("c")
        assert isinstance(app.screen, ComposeScreen)
        assert "[+]" not in view.render_line(y).text

    run_tui(server, scenario)


def test_one_gutter_click_opens_the_composer_for_that_line(server):
    async def scenario(app, view, pilot):
        first, other = line_rows(view, 2)

        await pilot.click(view, offset=(40, row_y(view, other)))
        assert view.cursor == view.rows.index(other)
        assert len(app.screen_stack) == 1

        await pilot.click(view, offset=(2, row_y(view, first)))
        assert isinstance(app.screen, ComposeScreen)
        assert len(app.screen_stack) == 2
        assert str(first.line["new_num"]) in heading(app)

        await type_and_save(pilot, "from the gutter")
        await until(pilot, lambda: any(r.thread for r in view.rows))
        (comment,) = (await app.client.comments())["app.py"]
        assert comment["line_index"] == first.line["index"]
        assert comment["sel_end_index"] is None

    run_tui(server, scenario)


def test_dragging_across_the_gutter_comments_on_the_range(server):
    async def scenario(app, view, pilot):
        first, middle, last = line_rows(view)
        await pilot.mouse_down(view, offset=(2, row_y(view, first)))
        await pilot.hover(view, offset=(2, row_y(view, middle)))
        await pilot.hover(view, offset=(2, row_y(view, last)))
        assert len(view.selected_lines()) == 3
        assert not isinstance(app.screen, ComposeScreen)
        await pilot.mouse_up(view, offset=(2, row_y(view, last)))

        assert isinstance(app.screen, ComposeScreen)
        a, b = (str(r.line["new_num"] or r.line["old_num"]) for r in (first, last))
        assert f"lines {a}\N{EN DASH}{b}" in heading(app)

        await type_and_save(pilot, "this whole block")
        await until(pilot, lambda: any(r.thread for r in view.rows))
        (comment,) = (await app.client.comments())["app.py"]
        assert comment["line_index"] == first.line["index"]
        assert comment["sel_end_index"] == last.line["index"]
        assert (comment["sel_start"], comment["sel_end"]) == (0, len(last.line["text"]))
        assert comment["selected_text"] == "\n".join(r.line["text"] for r in (first, middle, last))
        assert view.anchor is None
        thread_y = row_y(view, next(r for r in view.rows if r.thread))
        assert f"lines {a}\N{EN DASH}{b}" in view.render_line(thread_y).text

    run_tui(server, scenario)


def test_keyboard_range_comment_with_a_footer_that_follows_the_cursor(server):
    async def scenario(app, view, pilot):
        first, _, last = line_rows(view)
        await pilot.pause()
        assert hints(app).startswith("c Comment · v Select range")

        await pilot.press("shift+down")
        await pilot.pause()
        assert hints(app).startswith("c Comment on 2 lines · esc Clear")
        await pilot.press("escape", "up")
        await pilot.pause()
        assert view.anchor is None
        assert hints(app).startswith("c Comment · v Select range")

        await pilot.press("v", "down", "down")
        await pilot.pause()
        assert hints(app).startswith("c Comment on 3 lines · esc Clear")
        await pilot.press("c")
        assert isinstance(app.screen, ComposeScreen)
        await type_and_save(pilot, "keyboard range")
        await until(pilot, lambda: any(r.thread for r in view.rows))

        (comment,) = (await app.client.comments())["app.py"]
        assert (comment["line_index"], comment["sel_end_index"]) == (first.line["index"], last.line["index"])

        await pilot.press("n")
        await pilot.pause()
        assert hints(app).startswith("c Reply · x Resolve")
        await pilot.press("x")
        await until(pilot, lambda: (view.current.thread or {}).get("status") == "resolved")

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
