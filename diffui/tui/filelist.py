from __future__ import annotations

from rich.text import Text
from textual import events
from textual.message import Message
from textual.widgets import OptionList
from textual.widgets.option_list import Option, OptionDoesNotExist

from diffui.themes import DEFAULT_THEME
from diffui.themes.theme import Theme
from diffui.tui.diffview import add_fg


class FileList(OptionList, can_focus=False):
    class Picked(Message):
        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.palette: Theme = DEFAULT_THEME
        self._files: list[dict] = []
        self._active: str | None = None
        self._flat = False
        self._width, self._adds_w, self._dels_w = 20, 2, 2

    def set_files(self, files: list[dict], active: str | None, flat: bool) -> None:
        self._files, self._active, self._flat = files, active, flat
        self._rebuild()

    def set_active(self, path: str | None) -> None:
        previous, self._active = self._active, path
        for f in self._files:
            if f["path"] in (previous, path):
                self.replace_option_prompt(f["path"], self._file_text(f))
        self._highlight()

    def on_resize(self, event: events.Resize) -> None:
        if self._files:
            self._rebuild()

    def _rebuild(self) -> None:
        self._width = max(self.size.width - 2, 20)
        self._adds_w = max((len(str(f["adds"])) for f in self._files), default=1) + 1
        self._dels_w = max((len(str(f["dels"])) for f in self._files), default=1) + 1
        options: list[Option] = []
        last_dir = None
        for f in self._files:
            if not self._flat and f["dir"] != last_dir:
                last_dir = f["dir"]
                options.append(Option(Text(f" {last_dir}", style=f"bold {self.palette.fg_muted}"), disabled=True))
            options.append(Option(self._file_text(f), id=f["path"]))
        self.clear_options()
        self.add_options(options)
        self._highlight()

    def _file_text(self, f: dict) -> Text:
        p = self.palette
        risk = {"high": p.delete_fg, "medium": p.warn_fg}.get(f["risk_level"])
        reviewed = f["reviewed"]
        open_count = f["open_comment_count"]
        text = Text("▸" if f["path"] == self._active else " ", style=p.accent)
        text.append("✓ " if reviewed else "  ", style=p.accent)
        text.append("● " if risk else "  ", style=risk or "")
        right = Text(f"✎{open_count}".rjust(4) if open_count else "    ", style=p.comment_accent)
        right.append(f" +{f['adds']}".rjust(self._adds_w + 1), style=add_fg(p))
        right.append(f" -{f['dels']}".rjust(self._dels_w + 1), style=p.delete_fg)
        name = f["path"] if self._flat else f["short_name"]
        room = max(self._width - text.cell_len - right.cell_len - 1, 1)
        if len(name) > room:
            name = "…" + name[-(room - 1) :] if self._flat else name[: room - 1] + "…"
        label = Text(name.ljust(room), style=p.fg_muted if reviewed else p.fg, no_wrap=True)
        return text + label + Text(" ") + right

    def _highlight(self) -> None:
        if self._active is None:
            return
        try:
            self.highlighted = self.get_option_index(self._active)
        except OptionDoesNotExist:
            self.highlighted = None

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if event.option.id:
            self.post_message(self.Picked(event.option.id))
