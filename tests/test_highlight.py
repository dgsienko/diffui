from __future__ import annotations

import pytest

from diffui.diff import get_lexer
from diffui.server.highlight import (
    _apply_word_highlights,
    highlight_file_to_json,
    highlight_line_html,
    parse_diff_to_json,
)
from diffui.themes.definitions import CATPPUCCIN_MOCHA


class TestHighlightLineHtml:
    def test_plain_text(self):
        lexer = get_lexer("file.txt")
        result = highlight_line_html("hello world", lexer, {})
        assert "hello world" in result

    def test_html_escaping(self):
        lexer = get_lexer("file.txt")
        result = highlight_line_html("<script>alert(1)</script>", lexer, {})
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_syntax_coloring(self):
        lexer = get_lexer("file.py")
        result = highlight_line_html("def foo():", lexer, CATPPUCCIN_MOCHA.syntax)
        assert "<span" in result
        assert "color:" in result

    def test_strips_trailing_newline(self):
        lexer = get_lexer("file.txt")
        result = highlight_line_html("hello\n", lexer, {})
        assert not result.endswith("\n")

    def test_empty_line(self):
        lexer = get_lexer("file.txt")
        result = highlight_line_html("", lexer, {})
        assert result == ""


@pytest.mark.parametrize(
    ("code_html", "ranges", "plain", "marked"),
    [
        pytest.param(
            '<span style="color:red">hello</span>', [], "hello", '<span style="color:red">hello</span>', id="no-ranges"
        ),
        pytest.param("hello world", [(0, 5)], "hello world", "<mark>hello</mark> world", id="plain-text"),
        pytest.param(
            '<span style="color:red">abc</span>',
            [(0, 3)],
            "abc",
            '<span style="color:red"><mark>abc</mark></span>',
            id="inside-span",
        ),
        pytest.param(
            "&lt;div&gt;", [(0, 5)], "<div>", "<mark>&lt;div&gt;</mark>", id="entities-count-as-one-character"
        ),
        pytest.param("&lt;div&gt;", [(0, 1)], "<div>", "<mark>&lt;</mark>div&gt;", id="range-ends-inside-entities"),
    ],
)
def test_apply_word_highlights(code_html, ranges, plain, marked):
    assert _apply_word_highlights(code_html, ranges, plain) == marked


class TestParseDiffToJson:
    def test_empty_diff(self):
        result = parse_diff_to_json("", "file.py", CATPPUCCIN_MOCHA)
        assert result["file_path"] == "file.py"
        assert result["adds"] == 0
        assert result["dels"] == 0
        assert result["hunks"] == []

    def test_simple_add(self):
        diff = "diff --git a/f.py b/f.py\n--- /dev/null\n+++ b/f.py\n@@ -0,0 +1,2 @@\n+line one\n+line two\n"
        result = parse_diff_to_json(diff, "f.py", CATPPUCCIN_MOCHA)
        assert (result["adds"], result["dels"]) == (2, 0)
        lines = result["hunks"][-1]["lines"]
        assert [(line["type"], line["new_num"]) for line in lines] == [("add", "1"), ("add", "2")]
        assert all("html" in line for line in lines)

    def test_line_numbers_track_both_sides(self):
        diff = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n@@ -1,2 +1,2 @@\n-old\n+new\n ctx\n"
        lines = parse_diff_to_json(diff, "f.py", CATPPUCCIN_MOCHA)["hunks"][-1]["lines"]
        assert [(ln["type"], ln["old_num"], ln["new_num"]) for ln in lines] == [
            ("remove", "1", None),
            ("add", None, "1"),
            ("context", "2", "2"),
        ]

    def test_header_and_hunk_lines_are_not_emitted(self):
        diff = "diff --git a/f.py b/f.py\nnew file mode 100644\n--- /dev/null\n+++ b/f.py\n@@ -0,0 +1 @@\n+x\n"
        result = parse_diff_to_json(diff, "f.py", CATPPUCCIN_MOCHA)
        assert [h["header"] for h in result["hunks"]] == ["@@ -0,0 +1 @@"]
        assert [line["type"] for line in result["hunks"][0]["lines"]] == ["add"]
        assert result["file_note"] == "New file"

    def test_line_index_counts_skipped_header_and_hunk_lines(self):
        diff = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new\n@@ -9 +9 @@\n-a\n+b\n"
        result = parse_diff_to_json(diff, "f.py", CATPPUCCIN_MOCHA)
        by_text = {line["text"]: line["index"] for h in result["hunks"] for line in h["lines"]}
        assert by_text == {"-old": 4, "+new": 5, "-a": 7, "+b": 8}


class TestHighlightFileToJson:
    def test_empty_content(self):
        result = highlight_file_to_json("", "", "f.py", CATPPUCCIN_MOCHA)
        assert result["lines"] == []

    def test_basic_file(self):
        content = "line one\nline two\nline three\n"
        result = highlight_file_to_json(content, "", "f.txt", CATPPUCCIN_MOCHA)
        assert len(result["lines"]) == 3
        assert result["lines"][0]["num"] == 1
        assert result["lines"][2]["num"] == 3
        assert all(line["type"] == "context" for line in result["lines"])

    def test_with_diff_marks_added_lines(self):
        content = "old line\nnew line\n"
        diff = "diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1 +1,2 @@\n old line\n+new line\n"
        result = highlight_file_to_json(content, diff, "f.txt", CATPPUCCIN_MOCHA)
        assert result["lines"][1]["type"] == "add"
