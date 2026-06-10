from __future__ import annotations

from diffui.diff import get_lexer
from diffui.server.highlight import (
    _apply_word_highlights,
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


class TestApplyWordHighlights:
    def test_no_ranges_returns_unchanged(self):
        html = '<span style="color:red">hello</span>'
        assert _apply_word_highlights(html, [], "hello") == html

    def test_marks_plain_text(self):
        result = _apply_word_highlights("hello world", [(0, 5)], "hello world")
        assert "<mark>" in result
        assert "</mark>" in result
        assert "hello" in result

    def test_marks_inside_span(self):
        html = '<span style="color:red">abc</span>'
        result = _apply_word_highlights(html, [(0, 3)], "abc")
        assert "<mark>" in result

    def test_handles_html_entities(self):
        html = "&lt;div&gt;"
        result = _apply_word_highlights(html, [(0, 5)], "<div>")
        assert "<mark>" in result

    def test_malformed_tag_no_crash(self):
        result = _apply_word_highlights("<unclosed", [], "x")
        assert isinstance(result, str)

    def test_malformed_entity_no_crash(self):
        result = _apply_word_highlights("&notsemicolon", [(0, 1)], "&")
        assert isinstance(result, str)


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
        assert result["adds"] == 2
        assert result["dels"] == 0
        assert len(result["hunks"]) > 0
        lines = result["hunks"][-1]["lines"]
        add_lines = [line for line in lines if line["type"] == "add"]
        assert len(add_lines) == 2
        assert all("html" in line for line in add_lines)

    def test_line_numbers_present(self):
        diff = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n@@ -1,2 +1,2 @@\n-old\n+new\n ctx\n"
        result = parse_diff_to_json(diff, "f.py", CATPPUCCIN_MOCHA)
        lines = result["hunks"][-1]["lines"]
        remove_line = next(line for line in lines if line["type"] == "remove")
        add_line = next(line for line in lines if line["type"] == "add")
        assert remove_line["old_num"] is not None
        assert add_line["new_num"] is not None

    def test_each_line_has_index(self):
        diff = "diff --git a/f.py b/f.py\n--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new\n"
        result = parse_diff_to_json(diff, "f.py", CATPPUCCIN_MOCHA)
        for hunk in result["hunks"]:
            for line in hunk["lines"]:
                assert "index" in line
                assert isinstance(line["index"], int)


class TestHighlightFileToJson:
    def test_empty_content(self):
        from diffui.server.highlight import highlight_file_to_json

        result = highlight_file_to_json("", "", "f.py", CATPPUCCIN_MOCHA)
        assert result["lines"] == []
        assert result["total_lines"] == 0

    def test_basic_file(self):
        from diffui.server.highlight import highlight_file_to_json

        content = "line one\nline two\nline three\n"
        result = highlight_file_to_json(content, "", "f.txt", CATPPUCCIN_MOCHA)
        assert result["total_lines"] == 3
        assert len(result["lines"]) == 3
        assert result["lines"][0]["num"] == 1
        assert result["lines"][2]["num"] == 3
        assert all(line["type"] == "context" for line in result["lines"])

    def test_with_diff_marks_added_lines(self):
        from diffui.server.highlight import highlight_file_to_json

        content = "old line\nnew line\n"
        diff = "diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1 +1,2 @@\n old line\n+new line\n"
        result = highlight_file_to_json(content, diff, "f.txt", CATPPUCCIN_MOCHA)
        assert result["lines"][1]["type"] == "add"
        assert result["adds"] == 1
