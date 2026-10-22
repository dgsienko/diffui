from __future__ import annotations

import asyncio
import webbrowser
from pathlib import Path
from typing import ClassVar

import httpx
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.theme import Theme as TextualTheme
from textual.widgets import Footer, Static

from diffui.themes import ALL_THEMES
from diffui.tui.client import ApiClient, LocalServer
from diffui.tui.diffview import DiffView, span
from diffui.tui.filelist import FileList
from diffui.tui.screens import AgentScreen, ComposeScreen, HelpScreen

_CSS = """
#bar { dock: top; height: 1; padding: 0 1; background: $panel; color: $foreground; }
#body { height: 1fr; }
FileList { width: 30%; min-width: 28; max-width: 48; border: none; padding: 0; background: $surface; }
FileList > .option-list--option-highlighted { background: $primary 30%; text-style: none; }
FileList > .option-list--option-hover { background: $primary 15%; }
DiffView { width: 1fr; background: $background; }
ModalScreen { align: center middle; background: $background 60%; }
.dialog { width: 90%; max-width: 110; height: auto; max-height: 90%; padding: 1 2; background: $surface; border: round $primary; }
.dialog-title { text-style: bold; margin-bottom: 1; }
.hint { color: $text-muted; margin-top: 1; }
.dialog VerticalScroll { height: auto; max-height: 30; }
.buttons { height: auto; margin-top: 1; }
.buttons Button { margin-right: 2; }
#compose-text { height: 8; }
"""


_NEEDS = {"select_range": "line", "clear_selection": "range"}


def _number(line: dict) -> str:
    return str(line["new_num"] or line["old_num"])


class ContextFooter(Footer):
    """The footer, with the range hint naming how many lines `c` will comment on."""

    def compose(self) -> ComposeResult:
        count = len(self.app.query_one(DiffView).selected_lines())
        for widget in super().compose():
            if getattr(widget, "action", "") == "comment('range')":
                widget.description = f"Comment on {count} line{'s' * (count != 1)}"
            yield widget


class DiffuiApp(App[None]):
    TITLE = "diffui"
    ENABLE_COMMAND_PALETTE = False
    CSS = _CSS
    BINDINGS: ClassVar[list[BindingType]] = [
        # The first bindings hint what the cursor can do now; check_action shows the one that fits.
        Binding("c", "comment('range')", "Comment"),
        Binding("escape", "clear_selection", "Clear"),
        Binding("c", "comment('thread')", "Reply"),
        Binding("x", "resolve('thread')", "Resolve"),
        Binding("c", "comment('line')", "Comment"),
        Binding("v", "select_range", "Select range"),
        Binding("right,l", "file(1)", "Files", key_display="←/→"),
        Binding("left,h", "file(-1)", show=False),
        Binding("j", "hunk(1)", "Hunks", key_display="j/k"),
        Binding("k", "hunk(-1)", show=False),
        Binding("n", "thread(1)", show=False),
        Binding("p", "thread(-1)", show=False),
        Binding("right_square_bracket", "next_unreviewed", show=False),
        Binding("c", "comment('none')", "Comment"),
        Binding("x", "resolve('none')", "Resolve"),
        Binding("enter", "comment", show=False),
        Binding("x", "resolve", show=False),
        Binding("r", "review", "Reviewed"),
        Binding("s", "sort", "Risk sort"),
        Binding("A", "agent", "Agent", key_display="A"),
        Binding("o", "browser", "Browser"),
        Binding("b", "toggle_files", show=False),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client
        self.files: list[dict] = []
        self.comments: dict[str, list[dict]] = {}
        self.active: str | None = None
        self.order = "tree"
        self._branch: dict = {}
        self._diff_seq = 0

    def compose(self) -> ComposeResult:
        yield Static(id="bar")
        with Horizontal(id="body"):
            yield FileList()
            yield DiffView()
        yield ContextFooter()

    async def on_unmount(self) -> None:
        await self.client.aclose()

    def on_mount(self) -> None:
        self.query_one(DiffView).focus()
        self.run_worker(self._start(), exit_on_error=False)

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if isinstance(self.screen, ModalScreen):
            return action == "quit"
        views = self.query(DiffView)
        context = views.first().context if views else "none"
        if action in ("comment", "resolve") and parameters:
            return parameters[0] == context
        if action in _NEEDS:
            return _NEEDS[action] == context
        return True

    def push_screen(self, *args, **kwargs):
        self.query_one(DiffView).clear_hover()
        return super().push_screen(*args, **kwargs)

    async def _start(self) -> None:
        await self._safely(self._apply_theme())
        self._branch = await self.client.branch()
        self.comments = await self.client.comments()
        await self._safely(self._refresh_files())
        await self._safely(self._listen())

    async def _safely(self, work) -> None:
        try:
            await work
        except httpx.HTTPError as e:
            self.notify(f"Request failed: {e}", severity="error", markup=False)

    async def _apply_theme(self) -> None:
        name = (await self.client.settings())["theme"]
        theme = next(t for t in ALL_THEMES if t.name == name)
        self.register_theme(
            TextualTheme(
                name="diffui",
                primary=theme.accent,
                secondary=theme.hunk_fg,
                warning=theme.warn_fg,
                error=theme.delete_fg,
                foreground=theme.fg,
                background=theme.bg,
                surface=theme.bg_dark,
                panel=theme.comment_header_bg,
            )
        )
        self.theme = "diffui"
        view, files = self.query_one(DiffView), self.query_one(FileList)
        view.palette = files.palette = theme
        view.refresh()

    async def _listen(self) -> None:
        connected = 0
        async for events in self.client.events():
            if "connected" in events:
                connected += 1
                if connected > 1:
                    await self._refresh_all()
                continue
            if {"files_changed", "git_changed"} & set(events):
                await self._refresh_all()
            elif "comments_changed" in events:
                await self._refresh_comments()

    async def _refresh_all(self) -> None:
        self.comments = await self.client.comments()
        if not await self._refresh_files() and self.active:
            await self._load_diff(self.active)

    async def _refresh_comments(self) -> None:
        self.comments = await self.client.comments()
        await self._refresh_files()
        self.query_one(DiffView).set_comments(self.comments.get(self.active or "", []))

    async def _refresh_files(self) -> bool:
        """Reloads the list. Returns True when the active file changed and its diff was loaded."""
        self.files = await self.client.files(self.order)
        paths = [f["path"] for f in self.files]
        opening = self.active not in paths
        if opening:
            self.active = await self.client.next_unreviewed(self.order) or (paths[0] if paths else None)
        self.query_one(FileList).set_files(self.files, self.active, flat=self.order == "risk")
        self._update_bar()
        if opening and self.active:
            await self._load_diff(self.active)
        elif not self.active:
            self.query_one(DiffView).set_diff("", {"file_note": "No changes to review.", "hunks": []}, [])
        return opening

    def _update_bar(self) -> None:
        reviewed = sum(1 for f in self.files if f["reviewed"])
        open_comments = sum(f["open_comment_count"] for f in self.files)
        bar = Text(f"{self._branch.get('repo_name', '')}  {self._branch.get('name', '')}", style="bold")
        bar.append(f"   {reviewed}/{len(self.files)} reviewed   {open_comments} open comments", style="dim")
        if self.order == "risk":
            bar.append("   sorted by risk", style="dim")
        self.query_one("#bar", Static).update(bar)

    async def _load_diff(self, path: str) -> None:
        self._diff_seq += 1
        seq = self._diff_seq
        data = await self.client.diff(path)
        if seq == self._diff_seq and path == self.active:
            self.query_one(DiffView).set_diff(path, data, self.comments.get(path, []))

    async def _open_file(self, path: str) -> None:
        self.active = path
        self.query_one(FileList).set_active(path)
        await self._safely(self._load_diff(path))

    def on_file_list_picked(self, event: FileList.Picked) -> None:
        self.run_worker(self._open_file(event.path))
        self.query_one(DiffView).focus()

    async def action_file(self, step: int) -> None:
        paths = [f["path"] for f in self.files]
        if paths:
            index = paths.index(self.active) if self.active in paths else -step
            await self._open_file(paths[(index + step) % len(paths)])

    async def action_next_unreviewed(self) -> None:
        path = await self.client.next_unreviewed(self.order)
        if path:
            await self._open_file(path)
        else:
            self.notify("All files reviewed")

    def action_hunk(self, direction: int) -> None:
        if not self.query_one(DiffView).jump_hunk(direction):
            self.notify("No more hunks", timeout=2)

    def action_thread(self, direction: int) -> None:
        if not self.query_one(DiffView).jump_thread(direction):
            self.notify("No comments in this file", timeout=2)

    async def action_review(self) -> None:
        if not self.active:
            return
        reviewed = await self.client.toggle_reviewed(self.active)
        await self._refresh_files()
        if reviewed:
            await self.action_next_unreviewed()

    async def action_sort(self) -> None:
        self.order = "tree" if self.order == "risk" else "risk"
        await self._refresh_files()
        self.notify("Sorted by risk" if self.order == "risk" else "Default file order", timeout=2)

    def action_toggle_files(self) -> None:
        files = self.query_one(FileList)
        files.display = not files.display

    def action_comment(self, _context: str = "") -> None:
        view = self.query_one(DiffView)
        row = view.current
        if row is None or not self.active:
            return
        path = self.active
        lines = view.selected_lines() or ([row.line] if row.kind == "line" else [])
        if lines:
            first, last = lines[0], lines[-1]
            where = (
                f"{path}:{_number(first)}" if len(lines) == 1 else f"{path} lines {span(_number(first), _number(last))}"
            )
            self.push_screen(
                ComposeScreen(f"Comment on {where}", first["text"][1:].strip()[:120]),
                self._submit(lambda text: self.client.add_comment(path, first, text, lines)),
            )
        elif row.kind == "thread" and row.thread.get("id"):
            thread = row.thread
            self.push_screen(
                ComposeScreen(f"Reply to {thread.get('author') or 'user'}", thread.get("comment", "")[:120]),
                self._submit(lambda text: self.client.reply(path, thread["id"], text)),
            )
        else:
            self.notify("Move to a diff line to comment", timeout=2)

    def action_select_range(self) -> None:
        self.query_one(DiffView).start_selection()

    def action_clear_selection(self) -> None:
        self.query_one(DiffView).clear_selection()

    def on_diff_view_activated(self, _event: DiffView.Activated) -> None:
        self.action_comment()

    def _submit(self, make_request):
        async def callback(text: str | None) -> None:
            if text:
                await self._safely(self._write(make_request(text)))
                self.query_one(DiffView).clear_selection()

        return callback

    async def _write(self, request) -> None:
        await request
        await self._refresh_comments()

    async def action_resolve(self, _context: str = "") -> None:
        row = self.query_one(DiffView).current
        if row is None or row.kind != "thread" or not self.active:
            self.notify("Move to a comment thread to resolve it", timeout=2)
            return
        await self._safely(self._write(self.client.toggle_resolved(self.active, row.thread["id"])))

    async def action_agent(self) -> None:
        data = await self.client.agent_prompt()
        if not data["ok"]:
            self.notify(data["error"], severity="warning", markup=False)
            return
        self.push_screen(AgentScreen(data), self._paste)

    async def _paste(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        result = await self.client.agent_paste()
        if result["ok"]:
            self.notify(f"Pasted into {result['agent']}. Press Enter there to send.", markup=False)
        else:
            self.notify(result["error"], severity="error", markup=False)

    async def action_browser(self) -> None:
        if not self.active:
            return
        await self.client.set_active_file(self.active)
        opened = await asyncio.to_thread(webbrowser.open, self.client.base_url)
        self.notify(f"Opened {self.client.base_url}" if opened else f"Open {self.client.base_url} in a browser")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())


def run(repos: list[Path], active_index: int = 0) -> None:
    server = LocalServer(repos, active_index)
    server.start()
    try:
        DiffuiApp(ApiClient(server.url)).run()
    finally:
        server.stop()
