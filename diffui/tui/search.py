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
_SCOPES = (("changed", "Changed"), ("all", "All files"))
_NOT_IN_DIFF = "  not in diff"


class SearchScreen(ModalScreen[Target | None]):
    """Search file names and content."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss_search", show=False),
        Binding("tab", "toggle_scope", show=False),
        Binding("down", "move(1)", show=False),
        Binding("up", "move(-1)", show=False),
        Binding("pagedown", "move(10)", show=False),
        Binding("pageup", "move(-10)", show=False),
    ]

    def __init__(self, client: ApiClient, view: str, palette: Theme) -> None:
        super().__init__()
        self._client, self._view, self._palette = client, view, palette
        self._scope = "changed"
        self._targets: dict[str, Target] = {}
        self._timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(self._title(), classes="dialog-title", id="search-title")
            yield Input(placeholder="file name or text")
            yield OptionList()
            yield Static(
                "enter opens, tab switches Changed and All files, esc closes. Text matches ignore case.", classes="hint"
            )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def _title(self) -> Text:
        title = Text("Search ", style="bold")
        for scope, name in _SCOPES:
            title.append(f" {name} ", style="reverse" if scope == self._scope else "dim")
        return title

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._schedule(event.value, _DEBOUNCE)

    def _schedule(self, query: str, delay: float) -> None:
        if self._timer:
            self._timer.stop()
        self._timer = self.set_timer(delay, lambda: self.run_worker(self._search(query), exclusive=True))

    def action_toggle_scope(self) -> None:
        self._scope = "all" if self._scope == "changed" else "changed"
        self.query_one("#search-title", Static).update(self._title())
        self._schedule(self.query_one(Input).value, 0)

    async def _search(self, query: str) -> None:
        results = self.query_one(OptionList)
        if not query:
            results.clear_options()
            return
        try:
            data = await self._client.search(query, self._view, self._scope)
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

        def heading(text: str, changed: bool = True) -> None:
            label = Text(text, style=f"bold {p.accent}", no_wrap=True)
            if not changed:
                label.append(_NOT_IN_DIFF, style=f"not bold {p.fg_muted}")
            options.append(Option(label, disabled=True))

        files = data["files"]
        if files:
            heading(f"Files ({len(files)})")
            for f in files:
                label = Text(f["path"], style=p.fg if f["changed"] else p.fg_muted, no_wrap=True, overflow="ellipsis")
                label.highlight_regex(mark, f"bold {p.warn_fg}")
                if not f["changed"]:
                    label.append(_NOT_IN_DIFF, style=p.gutter_fg)
                add(label, (f["path"], None))
        current = None
        for hit in data["hits"]:
            changed = hit["changed"]
            if hit["path"] != current:
                current = hit["path"]
                heading(current, changed)
            label = Text(f"{hit['line']:>6}  ", style=p.gutter_fg, no_wrap=True, overflow="ellipsis")
            label.append(hit["text"].strip(), style=p.fg if changed else p.fg_muted)
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
        self.dismiss(self._targets[option.id])

    def action_dismiss_search(self) -> None:
        self.dismiss(None)
