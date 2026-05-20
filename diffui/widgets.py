from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Click, Key
from textual.message import Message
from textual.widgets import (
    Button,
    Collapsible,
    Input,
    Select,
    Static,
    TextArea,
)

from diffui.diff import (
    classify_line,
    get_lexer,
    highlight_line,
    pair_diff_lines,
    parse_line_numbers,
    resolve_line_num,
    split_into_hunks,
    strip_diff_prefix,
)
from diffui.git_utils import diff_stat, get_file_content
from diffui.themes import ALL_THEMES, get_current_theme

VIEW_MODE_DIFF = "diff"
VIEW_MODE_FILE = "file"


class LazyPlaceholder(Static):
    def __init__(self, file_path: str, display_name: str, **kwargs) -> None:
        super().__init__(f"[dim]Loading {display_name}...[/dim]", markup=True, classes="lazy-placeholder", **kwargs)
        self.file_path = file_path


EDITOR_OPTIONS = [
    ("VS Code", "code"),
    ("Cursor", "cursor"),
    ("Vim", "vim"),
    ("Neovim", "nvim"),
]


class InlineCommentBox(Vertical):

    class Submitted(Message):
        def __init__(self, line_index: int, line_text: str, file_path: str, comment: str, file_line_num: int | None) -> None:
            super().__init__()
            self.line_index = line_index
            self.line_text = line_text
            self.file_path = file_path
            self.comment = comment
            self.file_line_num = file_line_num

    class Cancelled(Message):
        pass

    def __init__(self, line_index: int, line_text: str, file_path: str, file_line_num: int | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.line_index = line_index
        self.line_text = line_text
        self.file_path = file_path
        self.file_line_num = file_line_num

    def compose(self) -> ComposeResult:
        yield TextArea("", id="inline-comment-input", show_line_numbers=False, highlight_cursor_line=False, compact=True)
        with Horizontal(id="inline-comment-actions"):
            yield Button("Comment", variant="primary", id="inline-comment-save")
            yield Button("Cancel", variant="default", id="inline-comment-cancel")

    def on_mount(self) -> None:
        self.query_one("#inline-comment-input", TextArea).focus()

    @on(Button.Pressed, "#inline-comment-save")
    def save(self, event: Button.Pressed | None = None) -> None:
        text = self.query_one("#inline-comment-input", TextArea).text.strip()
        if text:
            self.post_message(self.Submitted(self.line_index, self.line_text, self.file_path, text, self.file_line_num))
        else:
            self.post_message(self.Cancelled())

    @on(Button.Pressed, "#inline-comment-cancel")
    def cancel(self, event: Button.Pressed | None = None) -> None:
        self.post_message(self.Cancelled())


class InlineCommentDisplay(Vertical):

    class Deleted(Message):
        def __init__(self, widget: InlineCommentDisplay) -> None:
            super().__init__()
            self.file_path = widget.file_path
            self.line_index = widget.line_index
            self.comment_text = widget.comment_text
            self.widget = widget

    class ReplySubmitted(Message):
        def __init__(self, file_path: str, line_index: int, parent_comment: str, reply: str) -> None:
            super().__init__()
            self.file_path = file_path
            self.line_index = line_index
            self.parent_comment = parent_comment
            self.reply = reply

    class Edited(Message):
        def __init__(self, file_path: str, line_index: int, old_comment: str, new_comment: str) -> None:
            super().__init__()
            self.file_path = file_path
            self.line_index = line_index
            self.old_comment = old_comment
            self.new_comment = new_comment

    MAX_WIDTH = 100
    MIN_WIDTH = 50

    def __init__(self, comment_text: str, file_path: str, line_index: int, replies: list | None = None, author: str = "User", author_type: str = "user", **kwargs) -> None:
        super().__init__(**kwargs)
        self.comment_text = comment_text
        self.file_path = file_path
        self.line_index = line_index
        self.author = author
        self.author_type = author_type
        self._raw_replies = replies or []

    @staticmethod
    def _parse_reply(reply: str | dict) -> tuple[str, str, str]:
        if isinstance(reply, dict):
            return (
                reply.get("text", ""),
                reply.get("author", "agent"),
                reply.get("author_type", "agent"),
            )
        return reply, "agent", "agent"

    def _has_agent_reply(self) -> bool:
        return any(self._parse_reply(r)[2] != "user" for r in self._raw_replies)

    def _is_editable(self) -> bool:
        if self.author_type != "user":
            return False
        return not self._has_agent_reply()

    def compose(self) -> ComposeResult:
        escaped = self.comment_text.replace("[", "\\[")
        is_user = self.author_type == "user"
        icon = "💬" if is_user else "🤖"
        with Horizontal(classes="comment-header"):
            yield Static(f"{icon} {self.author}", markup=True, classes="comment-label")
            yield Button("↩", variant="default", classes="comment-reply-btn")
            if self._is_editable():
                yield Button("✎", variant="default", classes="comment-edit-btn")
            yield Button("✕", variant="error", classes="comment-delete")
        yield Static(escaped, markup=True, classes="comment-body")
        for text, r_author, r_type in (self._parse_reply(r) for r in self._raw_replies):
            text_escaped = text.replace("[", "\\[")
            icon = "💬" if r_type == "user" else "🤖"
            yield Static(f"  ↳ {icon} {r_author}: {text_escaped}", markup=True, classes="comment-reply")

    def on_mount(self) -> None:
        header_len = len(self.author) + 12
        reply_lens = (len(self._parse_reply(r)[0]) for r in self._raw_replies)
        longest = max(len(self.comment_text), max(reply_lens, default=0))
        content_len = longest + 8
        width = min(self.MAX_WIDTH, max(self.MIN_WIDTH, header_len, content_len))
        self.styles.width = width

    @on(Button.Pressed, ".comment-delete")
    def delete(self, event: Button.Pressed) -> None:
        self.post_message(self.Deleted(self))

    @on(Button.Pressed, ".comment-reply-btn")
    async def show_reply_input(self, event: Button.Pressed) -> None:
        if self.query(".inline-editing, .comment-input-group"):
            return
        ta = TextArea("", classes="comment-reply-input", show_line_numbers=False, highlight_cursor_line=False, compact=True)
        save_btn = Button("Reply", variant="primary", classes="comment-reply-save")
        group = Vertical(ta, save_btn, classes="comment-input-group")
        await self.mount(group)
        ta.focus()

    @on(Button.Pressed, ".comment-edit-btn")
    async def show_edit_input(self, event: Button.Pressed) -> None:
        if self.query(".inline-editing, .comment-input-group"):
            return
        body = self.query_one(".comment-body", Static)
        body.display = False
        ta = TextArea(self.comment_text, classes="inline-editing comment-inline-edit", show_line_numbers=False, highlight_cursor_line=False, compact=True)
        save_btn = Button("Save", variant="primary", classes="inline-edit-save")
        cancel_btn = Button("Cancel", variant="default", classes="inline-edit-cancel")
        group = Vertical(ta, Horizontal(save_btn, cancel_btn, classes="inline-edit-actions"), classes="inline-edit-group")
        await self.mount(group, after=body)
        ta.focus()

    @on(Button.Pressed, ".inline-edit-save")
    async def save_inline_edit(self, event: Button.Pressed) -> None:
        await self._save_comment_edit()

    @on(Button.Pressed, ".inline-edit-cancel")
    async def cancel_inline_edit(self, event: Button.Pressed) -> None:
        await self._cancel_inline_edits()

    @on(Button.Pressed, ".comment-reply-save")
    async def submit_reply(self, event: Button.Pressed) -> None:
        try:
            ta = self.query_one(".comment-reply-input", TextArea)
            text = ta.text.strip()
        except Exception:
            return
        for group in self.query(".comment-input-group"):
            await group.remove()
        if text:
            self.post_message(self.ReplySubmitted(self.file_path, self.line_index, self.comment_text, text))
            text_escaped = text.replace("[", "\\[")
            row = Horizontal(
                Static(f"↳ 💬 {text_escaped}", markup=True, classes="comment-reply-text"),
                classes="reply-row",
            )
            await self.mount(row)

    def on_key(self, event: Key) -> None:
        if event.key == "escape" and self.query(".inline-edit-group"):
            self.call_later(self._cancel_inline_edits)
            event.stop()

    async def _cancel_inline_edits(self) -> None:
        for group in self.query(".inline-edit-group"):
            await group.remove()
        try:
            body = self.query_one(".comment-body", Static)
            body.display = True
        except Exception:
            pass

    async def _save_comment_edit(self) -> None:
        try:
            ta = self.query_one(".comment-inline-edit", TextArea)
            text = ta.text.strip()
        except Exception:
            return
        for group in self.query(".inline-edit-group"):
            await group.remove()
        try:
            body = self.query_one(".comment-body", Static)
            body.display = True
        except Exception:
            pass
        if text and text != self.comment_text:
            old_comment = self.comment_text
            self.comment_text = text
            try:
                body = self.query_one(".comment-body", Static)
                body.update(text.replace("[", "\\["))
            except Exception:
                pass
            self.post_message(self.Edited(self.file_path, self.line_index, old_comment, text))


class DiffLine(Horizontal):

    class Clicked(Message):
        def __init__(self, diff_line: DiffLine) -> None:
            super().__init__()
            self.diff_line = diff_line

    class OpenInEditor(Message):
        def __init__(self, file_path: str, line_num: int) -> None:
            super().__init__()
            self.file_path = file_path
            self.line_num = line_num

    GUTTER_WIDTH = 13

    def __init__(
        self,
        content: str,
        line_index: int,
        line_type: str,
        file_path: str,
        old_num: str | None,
        new_num: str | None,
        highlighted: Text | None = None,
        search_match: bool = False,
        **kwargs,
    ) -> None:
        self.line_index = line_index
        self.line_type = line_type
        self.file_path = file_path
        self.raw_text = content
        self.old_num = old_num or ""
        self.new_num = new_num or ""
        self._highlighted = highlighted
        self._search_match = search_match

        super().__init__(**kwargs)
        self.add_class(f"diff-{line_type}")
        if search_match:
            self.add_class("search-match")

    def compose(self) -> ComposeResult:
        theme = get_current_theme()
        gutter_old = f"{self.old_num:>4} " if self.old_num else "     "
        gutter_new = f"{self.new_num:>4} " if self.new_num else "     "

        gutter_text = Text()
        gutter_text.append(gutter_old, style=theme.gutter_fg)
        gutter_text.append("│", style=theme.gutter_sep)
        gutter_text.append(gutter_new, style=theme.gutter_fg)
        gutter_text.append("│", style=theme.gutter_sep)

        yield Static(gutter_text, classes="diff-gutter")

        if self._highlighted:
            yield Static(self._highlighted, classes="diff-code")
        else:
            yield Static(self.raw_text, classes="diff-code")

    def on_click(self, event: Click) -> None:
        if event.button == 3:
            self.post_message(self.Clicked(self))
        elif event.button == 1 and event.ctrl:
            line_num = resolve_line_num(self.old_num, self.new_num)
            if line_num:
                self.post_message(self.OpenInEditor(self.file_path, line_num))


class DiffViewer(VerticalScroll):

    def __init__(self, file_path: str, diff_text: str, comments: dict, search_term: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.file_path = file_path
        self.diff_text = diff_text
        self.diff_lines: list[str] = diff_text.splitlines()
        self._comments = comments
        self._lexer = get_lexer(file_path)
        self._search_term = search_term

    def compose(self) -> ComposeResult:
        if not self.diff_lines:
            yield Static("[dim]No changes[/dim]", markup=True)
            return

        adds, dels = diff_stat(self.diff_text)
        header_text = f"[bold]{self.file_path}[/bold]  [green]+{adds}[/green]  [red]-{dels}[/red]"
        with Horizontal(classes="diff-file-header"):
            yield Static(header_text, markup=True, classes="diff-file-path")
            yield Button("Mark reviewed", id="inline-review-btn", variant="default", classes="review-btn-mark")

        theme = get_current_theme()
        numbers = parse_line_numbers(self.diff_text)
        file_comments = self._comments.get(self.file_path, [])
        comments_by_line: dict[int, list[dict]] = {}
        for c in file_comments:
            idx = c.get("line_index")
            if idx is not None:
                comments_by_line.setdefault(idx, []).append(c)

        word_highlights = pair_diff_lines(self.diff_lines)
        hunks = split_into_hunks(self.diff_lines)
        global_idx = 0

        for hunk_header, hunk_lines in hunks:
            lines_widgets = []

            for line in hunk_lines:
                i = global_idx
                line_type = classify_line(line)
                old_num, new_num = numbers[i] if i < len(numbers) else (None, None)

                if line_type in ("add", "remove", "context"):
                    code = strip_diff_prefix(line)
                    prefix = line[0] if line else " "
                    highlighted = Text()
                    highlighted.append(prefix, style=theme.gutter_fg if line_type == "context" else None)
                    hl_text = highlight_line(code, self._lexer, theme.syntax)
                    if i in word_highlights:
                        word_style = "bold underline"
                        for start, end in word_highlights[i]:
                            hl_text.stylize(word_style, start, end)
                    highlighted.append_text(hl_text)
                elif line_type == "hunk":
                    highlighted = Text(line, style=f"{theme.hunk_fg} bold")
                else:
                    highlighted = Text(line, style=f"{theme.fg_muted} bold")

                search_match = bool(self._search_term and self._search_term.lower() in line.lower())

                dl = DiffLine(
                    line,
                    line_index=i,
                    line_type=line_type,
                    file_path=self.file_path,
                    old_num=old_num,
                    new_num=new_num,
                    highlighted=highlighted,
                    search_match=search_match,
                )
                lines_widgets.append(dl)

                if i in comments_by_line:
                    for c_data in comments_by_line[i]:
                        lines_widgets.append(InlineCommentDisplay(
                            c_data.get("comment", ""),
                            file_path=self.file_path,
                            line_index=i,
                            replies=c_data.get("replies", []),
                            author=c_data.get("author", "User"),
                            author_type=c_data.get("author_type", "user"),
                        ))

                global_idx += 1

            yield Collapsible(*lines_widgets, title=hunk_header[:80], collapsed=False)


class _FileLineStatic(Static):

    def __init__(self, line_index: int, file_path: str, rendered: Text, **kwargs) -> None:
        super().__init__(rendered, **kwargs)
        self.line_index = line_index
        self.file_path = file_path
        self.old_num = str(line_index + 1)
        self.new_num = str(line_index + 1)
        self.raw_text = rendered.plain


class FullFileViewer(VerticalScroll):

    LINES_PER_CHUNK = 50

    def __init__(self, file_path: str, comments: dict, search_term: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.file_path = file_path
        self.diff_text = ""
        self.diff_lines: list[str] = []
        self._comments = comments
        self._search_term = search_term
        self._cached_content: str | None = None

    def compose(self) -> ComposeResult:
        if self._cached_content is None:
            self._cached_content = get_file_content(self.file_path)
        content = self._cached_content
        if not content:
            yield Static("[dim]File is empty or unreadable[/dim]", markup=True)
            return

        theme = get_current_theme()
        lexer = get_lexer(self.file_path)
        lines = content.splitlines()

        adds, dels = diff_stat(self.diff_text) if self.diff_text else (0, 0)
        header_text = f"[bold]{self.file_path}[/bold]  [dim]{len(lines)} lines[/dim]"
        if adds or dels:
            header_text += f"  [green]+{adds}[/green]  [red]-{dels}[/red]"
        with Horizontal(classes="diff-file-header"):
            yield Static(header_text, markup=True, classes="diff-file-path")
            yield Button("Mark reviewed", id="inline-review-btn", variant="default", classes="review-btn-mark")

        file_comments = self._comments.get(self.file_path, [])
        comments_by_line: dict[int, list[dict]] = {}
        for c in file_comments:
            idx = c.get("line_index")
            if idx is not None:
                comments_by_line.setdefault(idx, []).append(c)

        for i, line in enumerate(lines):
            rendered = Text()
            rendered.append(f"{i + 1:>4} ", style=theme.gutter_fg)
            rendered.append("│ ", style=theme.gutter_sep)
            rendered.append_text(highlight_line(line, lexer, theme.syntax))

            yield _FileLineStatic(i, self.file_path, rendered, classes="diff-context")

            if i in comments_by_line:
                for c_data in comments_by_line[i]:
                    yield InlineCommentDisplay(
                        c_data.get("comment", ""),
                        file_path=self.file_path,
                        line_index=i,
                        replies=c_data.get("replies", []),
                        author=c_data.get("author", "User"),
                        author_type=c_data.get("author_type", "user"),
                    )


class SearchBar(Horizontal):

    class SearchChanged(Message):
        def __init__(self, term: str) -> None:
            super().__init__()
            self.term = term

    class SearchClosed(Message):
        pass

    def compose(self) -> ComposeResult:
        yield Static("Search: ", markup=True, id="search-label")
        yield Input(placeholder="Type to search...", id="search-input")
        yield Button("✕", id="search-close")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    @on(Input.Changed, "#search-input")
    def input_changed(self, event: Input.Changed) -> None:
        self.post_message(self.SearchChanged(event.value))

    @on(Button.Pressed, "#search-close")
    def close(self, event: Button.Pressed) -> None:
        self.post_message(self.SearchClosed())

    def on_key(self, event: Key) -> None:
        if event.key == "escape":
            self.post_message(self.SearchClosed())
            event.stop()


class FileTree(VerticalScroll):

    class FileSelected(Message):
        def __init__(self, file_path: str) -> None:
            super().__init__()
            self.file_path = file_path

    def __init__(self, files: list[str], reviewed: set[str] | None = None, active_file: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._files = files
        self._reviewed = reviewed or set()
        self._active_file = active_file

    def compose(self) -> ComposeResult:
        yield Static("[bold]Files[/bold]", markup=True, classes="filetree-title")
        tree: dict[str, list[str]] = {}
        for f in self._files:
            parts = f.rsplit("/", 1)
            if len(parts) == 2:
                directory, name = parts
            else:
                directory, name = ".", parts[0]
            tree.setdefault(directory, []).append(f)

        file_idx = 0
        for directory in sorted(tree.keys()):
            if directory != ".":
                yield Static(f"[dim]{directory}/[/dim]", markup=True, classes="filetree-dir")
            for file_path in sorted(tree[directory]):
                name = file_path.rsplit("/", 1)[-1]
                prefix = "✓ " if file_path in self._reviewed else "  "
                classes = "filetree-file filetree-active" if file_path == self._active_file else "filetree-file"
                btn = Button(f"{prefix}{name}", classes=classes, id=f"ft-{file_idx}")
                btn.file_path = file_path  # type: ignore[attr-defined]
                yield btn
                file_idx += 1

    @on(Button.Pressed, ".filetree-file")
    def file_clicked(self, event: Button.Pressed) -> None:
        file_path = getattr(event.button, "file_path", None)
        if file_path:
            self.post_message(self.FileSelected(file_path))


class SettingsPanel(Vertical):

    class ThemeChanged(Message):
        def __init__(self, theme_index: int) -> None:
            super().__init__()
            self.theme_index = theme_index

    class EditorChanged(Message):
        def __init__(self, editor: str) -> None:
            super().__init__()
            self.editor = editor

    class ViewModeChanged(Message):
        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode

    class UserNameChanged(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    class Closed(Message):
        pass

    def __init__(self, current_theme_index: int, current_editor: str, current_view_mode: str = VIEW_MODE_DIFF, current_user_name: str = "User", **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_theme_index = current_theme_index
        self.current_editor = current_editor
        self.current_view_mode = current_view_mode
        self.current_user_name = current_user_name
        self._ready = False

    def on_mount(self) -> None:
        self.set_timer(0.1, self._mark_ready)

    def _mark_ready(self) -> None:
        self._ready = True

    def compose(self) -> ComposeResult:
        yield Static("[bold]Settings[/bold]", markup=True, id="settings-title")
        yield Static("Theme", markup=True, classes="settings-label")
        yield Select[int](
            [(t.name, i) for i, t in enumerate(ALL_THEMES)],
            value=self.current_theme_index,
            id="theme-select",
            allow_blank=False,
        )
        yield Static("Editor", markup=True, classes="settings-label")
        yield Select[str](
            EDITOR_OPTIONS,
            value=self.current_editor,
            id="editor-select",
            allow_blank=False,
        )
        yield Static("View mode", markup=True, classes="settings-label")
        yield Select[str](
            [("Diff view", VIEW_MODE_DIFF), ("Full file", VIEW_MODE_FILE)],
            value=self.current_view_mode,
            id="view-mode-select",
            allow_blank=False,
        )
        yield Static("Display name", markup=True, classes="settings-label")
        yield Input(value=self.current_user_name, id="user-name-input")
        yield Button("Close", id="settings-close", variant="default")

    @on(Select.Changed, "#theme-select")
    def theme_changed(self, event: Select.Changed) -> None:
        if self._ready and isinstance(event.value, int):
            self.post_message(self.ThemeChanged(event.value))

    @on(Select.Changed, "#editor-select")
    def editor_changed(self, event: Select.Changed) -> None:
        if self._ready and isinstance(event.value, str):
            self.post_message(self.EditorChanged(event.value))

    @on(Select.Changed, "#view-mode-select")
    def view_mode_changed(self, event: Select.Changed) -> None:
        if self._ready and isinstance(event.value, str):
            self.post_message(self.ViewModeChanged(event.value))

    @on(Input.Submitted, "#user-name-input")
    def user_name_submitted(self, event: Input.Submitted) -> None:
        name = event.value.strip()
        if name and self._ready:
            self.post_message(self.UserNameChanged(name))

    @on(Button.Pressed, "#settings-close")
    def close(self, event: Button.Pressed) -> None:
        try:
            name = self.query_one("#user-name-input", Input).value.strip()
            if name and name != self.current_user_name:
                self.post_message(self.UserNameChanged(name))
        except Exception:
            pass
        self.post_message(self.Closed())
