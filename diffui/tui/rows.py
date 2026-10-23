from __future__ import annotations

from dataclasses import dataclass, field

from pygments import lex
from textual.strip import Strip

from diffui.diff import token_color
from diffui.tui.style import Tokens

MAX_CODE_COLS = 1000


def code_of(line: dict) -> str:
    """The text a line draws and the find bar searches: no diff prefix, tabs expanded, capped."""
    return line["text"][1:].expandtabs(4)[:MAX_CODE_COLS]


@dataclass(slots=True)
class Row:
    kind: str  # note, hunk, line or thread
    text: str = ""
    # The line a comment on this row is stored against: the new side when the row has both.
    line: dict | None = None
    # Split rows only: the left and right lines. A context line is both sides.
    old: dict | None = None
    new: dict | None = None
    thread: dict | None = None
    top: int = 0
    height: int = 1
    tokens: dict[int, Tokens] = field(default_factory=dict)
    strips: dict[bool, list[Strip]] = field(default_factory=dict)

    def key(self) -> tuple:
        if self.line:
            return ("line", self.line["index"])
        if self.thread:
            return ("thread", self.thread.get("id"))
        return (self.kind, self.text)

    def mirrored(self) -> bool:
        """A split row's context line, shown on both sides."""
        return self.old is not None and self.old is self.new

    def lines(self) -> list[dict]:
        """The distinct diff lines the row shows."""
        if self.old is None and self.new is None:
            return [self.line] if self.line else []
        return [self.old] if self.mirrored() else [ln for ln in (self.old, self.new) if ln]

    def sides(self) -> list[tuple[str, dict]]:
        """(side, line) pairs for find: unified rows have one side, split rows up to two, a mirrored line its new side."""
        if self.old is None and self.new is None:
            return [("u", self.line)] if self.line else []
        if self.mirrored():
            return [("new", self.new)]
        return [(side, ln) for side, ln in (("old", self.old), ("new", self.new)) if ln]

    def paired(self) -> bool:
        return self.old is not None and self.new is not None and not self.mirrored()

    def tokens_of(self, line: dict, lexer, syntax: dict) -> Tokens:
        cached = self.tokens.get(line["index"])
        if cached is None:
            cached = [(value, token_color(token_type, syntax)) for token_type, value in lex(code_of(line), lexer)]
            if cached and cached[-1][0].endswith("\n"):
                last, color = cached.pop()
                if last != "\n":
                    cached.append((last[:-1], color))
            self.tokens[line["index"]] = cached
        return cached


def split_pairs(lines: list[dict]) -> list[tuple[dict | None, dict | None]]:
    """Left and right lines of a hunk: a run of removes sits beside the run of adds that follows it."""
    pairs: list[tuple[dict | None, dict | None]] = []
    removes: list[dict] = []
    adds: list[dict] = []

    def flush() -> None:
        for i in range(max(len(removes), len(adds))):
            pairs.append((removes[i] if i < len(removes) else None, adds[i] if i < len(adds) else None))
        removes.clear()
        adds.clear()

    for line in lines:
        if line["type"] == "remove":
            if adds:
                flush()
            removes.append(line)
        elif line["type"] == "add":
            adds.append(line)
        elif line["type"] != "meta":
            flush()
            pairs.append((line, line))
    flush()
    return pairs


def build_rows(data: dict, comments: list[dict], split: bool = False) -> list[Row]:
    by_line: dict[int, list[dict]] = {}
    for c in comments:
        by_line.setdefault(c.get("line_index", -1), []).append(c)
    placed: set[int] = set()
    rows: list[Row] = []

    def add_line(row: Row) -> None:
        rows.append(row)
        for line in row.lines():
            for c in by_line.get(line["index"], []):
                rows.append(Row("thread", thread=c))
                placed.add(id(c))

    if data.get("file_note"):
        rows.append(Row("note", text=data["file_note"]))
    for hunk in data.get("hunks", []):
        if hunk["header"]:
            rows.append(Row("hunk", text=hunk["header"]))
        if split:
            for old, new in split_pairs(hunk["lines"]):
                add_line(Row("line", line=new or old, old=old, new=new))
        else:
            for line in hunk["lines"]:
                add_line(Row("line", line=line))
    if not rows:
        rows.append(Row("note", text="No changes in this file."))
    loose = [c for c in comments if id(c) not in placed]
    if loose:
        rows.append(Row("note", text="Comments on lines that are no longer in the diff"))
        rows.extend(Row("thread", thread=c) for c in loose)
    return rows
