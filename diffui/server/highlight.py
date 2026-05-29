from __future__ import annotations

import html

from pygments import lex

from diffui.diff import (
    classify_line,
    get_lexer,
    pair_diff_lines,
    parse_line_numbers,
    split_into_hunks,
    strip_diff_prefix,
    token_color,
)
from diffui.git_utils import diff_stat
from diffui.themes.theme import Theme


def highlight_line_html(code: str, lexer, style_map: dict) -> str:
    parts: list[str] = []
    for token_type, value in lex(code, lexer):
        escaped = html.escape(value)
        color = token_color(token_type, style_map)
        if color:
            parts.append(f'<span style="color:{color}">{escaped}</span>')
        else:
            parts.append(escaped)
    result = "".join(parts)
    if result.endswith("\n"):
        result = result[:-1]
    return result


def _apply_word_highlights(code_html: str, ranges: list[tuple[int, int]], code_plain: str) -> str:
    if not ranges:
        return code_html
    marked_chars: set[int] = set()
    for start, end in ranges:
        for i in range(start, min(end, len(code_plain))):
            marked_chars.add(i)

    result: list[str] = []
    plain_idx = 0
    i = 0
    in_highlight = False
    while i < len(code_html):
        if code_html[i] == "<":
            if in_highlight:
                result.append("</mark>")
                in_highlight = False
            end_tag = code_html.find(">", i)
            if end_tag == -1:
                result.append(code_html[i:])
                break
            result.append(code_html[i : end_tag + 1])
            i = end_tag + 1
            continue
        if code_html[i] == "&":
            semi = code_html.find(";", i)
            if semi == -1:
                result.append(code_html[i])
                plain_idx += 1
                i += 1
                continue
            entity = code_html[i : semi + 1]
            should_mark = plain_idx in marked_chars
            if should_mark and not in_highlight:
                result.append("<mark>")
                in_highlight = True
            elif not should_mark and in_highlight:
                result.append("</mark>")
                in_highlight = False
            result.append(entity)
            plain_idx += 1
            i = semi + 1
            continue
        should_mark = plain_idx in marked_chars
        if should_mark and not in_highlight:
            result.append("<mark>")
            in_highlight = True
        elif not should_mark and in_highlight:
            result.append("</mark>")
            in_highlight = False
        result.append(code_html[i])
        plain_idx += 1
        i += 1
    if in_highlight:
        result.append("</mark>")
    return "".join(result)


def parse_diff_to_json(diff_text: str, file_path: str, theme: Theme) -> dict:
    lines = diff_text.splitlines()
    if not lines:
        return {"file_path": file_path, "adds": 0, "dels": 0, "hunks": []}

    adds, dels = diff_stat(diff_text)
    numbers = parse_line_numbers(diff_text)
    word_highlights = pair_diff_lines(lines)
    hunks = split_into_hunks(lines)
    lexer = get_lexer(file_path)

    result_hunks: list[dict] = []
    global_idx = 0

    for hunk_header, hunk_lines in hunks:
        result_lines: list[dict] = []
        for line in hunk_lines:
            i = global_idx
            line_type = classify_line(line)
            old_num, new_num = numbers[i] if i < len(numbers) else (None, None)

            if line_type in ("add", "remove", "context"):
                code = strip_diff_prefix(line)
                prefix = line[0] if line else " "
                code_html = highlight_line_html(code, lexer, theme.syntax)
                prefix_html = html.escape(prefix)
                if i in word_highlights:
                    code_html = _apply_word_highlights(code_html, word_highlights[i], code)
                line_html = f'<span class="diff-prefix">{prefix_html}</span>{code_html}'
            elif line_type == "hunk":
                line_html = f'<span class="hunk-text">{html.escape(line)}</span>'
            else:
                line_html = html.escape(line)

            result_lines.append(
                {
                    "index": i,
                    "type": line_type,
                    "old_num": old_num,
                    "new_num": new_num,
                    "html": line_html,
                    "text": line,
                }
            )
            global_idx += 1

        result_hunks.append({"header": hunk_header[:80], "lines": result_lines})

    return {"file_path": file_path, "adds": adds, "dels": dels, "hunks": result_hunks}
