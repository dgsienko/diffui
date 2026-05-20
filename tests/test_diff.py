from __future__ import annotations

from pygments.token import Token

from diffui.diff import (
    _is_meta_line,
    classify_line,
    get_lexer,
    highlight_line,
    pair_diff_lines,
    parse_line_numbers,
    resolve_line_num,
    split_into_hunks,
    strip_diff_prefix,
    token_color,
    word_diff_ranges,
)


class TestClassifyLine:
    def test_add(self):
        assert classify_line("+new line") == "add"

    def test_remove(self):
        assert classify_line("-old line") == "remove"

    def test_context(self):
        assert classify_line(" unchanged") == "context"

    def test_hunk(self):
        assert classify_line("@@ -1,3 +1,5 @@") == "hunk"

    def test_meta_diff(self):
        assert classify_line("diff --git a/file b/file") == "meta"

    def test_meta_index(self):
        assert classify_line("index abc123..def456 100644") == "meta"

    def test_meta_plus(self):
        assert classify_line("+++ b/file.py") == "meta"

    def test_meta_minus(self):
        assert classify_line("--- a/file.py") == "meta"

    def test_empty_line(self):
        assert classify_line("") == "context"


class TestIsMetaLine:
    def test_diff_header(self):
        assert _is_meta_line("diff --git a/f b/f")

    def test_index_line(self):
        assert _is_meta_line("index abc..def")

    def test_plus_header(self):
        assert _is_meta_line("+++ b/file")

    def test_minus_header(self):
        assert _is_meta_line("--- a/file")

    def test_regular_add(self):
        assert not _is_meta_line("+some code")

    def test_context(self):
        assert not _is_meta_line(" context line")


class TestStripDiffPrefix:
    def test_add(self):
        assert strip_diff_prefix("+new line") == "new line"

    def test_remove(self):
        assert strip_diff_prefix("-old line") == "old line"

    def test_context(self):
        assert strip_diff_prefix(" unchanged") == "unchanged"

    def test_no_prefix(self):
        assert strip_diff_prefix("no prefix") == "no prefix"

    def test_empty(self):
        assert strip_diff_prefix("") == ""


class TestResolveLineNum:
    def test_prefers_new(self):
        assert resolve_line_num("10", "20") == 20

    def test_falls_back_to_old(self):
        assert resolve_line_num("10", "") == 10

    def test_returns_none_when_both_empty(self):
        assert resolve_line_num("", "") is None

    def test_new_only(self):
        assert resolve_line_num("", "5") == 5


class TestParseLineNumbers:
    def test_simple_diff(self):
        diff = (
            "diff --git a/f b/f\n"
            "--- a/f\n"
            "+++ b/f\n"
            "@@ -1,3 +1,4 @@\n"
            " line1\n"
            "-line2\n"
            "+line2_new\n"
            "+line2_extra\n"
            " line3\n"
        )
        nums = parse_line_numbers(diff)
        assert nums[0] == (None, None)  # diff
        assert nums[1] == (None, None)  # ---
        assert nums[2] == (None, None)  # +++
        assert nums[3] == (None, None)  # @@
        assert nums[4] == ("1", "1")    # context
        assert nums[5] == ("2", None)   # remove
        assert nums[6] == (None, "2")   # add
        assert nums[7] == (None, "3")   # add
        assert nums[8] == ("3", "4")    # context

    def test_empty(self):
        assert parse_line_numbers("") == []


class TestSplitIntoHunks:
    def test_single_hunk(self):
        lines = [
            "diff --git a/f b/f",
            "--- a/f",
            "+++ b/f",
            "@@ -1,3 +1,3 @@",
            " line1",
            "-line2",
            "+line2new",
        ]
        hunks = split_into_hunks(lines)
        assert len(hunks) == 2
        assert hunks[0][0] == "File header"
        assert hunks[1][0] == "@@ -1,3 +1,3 @@"
        assert len(hunks[1][1]) == 4  # hunk header + 3 lines

    def test_multiple_hunks(self):
        lines = [
            "@@ -1,2 +1,2 @@",
            " a",
            "-b",
            "+c",
            "@@ -10,2 +10,2 @@",
            " x",
            "-y",
            "+z",
        ]
        hunks = split_into_hunks(lines)
        assert len(hunks) == 2
        assert hunks[0][0].startswith("@@ -1")
        assert hunks[1][0].startswith("@@ -10")

    def test_empty(self):
        assert split_into_hunks([]) == []

    def test_only_header(self):
        lines = ["diff --git a/f b/f", "--- a/f", "+++ b/f"]
        hunks = split_into_hunks(lines)
        assert len(hunks) == 1
        assert hunks[0][0] == "File header"


class TestGetLexer:
    def test_python_file(self):
        lexer = get_lexer("test.py")
        assert "python" in lexer.name.lower()

    def test_unknown_extension(self):
        lexer = get_lexer("file.xyz_unknown")
        assert lexer is not None  # falls back to TextLexer

    def test_terraform(self):
        lexer = get_lexer("main.tf")
        assert lexer is not None


class TestTokenColor:
    def test_direct_match(self):
        style_map = {Token.Keyword: "#ff0000"}
        assert token_color(Token.Keyword, style_map) == "#ff0000"

    def test_parent_fallback(self):
        style_map = {Token.Keyword: "#ff0000"}
        assert token_color(Token.Keyword.Constant, style_map) == "#ff0000"

    def test_no_match(self):
        style_map = {Token.Keyword: "#ff0000"}
        assert token_color(Token.Name, style_map) is None


class TestHighlightLine:
    def test_returns_text(self):
        lexer = get_lexer("test.py")
        result = highlight_line("x = 1", lexer, {})
        assert result.plain == "x = 1"

    def test_strips_trailing_newline(self):
        lexer = get_lexer("test.py")
        result = highlight_line("x = 1\n", lexer, {})
        assert not result.plain.endswith("\n")


class TestWordDiffRanges:
    def test_single_word_change(self):
        old_ranges, new_ranges = word_diff_ranges("hello world", "hello earth")
        assert len(old_ranges) == 1
        assert len(new_ranges) == 1

    def test_identical_lines(self):
        old_ranges, new_ranges = word_diff_ranges("same text", "same text")
        assert old_ranges == []
        assert new_ranges == []

    def test_complete_replacement(self):
        old_ranges, new_ranges = word_diff_ranges("old", "new")
        assert len(old_ranges) == 1
        assert len(new_ranges) == 1

    def test_insertion(self):
        old_ranges, new_ranges = word_diff_ranges("a c", "a b c")
        assert old_ranges == []
        assert len(new_ranges) == 1

    def test_deletion(self):
        old_ranges, new_ranges = word_diff_ranges("a b c", "a c")
        assert len(old_ranges) == 1
        assert new_ranges == []

    def test_empty_lines(self):
        old_ranges, new_ranges = word_diff_ranges("", "")
        assert old_ranges == []
        assert new_ranges == []


class TestPairDiffLines:
    def test_paired_add_remove(self):
        lines = [
            "@@ -1,2 +1,2 @@",
            "-old line",
            "+new line",
        ]
        result = pair_diff_lines(lines)
        assert 1 in result  # remove line index
        assert 2 in result  # add line index

    def test_no_pairs(self):
        lines = [
            "@@ -1 +1,2 @@",
            " context",
            "+added",
        ]
        result = pair_diff_lines(lines)
        assert result == {}

    def test_multiple_pairs(self):
        lines = [
            "-old1",
            "-old2",
            "+new1",
            "+new2",
        ]
        result = pair_diff_lines(lines)
        assert 0 in result or 1 in result

    def test_unmatched_removes(self):
        lines = [
            "-removed1",
            "-removed2",
            "+added1",
        ]
        result = pair_diff_lines(lines)
        assert 0 in result
        assert 2 in result
