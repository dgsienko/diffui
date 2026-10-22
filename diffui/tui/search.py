from __future__ import annotations

import re
from typing import ClassVar

import httpx
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from diffui.themes.theme import Theme
from diffui.tui.client import ApiClient

Target = tuple[str, int | None]
_DEBOUNCE = 0.15


class SearchScreen(ModalScreen[Target | None]):
    """Search the files in the current scope by name and content. Enter opens the file, at the line for a content hit."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_search", show=False),
        Binding("down", "move(1)", show=False),
        Binding("up", "move(-1)", show=False),
        Binding("pagedown", "move(10)", show=False),
        Binding("pageup", "move(-10)", show=False),
    ]

    def __init__(self, client: ApiClient, view: str, palette: Theme) -> None:
        super().__init__()
        self._client, self._view, self._palette = client, view, palette
        self._targets: dict[str, Target] = {}
        self._timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static("Search changed files", classes="dialog-title")
            yield Input(id="search-input", placeholder="file name or text")
            yield OptionList(id="search-results")
            yield Static("enter opens, esc closes. Matches are case-insensitive.", classes="hint")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        if self._timer:
            self._timer.stop()
        self._timer = self.set_timer(_DEBOUNCE, lambda: self.run_worker(self._search(event.value), exclusive=True))

    async def _search(self, query: str) -> None:
        results = self.query_one(OptionList)
        if not query:
            results.clear_options()
            return
        try:
            data = await self._client.search(query, self._view)
        except httpx.HTTPError as e:
            results.clear_options()
            results.add_option(Option(Text(f"Search failed: {e}"), disabled=True))
            return
        self._show(data, query)

    def _show(self, data: dict, query: str) -> None:
        p = self._palette
        mark = re.compile(re.escape(query), re.IGNORECASE)
        options: list[Option] = []
        self._targets = {}

        def add(text: Text, target: Target) -> None:
            key = f"t{len(self._targets)}"
            self._targets[key] = target
            options.append(Option(text, id=key))

        def heading(text: str) -> None:
            options.append(Option(Text(text, style=f"bold {p.accent}", no_wrap=True), disabled=True))

        if data["files"]:
            heading(f"Files ({len(data['files'])})")
            for path in data["files"]:
                label = Text(path, style=p.fg, no_wrap=True, overflow="ellipsis")
                label.highlight_regex(mark, f"bold {p.warn_fg}")
                add(label, (path, None))
        current = None
        for hit in data["hits"]:
            if hit["path"] != current:
                current = hit["path"]
                heading(current)
            label = Text(f"{hit['line']:>6}  ", style=p.gutter_fg, no_wrap=True, overflow="ellipsis")
            label.append(hit["text"].strip(), style=p.fg)
            label.highlight_regex(mark, f"bold {p.warn_fg}")
            add(label, (hit["path"], hit["line"]))
        if data["truncated"]:
            options.append(
                Option(Text("Showing the first matches only. Narrow the query.", style=p.fg_muted), disabled=True)
            )
        if not options:
            options.append(Option(Text("No matches", style=p.fg_muted), disabled=True))
        results = self.query_one(OptionList)
        results.clear_options()
        results.add_options(options)
        results.highlighted = next((i for i, o in enumerate(options) if not o.disabled), None)

    def action_move(self, step: int) -> None:
        results = self.query_one(OptionList)
        move = results.action_cursor_down if step > 0 else results.action_cursor_up
        for _ in range(abs(step)):
            move()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        results = self.query_one(OptionList)
        if results.highlighted is not None:
            self._pick(results.get_option_at_index(results.highlighted))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self._pick(event.option)

    def _pick(self, option: Option) -> None:
        if option.id in self._targets:
            self.dismiss(self._targets[option.id])

    def action_dismiss_search(self) -> None:
        self.dismiss(None)
