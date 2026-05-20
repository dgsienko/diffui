from __future__ import annotations

import difflib
import re

from pygments import lex
from pygments.lexers import get_lexer_for_filename
from pygments.lexers.special import TextLexer
from rich.text import Text

_META_PREFIXES = ("---", "+++", "diff ", "index ")
_HUNK_RE = re.compile(r"^@@ -(\d+)")
_HUNK_NEW_RE = re.compile(r"\+(\d+)")


def _is_meta_line(line: str) -> bool:
    return any(line.startswith(p) for p in _META_PREFIXES)


def get_lexer(file_path: str):
    try:
        return get_lexer_for_filename(file_path, stripnl=False, stripall=False)
    except Exception:
        return TextLexer(stripnl=False, stripall=False)


def token_color(token_type, style_map: dict) -> str | None:
    while token_type:
        if token_type in style_map:
            return style_map[token_type]
        token_type = token_type.parent
    return None


def highlight_line(code: str, lexer, style_map: dict) -> Text:
    text = Text()
    for token_type, value in lex(code, lexer):
        color = token_color(token_type, style_map)
        if color:
            text.append(value, style=color)
        else:
            text.append(value)
    if text.plain.endswith("\n"):
        text.right_crop(1)
    return text


def parse_line_numbers(diff_text: str) -> list[tuple[str | None, str | None]]:
    numbers: list[tuple[str | None, str | None]] = []
    old_num = 0
    new_num = 0
    for line in diff_text.splitlines():
        hunk = _HUNK_RE.match(line)
        if hunk:
            old_num = int(hunk.group(1))
            new_num_match = _HUNK_NEW_RE.search(line)
            new_num = int(new_num_match.group(1)) if new_num_match else 0
            numbers.append((None, None))
        elif _is_meta_line(line):
            numbers.append((None, None))
        elif line.startswith("-"):
            numbers.append((str(old_num), None))
            old_num += 1
        elif line.startswith("+"):
            numbers.append((None, str(new_num)))
            new_num += 1
        else:
            numbers.append((str(old_num), str(new_num)))
            old_num += 1
            new_num += 1
    return numbers


def resolve_line_num(old_num: str, new_num: str) -> int | None:
    if new_num:
        return int(new_num)
    if old_num:
        return int(old_num)
    return None


def classify_line(line: str) -> str:
    if _is_meta_line(line):
        return "meta"
    if line.startswith("@@"):
        return "hunk"
    if line.startswith("+"):
        return "add"
    if line.startswith("-"):
        return "remove"
    return "context"


def strip_diff_prefix(line: str) -> str:
    if line.startswith("+") or line.startswith("-"):
        return line[1:]
    if line.startswith(" "):
        return line[1:]
    return line


def _word_offsets(words: list[str]) -> list[int]:
    offsets = [0] * (len(words) + 1)
    for i, w in enumerate(words):
        offsets[i + 1] = offsets[i] + len(w) + 1
    return offsets


def word_diff_ranges(old_line: str, new_line: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    old_words = old_line.split()
    new_words = new_line.split()
    old_off = _word_offsets(old_words)
    new_off = _word_offsets(new_words)
    matcher = difflib.SequenceMatcher(None, old_words, new_words)
    old_ranges: list[tuple[int, int]] = []
    new_ranges: list[tuple[int, int]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            old_ranges.append((old_off[i1], max(old_off[i2] - 1, old_off[i1])))
        if tag in ("replace", "insert"):
            new_ranges.append((new_off[j1], max(new_off[j2] - 1, new_off[j1])))
    return old_ranges, new_ranges


def pair_diff_lines(lines: list[str]) -> dict[int, list[tuple[int, int]]]:
    paired: dict[int, list[tuple[int, int]]] = {}
    i = 0
    while i < len(lines):
        if lines[i].startswith("-") and not lines[i].startswith("---"):
            removes = []
            while i < len(lines) and lines[i].startswith("-") and not lines[i].startswith("---"):
                removes.append(i)
                i += 1
            adds = []
            while i < len(lines) and lines[i].startswith("+") and not lines[i].startswith("+++"):
                adds.append(i)
                i += 1
            for r_idx, a_idx in zip(removes, adds, strict=False):
                old_content = lines[r_idx][1:]
                new_content = lines[a_idx][1:]
                old_ranges, new_ranges = word_diff_ranges(old_content, new_content)
                if old_ranges:
                    paired[r_idx] = old_ranges
                if new_ranges:
                    paired[a_idx] = new_ranges
        else:
            i += 1
    return paired


def split_into_hunks(lines: list[str]) -> list[tuple[str, list[str]]]:
    hunks: list[tuple[str, list[str]]] = []
    header_lines: list[str] = []
    current_hunk_header = ""
    current_hunk_lines: list[str] = []

    for line in lines:
        if line.startswith("@@"):
            if current_hunk_header:
                hunks.append((current_hunk_header, current_hunk_lines))
            elif header_lines:
                hunks.append(("File header", header_lines))
            current_hunk_header = line
            current_hunk_lines = [line]
        elif not current_hunk_header:
            header_lines.append(line)
        else:
            current_hunk_lines.append(line)

    if current_hunk_header:
        hunks.append((current_hunk_header, current_hunk_lines))
    elif header_lines:
        hunks.append(("File header", header_lines))

    return hunks
