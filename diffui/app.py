from __future__ import annotations

import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.timer import Timer
from textual.widgets import (
    Button,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from diffui.diff import resolve_line_num
from diffui.git_utils import (
    Commit,
    _comments_path,
    clear_branch_cache,
    current_branch,
    get_branch_commits,
    get_changed_files,
    get_commit_diff,
    get_file_mtime,
    get_full_diff,
    get_git_user_name,
    get_main_branch,
    get_merge_base,
    get_repo_root,
    get_working_changed_files,
    get_working_diff,
    load_comments,
    load_reviewed,
    load_settings,
    save_comments,
    save_reviewed,
    save_settings,
    short_name,
)
from diffui.themes import ALL_THEMES, CATPPUCCIN_MOCHA, Theme, generate_css, set_current_theme
from diffui.widgets import (
    VIEW_MODE_DIFF,
    VIEW_MODE_FILE,
    DiffLine,
    DiffViewer,
    FileTree,
    FullFileViewer,
    InlineCommentBox,
    InlineCommentDisplay,
    LazyPlaceholder,
    SearchBar,
    SettingsPanel,
)

_SENTINEL = object()
_CSS_FILE = Path(tempfile.gettempdir()) / "diffui_theme.tcss"
_diff_cache: dict[tuple[str, str, float], str] = {}


def _write_css(theme: Theme) -> None:
    _CSS_FILE.write_text(generate_css(theme))


class DiffUI(App):

    CSS_PATH = str(_CSS_FILE)

    BINDINGS = [
        Binding("r", "toggle_review", "Toggle reviewed"),
        Binding("q", "quit", "Quit"),
        Binding("a", "show_all", "Show all"),
        Binding("left", "prev_tab", show=False),
        Binding("right", "next_tab", show=False),
        Binding("ctrl+f", "search", show=False),
        Binding("n", "next_comment", show=False),
        Binding("p", "prev_comment", show=False),
        Binding("j", "next_hunk", show=False),
        Binding("k", "prev_hunk", show=False),
        Binding("y", "copy_path", show=False),
        Binding("b", "toggle_sidebar", show=False),
        Binding("escape", "close_panel", show=False),
    ]

    TITLE = "diffui"

    def __init__(self) -> None:
        saved = load_settings()
        theme_name = saved.get("theme", CATPPUCCIN_MOCHA.name)
        theme_index = next((i for i, t in enumerate(ALL_THEMES) if t.name == theme_name), 0)

        set_current_theme(ALL_THEMES[theme_index])
        _write_css(ALL_THEMES[theme_index])

        super().__init__()
        self._repo_root = get_repo_root()
        self._theme_index = theme_index
        self._editor = saved.get("editor", "code")
        self._view_mode = saved.get("view_mode", VIEW_MODE_DIFF)
        self._user_name = saved.get("user_name", get_git_user_name())
        self._search_term = ""
        self._search_debounce: Timer | None = None
        self._tab_generation = 0
        self._branch_name = current_branch()
        self.main_branch = get_main_branch()
        self.merge_base = get_merge_base(self.main_branch)
        self.commits = get_branch_commits(self.merge_base)
        self.all_files = get_changed_files(self.merge_base)
        self.reviewed = load_reviewed()
        self.comments = load_comments()
        self.current_view = "all"
        self.show_reviewed = True
        self._active_files: list[str] = []
        self._active_tab_ids: list[str] = []
        self._comment_nav_index: int = -1
        self._scroll_positions: dict[str, int] = {}
        self._last_file_mtimes = self._snapshot_file_mtimes()
        self._last_comments_mtime = self._get_comments_mtime()
        self._git_head_mtime = self._stat_mtime(self._repo_root / ".git" / "HEAD")
        self._git_index_mtime = self._stat_mtime(self._repo_root / ".git" / "index")
        self._git_ref_path = self._repo_root / ".git" / "refs" / "heads" / self._branch_name
        self._git_ref_mtime = self._stat_mtime(self._git_ref_path)

    # --- Helpers ---

    @staticmethod
    def _stat_mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except FileNotFoundError:
            return 0.0

    async def _remove_all(self, selector: str) -> None:
        for w in self.query(selector):
            await w.remove()

    def _build_view_options(self) -> list[tuple[str, str]]:
        options: list[tuple[str, str]] = [("- All changes", "all")]
        if self._git_index_mtime > 0:
            options.append(("- Working changes (uncommitted)", "working"))
        for c in reversed(self.commits):
            options.append((f"- {c.message[:38]}", c.sha))
        return options

    def _get_visible_files(self) -> list[str]:
        if self.current_view == "all":
            working = get_working_changed_files()
            files = sorted(set(self.all_files) | set(working))
        elif self.current_view == "working":
            files = get_working_changed_files()
        else:
            commit = next((c for c in self.commits if c.sha == self.current_view), None)
            files = commit.files if commit else []
        if not self.show_reviewed:
            files = [f for f in files if not self._is_reviewed(f)]
        return files

    def _is_reviewed(self, path: str) -> bool:
        if path not in self.reviewed:
            return False
        return self.reviewed[path] == self._last_file_mtimes.get(path, get_file_mtime(path))

    def _get_diff(self, path: str) -> str:
        mtime = self._last_file_mtimes.get(path, get_file_mtime(path))
        cache_key = (path, self.current_view, mtime)
        if cache_key in _diff_cache:
            return _diff_cache[cache_key]
        if self.current_view == "all":
            result = get_full_diff(self.merge_base, path)
        elif self.current_view == "working":
            result = get_working_diff(path)
        else:
            result = get_commit_diff(self.current_view, path)
        _diff_cache[cache_key] = result
        return result

    def _build_viewer(self, path: str) -> DiffViewer | FullFileViewer:
        if self._view_mode == VIEW_MODE_FILE:
            viewer = FullFileViewer(path, self.comments, search_term=self._search_term)
            viewer.diff_text = self._get_diff(path)
            return viewer
        return DiffViewer(path, self._get_diff(path), self.comments, search_term=self._search_term)

    def _tab_label(self, path: str) -> str:
        name = short_name(path)
        prefix = "✓ " if self._is_reviewed(path) else ""
        return f"{prefix}{name}"

    # --- Compose ---

    def compose(self) -> ComposeResult:
        with Horizontal(id="top-bar"):
            yield Select(
                self._build_view_options(),
                value="all",
                id="view-select",
                allow_blank=False,
            )
            yield Select[str](
                [],
                id="comments-select",
                prompt="No comments",
                allow_blank=True,
                disabled=True,
            )
            yield Button("Hide reviewed", id="toggle-reviewed", variant="default")
            yield Static("", id="file-counter")
            yield Static("", id="top-bar-spacer")
            yield Static("", id="branch-label")
            yield Button("☰", id="settings-btn", variant="default")
        yield TabbedContent(id="file-tabs")
        yield Static(
            "[bold #6c7086]ctrl+click[/] open in editor    "
            "[bold #6c7086]right-click[/] add comment    "
            "[bold #6c7086]n/p[/] next/prev comment    "
            "[bold #6c7086]j/k[/] next/prev hunk    "
            "[bold #6c7086]r[/] toggle reviewed    "
            "[bold #6c7086]a[/] show/hide reviewed    "
            "[bold #6c7086]←/→[/] prev/next file    "
            "[bold #6c7086]y[/] copy path    "
            "[bold #6c7086]b[/] file tree    "
            "[bold #6c7086]ctrl+f[/] search    "
            "[bold #6c7086]q[/] quit",
            markup=True,
            id="legend",
        )

    async def on_mount(self) -> None:
        try:
            self.query_one("#branch-label", Static).update(
                f"[dim]{self._branch_name}[/dim]"
            )
        except NoMatches:
            pass
        await self._refresh_tabs()
        self.set_interval(3, self._start_poll)

    # --- Polling (off main thread) ---

    def _get_comments_mtime(self) -> float:
        return self._stat_mtime(_comments_path())

    def _snapshot_file_mtimes(self) -> dict[str, float]:
        return {f: get_file_mtime(f) for f in self.all_files}

    def _start_poll(self) -> None:
        self._poll_worker()

    @work(thread=True, exclusive=True, group="poll")
    def _poll_worker(self) -> None:
        head_mtime = self._stat_mtime(self._repo_root / ".git" / "HEAD")
        index_mtime = self._stat_mtime(self._repo_root / ".git" / "index")
        ref_mtime = self._stat_mtime(self._git_ref_path)
        comments_mtime = self._get_comments_mtime()
        current_files = self.all_files
        file_mtimes = {f: get_file_mtime(f) for f in current_files}

        git_changed = (
            head_mtime != self._git_head_mtime
            or index_mtime != self._git_index_mtime
            or ref_mtime != self._git_ref_mtime
        )
        files_changed = file_mtimes != self._last_file_mtimes
        comments_changed = comments_mtime != self._last_comments_mtime

        if git_changed:
            clear_branch_cache()
            new_commits = get_branch_commits(self.merge_base)
            new_all_files = get_changed_files(self.merge_base)
            new_file_mtimes = {f: get_file_mtime(f) for f in new_all_files}
            if new_file_mtimes != file_mtimes:
                file_mtimes = new_file_mtimes
                files_changed = True
        else:
            new_commits = self.commits
            new_all_files = self.all_files

        if not (git_changed or files_changed or comments_changed):
            return

        new_comments = load_comments() if comments_changed else self.comments

        self.call_from_thread(
            self._apply_poll_result,
            git_changed, files_changed, comments_changed,
            head_mtime, index_mtime, ref_mtime, comments_mtime,
            file_mtimes, new_commits, new_all_files, new_comments,
        )

    async def _apply_poll_result(
        self,
        git_changed: bool,
        files_changed: bool,
        comments_changed: bool,
        head_mtime: float,
        index_mtime: float,
        ref_mtime: float,
        comments_mtime: float,
        file_mtimes: dict[str, float],
        new_commits: list[Commit],
        new_all_files: list[str],
        new_comments: dict[str, list[dict]],
    ) -> None:
        if git_changed:
            self._git_head_mtime = head_mtime
            self._git_index_mtime = index_mtime
            self._git_ref_mtime = ref_mtime
            _diff_cache.clear()
            self.commits = new_commits
            self.all_files = new_all_files

        if files_changed:
            self._last_file_mtimes = file_mtimes
            _diff_cache.clear()

        if comments_changed:
            self._last_comments_mtime = comments_mtime
            self.comments = new_comments

        if git_changed or files_changed:
            try:
                self.query_one("#view-select", Select).set_options(self._build_view_options())
            except NoMatches:
                pass
            self.reviewed = load_reviewed()
            await self._incremental_refresh()
            self.notify("Changes detected — refreshed", timeout=2)

        if comments_changed:
            self._refresh_comments_select()
            await self._refresh_comments_in_viewer()

    # --- Tab management ---

    @on(Select.Changed, "#view-select")
    async def view_changed(self, event: Select.Changed) -> None:
        if event.value is not None:
            self.current_view = str(event.value)
            await self._refresh_tabs()

    def _get_current_file(self) -> str | None:
        viewer = self._get_active_viewer()
        return viewer.file_path if viewer else None

    async def _incremental_refresh(self) -> None:
        new_files = self._get_visible_files()

        if new_files == self._active_files:
            self._update_tab_labels(new_files)
            self._update_counters()
            await self._invalidate_active_viewer()
            return

        await self._refresh_tabs()

    def _update_tab_labels(self, files: list[str]) -> None:
        tabs = self.query_one("#file-tabs", TabbedContent)
        for i, path in enumerate(files):
            if i >= len(self._active_tab_ids):
                break
            label = self._tab_label(path)
            try:
                tab = tabs.get_tab(self._active_tab_ids[i])
                if tab.label_text != label:
                    tab.label = label
            except Exception:
                pass

    def _update_counters(self) -> None:
        total = len(self.all_files) if self.current_view == "all" else len(self._active_files)
        reviewed = sum(1 for f in self.all_files if self._is_reviewed(f))
        self._update_file_counter(total, reviewed)

    async def _invalidate_active_viewer(self) -> None:
        viewer = self._get_active_viewer()
        if not viewer:
            return
        new_diff = self._get_diff(viewer.file_path)
        if new_diff != viewer.diff_text:
            viewer.diff_text = new_diff
            viewer.diff_lines = new_diff.splitlines()
            viewer._comments = self.comments
            viewer._search_term = self._search_term
            if isinstance(viewer, FullFileViewer):
                viewer._cached_content = None
            await viewer.recompose()

    async def _refresh_comments_in_viewer(self) -> None:
        viewer = self._get_active_viewer()
        if not viewer:
            return
        viewer._comments = self.comments
        if isinstance(viewer, FullFileViewer):
            viewer._cached_content = None
        await viewer.recompose()

    async def _refresh_tabs(self, restore_file: str | None | object = _SENTINEL) -> None:
        if restore_file is _SENTINEL:
            restore_file = self._get_current_file()

        self._tab_generation += 1
        gen = self._tab_generation
        tabs = self.query_one("#file-tabs", TabbedContent)
        tabs.display = False
        await tabs.clear_panes()
        files = self._get_visible_files()
        self._active_files = files

        total = len(self.all_files) if self.current_view == "all" else len(files)
        reviewed = sum(1 for f in self.all_files if self._is_reviewed(f))
        self._update_file_counter(total, reviewed)

        if not files:
            await tabs.add_pane(
                TabPane("No files", Static("All files reviewed.", classes="empty-state"), id=f"tab-empty-{gen}")
            )
            self._refresh_comments_select()
            tabs.display = True
            return

        restore_tab_id = None
        if restore_file and restore_file in files:
            active_path = restore_file
        else:
            active_path = next((f for f in files if not self._is_reviewed(f)), files[0])
        tab_ids = []
        for i, path in enumerate(files):
            label = self._tab_label(path)
            tab_id = f"tab-{gen}-{i}"
            tab_ids.append(tab_id)
            if path == active_path:
                content = self._build_viewer(path)
                restore_tab_id = tab_id
            else:
                content = LazyPlaceholder(path, short_name(path))
            pane = TabPane(label, content, id=tab_id)
            await tabs.add_pane(pane)
        self._active_tab_ids = tab_ids

        if restore_tab_id:
            tabs.active = restore_tab_id

        tabs.display = True
        self._refresh_comments_select()
        self._prewarm_adjacent_tab()

    def _prewarm_adjacent_tab(self) -> None:
        if not self._active_files or not self._active_tab_ids:
            return
        tabs = self.query_one("#file-tabs", TabbedContent)
        try:
            idx = self._active_tab_ids.index(tabs.active)
        except ValueError:
            return
        next_idx = (idx + 1) % len(self._active_files)
        if next_idx != idx:
            self._get_diff(self._active_files[next_idx])

    def _update_file_counter(self, total: int, reviewed: int) -> None:
        try:
            self.query_one("#file-counter", Static).update(f"[bold]{reviewed}/{total}[/bold] reviewed")
        except NoMatches:
            pass

    def _update_review_button(self) -> None:
        viewer = self._get_active_viewer()
        is_reviewed = viewer and self._is_reviewed(viewer.file_path)
        label = "Mark unreviewed" if is_reviewed else "Mark reviewed"
        mark_class = "review-btn-unmark" if is_reviewed else "review-btn-mark"
        unmark_class = "review-btn-mark" if is_reviewed else "review-btn-unmark"
        for widget in self.query("#inline-review-btn"):
            if isinstance(widget, Button):
                widget.label = label
                widget.add_class(mark_class)
                widget.remove_class(unmark_class)

    def _update_toggle_button(self) -> None:
        try:
            self.query_one("#toggle-reviewed", Button).label = "Hide reviewed" if self.show_reviewed else "Show all"
        except NoMatches:
            pass

    def _save_scroll_position(self) -> None:
        viewer = self._get_active_viewer()
        if viewer:
            self._scroll_positions[viewer.file_path] = viewer.scroll_offset.y

    def _restore_scroll_position(self, viewer: DiffViewer | FullFileViewer) -> None:
        saved_y = self._scroll_positions.get(viewer.file_path, 0)
        if saved_y > 0:
            viewer.scroll_to(y=saved_y, animate=False)

    @on(TabbedContent.TabActivated)
    async def tab_activated(self, event: TabbedContent.TabActivated) -> None:
        self._save_scroll_position()
        pane = event.pane
        try:
            placeholder = pane.query_one(LazyPlaceholder)
            file_path = placeholder.file_path
            viewer = self._build_viewer(file_path)
            await pane.mount(viewer, before=placeholder)
            await placeholder.remove()
        except NoMatches:
            pass
        viewer = self._get_active_viewer()
        if viewer:
            self._restore_scroll_position(viewer)
        self._refresh_comments_select()
        self._update_review_button()
        self._update_file_tree_highlight()
        self._prewarm_adjacent_tab()

    def _get_active_viewer(self) -> DiffViewer | FullFileViewer | None:
        try:
            tabs = self.query_one("#file-tabs", TabbedContent)
            if not tabs.active:
                return None
            pane = tabs.query_one(f"#{tabs.active}", TabPane)
            try:
                return pane.query_one(DiffViewer)
            except NoMatches:
                return pane.query_one(FullFileViewer)
        except NoMatches:
            return None

    # --- Buttons ---

    @on(Button.Pressed, "#review-btn")
    @on(Button.Pressed, "#inline-review-btn")
    async def review_button_pressed(self, event: Button.Pressed) -> None:
        self.set_focus(None)
        await self.action_toggle_review()

    @on(Button.Pressed, "#settings-btn")
    async def toggle_settings(self, event: Button.Pressed) -> None:
        if self.query("SettingsPanel"):
            await self._remove_all("SettingsPanel")
        else:
            await self.mount(SettingsPanel(self._theme_index, self._editor, self._view_mode, self._user_name))
        self.set_focus(None)

    @on(SettingsPanel.ThemeChanged)
    async def settings_theme_changed(self, event: SettingsPanel.ThemeChanged) -> None:
        self._theme_index = event.theme_index
        theme = ALL_THEMES[self._theme_index]
        set_current_theme(theme)
        _write_css(theme)
        await self._remove_all("SettingsPanel")
        self._save_settings()
        stylesheet = self.stylesheet.copy()
        stylesheet.read_all(self.css_path)
        stylesheet.parse()
        self.stylesheet = stylesheet
        self.stylesheet.update(self)
        for screen in self.screen_stack:
            self.stylesheet.update(screen)
        await self._refresh_tabs()
        self.set_focus(None)

    @on(SettingsPanel.EditorChanged)
    def settings_editor_changed(self, event: SettingsPanel.EditorChanged) -> None:
        self._editor = event.editor
        self._save_settings()

    @on(SettingsPanel.ViewModeChanged)
    async def settings_view_mode_changed(self, event: SettingsPanel.ViewModeChanged) -> None:
        self._view_mode = event.mode
        self._save_settings()
        _diff_cache.clear()
        await self._refresh_tabs()

    @on(SettingsPanel.UserNameChanged)
    def settings_user_name_changed(self, event: SettingsPanel.UserNameChanged) -> None:
        self._user_name = event.name
        self._save_settings()

    @on(SettingsPanel.Closed)
    async def settings_closed(self, event: SettingsPanel.Closed) -> None:
        await self._remove_all("SettingsPanel")
        self.set_focus(None)

    @on(Button.Pressed, "#toggle-reviewed")
    async def toggle_reviewed(self) -> None:
        self.show_reviewed = not self.show_reviewed
        self._update_toggle_button()
        self.set_focus(None)
        await self._refresh_tabs()

    # --- Keyboard nav ---

    def _navigate_tab(self, delta: int) -> None:
        if not self._active_tab_ids:
            return
        tabs = self.query_one("#file-tabs", TabbedContent)
        try:
            idx = self._active_tab_ids.index(tabs.active)
            tabs.active = self._active_tab_ids[(idx + delta) % len(self._active_tab_ids)]
        except (ValueError, IndexError):
            pass

    def action_prev_tab(self) -> None:
        self._navigate_tab(-1)

    def action_next_tab(self) -> None:
        self._navigate_tab(1)

    # --- File tree sidebar ---

    async def action_toggle_sidebar(self) -> None:
        if self.query("FileTree"):
            await self._remove_all("FileTree")
        else:
            reviewed_set = {f for f in self._active_files if self._is_reviewed(f)}
            tree = FileTree(self._active_files, reviewed=reviewed_set, active_file=self._get_current_file(), id="file-tree")
            tabs = self.query_one("#file-tabs", TabbedContent)
            await self.mount(tree, before=tabs)

    @on(FileTree.FileSelected)
    async def file_tree_selected(self, event: FileTree.FileSelected) -> None:
        await self._activate_file_tab(event.file_path, 0)
        self._update_file_tree_highlight(event.file_path)

    def _update_file_tree_highlight(self, active_file: str | None = None) -> None:
        if active_file is None:
            active_file = self._get_current_file()
        for btn in self.query(".filetree-file"):
            fp = getattr(btn, "file_path", None)
            if fp == active_file:
                btn.add_class("filetree-active")
            else:
                btn.remove_class("filetree-active")

    # --- Hunk navigation ---

    def _navigate_hunk(self, delta: int) -> None:
        viewer = self._get_active_viewer()
        if not viewer:
            return
        collapsibles = list(viewer.query("Collapsible"))
        if not collapsibles:
            return
        current_y = viewer.scroll_offset.y
        if delta > 0:
            for c in collapsibles:
                widget_y = c.region.y - viewer.region.y + viewer.scroll_offset.y
                if widget_y > current_y + 2:
                    viewer.scroll_to(y=widget_y, animate=False)
                    return
            viewer.scroll_to(y=collapsibles[0].region.y - viewer.region.y + viewer.scroll_offset.y, animate=False)
        else:
            for c in reversed(collapsibles):
                widget_y = c.region.y - viewer.region.y + viewer.scroll_offset.y
                if widget_y < current_y - 2:
                    viewer.scroll_to(y=widget_y, animate=False)
                    return
            last = collapsibles[-1]
            viewer.scroll_to(y=last.region.y - viewer.region.y + viewer.scroll_offset.y, animate=False)

    def action_next_hunk(self) -> None:
        self._navigate_hunk(1)

    def action_prev_hunk(self) -> None:
        self._navigate_hunk(-1)

    # --- Copy path ---

    def action_copy_path(self) -> None:
        viewer = self._get_active_viewer()
        if not viewer:
            return
        try:
            import pyperclip
            pyperclip.copy(viewer.file_path)
            self.notify(f"Copied: {viewer.file_path}", timeout=2)
        except ImportError:
            subprocess.run(
                ["pbcopy"] if sys.platform == "darwin" else ["xclip", "-selection", "clipboard"],
                input=viewer.file_path.encode(),
                check=False,
            )
            self.notify(f"Copied: {viewer.file_path}", timeout=2)

    async def action_close_panel(self) -> None:
        if self.query("SettingsPanel"):
            await self._remove_all("SettingsPanel")
            self.set_focus(None)
        elif self.query("SearchBar"):
            self._search_term = ""
            if self._search_debounce:
                self._search_debounce.stop()
                self._search_debounce = None
            await self._remove_all("SearchBar")
            await self._refresh_tabs()

    # --- Comment navigation ---

    def _get_comment_locations(self) -> list[tuple[str, int]]:
        locations: list[tuple[str, int]] = []
        for file_path, file_comments in self.comments.items():
            for c in file_comments:
                locations.append((file_path, c.get("line_index", 0)))
        return locations

    async def action_next_comment(self) -> None:
        await self._navigate_comment(1)

    async def action_prev_comment(self) -> None:
        await self._navigate_comment(-1)

    async def _navigate_comment(self, delta: int) -> None:
        locations = self._get_comment_locations()
        if not locations:
            self.notify("No comments", timeout=2)
            self._comment_nav_index = -1
            return

        if self._comment_nav_index < 0 or self._comment_nav_index >= len(locations):
            self._comment_nav_index = 0 if delta > 0 else len(locations) - 1
        else:
            self._comment_nav_index = (self._comment_nav_index + delta) % len(locations)

        file_path, line_idx = locations[self._comment_nav_index]
        self.clear_notifications()
        self.notify(f"Comment {self._comment_nav_index + 1}/{len(locations)}: {short_name(file_path)}:{line_idx}", timeout=2)

        if not await self._activate_file_tab(file_path, line_idx):
            self.show_reviewed = True
            self._update_toggle_button()
            await self._refresh_tabs()
            await self._activate_file_tab(file_path, line_idx)

    # --- Search ---

    async def action_search(self) -> None:
        if self.query("SearchBar"):
            return
        await self.mount(SearchBar(id="search-bar"), before=self.query_one("#file-tabs", TabbedContent))

    @on(SearchBar.SearchChanged)
    def search_changed(self, event: SearchBar.SearchChanged) -> None:
        self._search_term = event.term
        if self._search_debounce:
            self._search_debounce.stop()
        self._search_debounce = self.set_timer(0.4, self._do_search_refresh)

    async def _do_search_refresh(self) -> None:
        await self._refresh_tabs()
        if self._search_term:
            viewer = self._get_active_viewer()
            if viewer:
                for dl in viewer.query(DiffLine):
                    if dl._search_match:
                        dl.scroll_visible(animate=False)
                        break

    @on(SearchBar.SearchClosed)
    async def search_closed(self, event: SearchBar.SearchClosed) -> None:
        self._search_term = ""
        if self._search_debounce:
            self._search_debounce.stop()
            self._search_debounce = None
        await self._remove_all("SearchBar")
        await self._refresh_tabs()

    # --- Editor ---

    @on(DiffLine.OpenInEditor)
    def open_in_editor(self, event: DiffLine.OpenInEditor) -> None:
        full_path = self._repo_root / event.file_path
        editor = self._editor
        if editor in ("code", "cursor"):
            cmd = [editor, "--goto", f"{full_path}:{event.line_num}"]
        elif editor in ("vim", "nvim"):
            cmd = [editor, f"+{event.line_num}", str(full_path)]
        else:
            cmd = [editor, str(full_path)]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # --- Comments ---

    @on(DiffLine.Clicked)
    async def diff_line_clicked(self, event: DiffLine.Clicked) -> None:
        await self._remove_all("InlineCommentBox")
        diff_line = event.diff_line
        file_line_num = resolve_line_num(diff_line.old_num, diff_line.new_num)
        comment_box = InlineCommentBox(
            line_index=diff_line.line_index,
            line_text=diff_line.raw_text,
            file_path=diff_line.file_path,
            file_line_num=file_line_num,
        )
        assert diff_line.parent is not None
        await diff_line.parent.mount(comment_box, after=diff_line)  # type: ignore[union-attr]

    @on(InlineCommentBox.Submitted)
    async def inline_comment_submitted(self, event: InlineCommentBox.Submitted) -> None:
        if event.file_path not in self.comments:
            self.comments[event.file_path] = []
        self.comments[event.file_path].append({
            "file_path": event.file_path,
            "line_text": event.line_text,
            "line_index": event.line_index,
            "file_line_num": event.file_line_num,
            "comment": event.comment,
            "author": self._user_name,
            "author_type": "user",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        save_comments(self.comments)
        self._comment_nav_index = -1
        self._refresh_comments_select()
        box = self.query_one("InlineCommentBox")
        assert box.parent is not None
        await box.parent.mount(InlineCommentDisplay(event.comment, event.file_path, event.line_index, author=self._user_name, author_type="user"), before=box)  # type: ignore[union-attr]
        await box.remove()
        self.notify(f"Comment added to {short_name(event.file_path)}", timeout=3)

    @on(InlineCommentBox.Cancelled)
    async def inline_comment_cancelled(self, event: InlineCommentBox.Cancelled) -> None:
        await self._remove_all("InlineCommentBox")

    @on(InlineCommentDisplay.ReplySubmitted)
    async def inline_comment_reply(self, event: InlineCommentDisplay.ReplySubmitted) -> None:
        file_comments = self.comments.get(event.file_path, [])
        for c in file_comments:
            if c.get("line_index") == event.line_index and c.get("comment") == event.parent_comment:
                if "replies" not in c:
                    c["replies"] = []
                c["replies"].append({"text": event.reply, "author": self._user_name, "author_type": "user"})
                break
        save_comments(self.comments)
        self._refresh_comments_select()
        viewer = self._get_active_viewer()
        if viewer:
            viewer._comments = self.comments

    @on(InlineCommentDisplay.Edited)
    async def inline_comment_edited(self, event: InlineCommentDisplay.Edited) -> None:
        file_comments = self.comments.get(event.file_path, [])
        for c in file_comments:
            if c.get("line_index") == event.line_index and c.get("comment") == event.old_comment:
                c["comment"] = event.new_comment
                break
        save_comments(self.comments)
        self._refresh_comments_select()
        viewer = self._get_active_viewer()
        if viewer:
            viewer._comments = self.comments

    @on(InlineCommentDisplay.Deleted)
    async def inline_comment_deleted(self, event: InlineCommentDisplay.Deleted) -> None:
        file_comments = self.comments.get(event.file_path, [])
        self.comments[event.file_path] = [
            c for c in file_comments
            if not (c.get("line_index") == event.line_index and c.get("comment") == event.comment_text)
        ]
        if not self.comments[event.file_path]:
            del self.comments[event.file_path]
        save_comments(self.comments)
        self._comment_nav_index = -1
        self._refresh_comments_select()
        await event.widget.remove()

    def _refresh_comments_select(self) -> None:
        try:
            sel = self.query_one("#comments-select", Select)
        except NoMatches:
            return

        all_comments: list[tuple[str, str]] = []
        for file_path, file_comments in self.comments.items():
            name = short_name(file_path)
            count = len(file_comments)
            for idx, c in enumerate(file_comments):
                if count > 1:
                    label = f"- {name} ({idx + 1})"
                else:
                    label = f"- {name}"
                all_comments.append((label, f"{file_path}:{c.get('line_index', 0)}"))

        if all_comments:
            sel.set_options(all_comments)
            sel.prompt = f"Comments ({len(all_comments)})"
            sel.disabled = False
            sel.clear()
        else:
            sel.set_options([])
            sel.prompt = "No comments"
            sel.disabled = True

    @on(Select.Changed, "#comments-select")
    async def comment_selected(self, event: Select.Changed) -> None:
        if event.value is None or event.value is Select.BLANK:
            return
        value = str(event.value)
        if not value:
            return
        parts = value.rsplit(":", 1)
        if len(parts) != 2:
            return
        file_path, line_idx = parts[0], int(parts[1])

        if not await self._activate_file_tab(file_path, line_idx):
            self.show_reviewed = True
            self._update_toggle_button()
            await self._refresh_tabs()
            await self._activate_file_tab(file_path, line_idx)

        try:
            self.query_one("#comments-select", Select).clear()
        except NoMatches:
            pass

    async def _activate_file_tab(self, file_path: str, line_idx: int) -> bool:
        tabs = self.query_one("#file-tabs", TabbedContent)
        for i, path in enumerate(self._active_files):
            if path == file_path and i < len(self._active_tab_ids):
                tab_id = self._active_tab_ids[i]
                tabs.active = tab_id
                viewer = self._get_active_viewer()
                if viewer:
                    await self._scroll_to_line(viewer, line_idx)
                return True
        return False

    async def _scroll_to_line(self, viewer: DiffViewer | FullFileViewer, line_index: int) -> None:
        for dl in viewer.query(DiffLine):
            if dl.line_index == line_index:
                viewer_height = viewer.size.height
                line_y = dl.region.y - viewer.region.y + viewer.scroll_offset.y
                viewer.scroll_to(y=max(0, line_y - viewer_height // 2), animate=False)
                return

    # --- Review ---

    async def action_toggle_review(self) -> None:
        viewer = self._get_active_viewer()
        if not viewer:
            return
        path = viewer.file_path
        name = short_name(path)
        marking_reviewed = not self._is_reviewed(path)
        if marking_reviewed:
            self.reviewed[path] = get_file_mtime(path)
            self._last_file_mtimes[path] = self.reviewed[path]
            save_reviewed(self.reviewed)
            self.notify(f"Marked {name} as reviewed", timeout=3)
        else:
            del self.reviewed[path]
            save_reviewed(self.reviewed)
            self.notify(f"Unmarked {name} as reviewed", timeout=3)

        if marking_reviewed and self.show_reviewed:
            next_unreviewed = self._find_next_unreviewed(path)
            await self._refresh_tabs(restore_file=next_unreviewed if next_unreviewed else path)
        else:
            await self._refresh_tabs()
        self._update_review_button()

    def _find_next_unreviewed(self, current_path: str) -> str | None:
        files = self._get_visible_files()
        try:
            idx = files.index(current_path)
        except ValueError:
            idx = -1
        for offset in range(1, len(files)):
            candidate = files[(idx + offset) % len(files)]
            if not self._is_reviewed(candidate):
                return candidate
        return None

    async def action_show_all(self) -> None:
        self.show_reviewed = not self.show_reviewed
        self._update_toggle_button()
        await self._refresh_tabs()

    def _save_settings(self) -> None:
        save_settings({"theme": ALL_THEMES[self._theme_index].name, "editor": self._editor, "view_mode": self._view_mode, "user_name": self._user_name})

    def action_quit(self) -> None:
        self.exit()


if __name__ == "__main__":
    from diffui.cli import main

    main()
