from __future__ import annotations

import pytest
from pygments.token import Token

from diffui.diff import (
    classify_line,
    file_change_note,
    get_lexer,
    is_meta_line,
    pair_diff_lines,
    parse_line_numbers,
    resolve_line_num,
    split_into_hunks,
    strip_diff_prefix,
    token_color,
    word_diff_ranges,
)


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ("+new line", "add"),
        ("-old line", "remove"),
        (" unchanged", "context"),
        ("@@ -1,3 +1,5 @@", "hunk"),
        ("diff --git a/file b/file", "meta"),
        ("index abc123..def456 100644", "meta"),
        ("+++ b/file.py", "meta"),
        ("--- a/file.py", "meta"),
        ("", "context"),
    ],
)
def test_classify_line(line, kind):
    assert classify_line(line) == kind


@pytest.mark.parametrize(
    ("line", "meta"),
    [
        ("diff --git a/f b/f", True),
        ("index abc..def", True),
        ("+++ b/file", True),
        ("--- a/file", True),
        ("+some code", False),
        (" context line", False),
    ],
)
def test_is_meta_line(line, meta):
    assert is_meta_line(line) is meta


@pytest.mark.parametrize(
    ("line", "text"),
    [
        ("+new line", "new line"),
        ("-old line", "old line"),
        (" unchanged", "unchanged"),
        ("no prefix", "no prefix"),
        ("", ""),
    ],
)
def test_strip_diff_prefix(line, text):
    assert strip_diff_prefix(line) == text


@pytest.mark.parametrize(("old", "new", "expected"), [("10", "20", 20), ("10", "", 10), ("", "5", 5), ("", "", None)])
def test_resolve_line_num_prefers_the_new_side(old, new, expected):
    assert resolve_line_num(old, new) == expected


class TestParseLineNumbers:
    def test_simple_diff(self):
        diff = (
            "diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1,3 +1,4 @@\n line1\n-line2\n+line2_new\n+line2_extra\n line3\n"
        )
        nums = parse_line_numbers(diff)
        assert nums[0] == (None, None)  # diff
        assert nums[1] == (None, None)  # ---
        assert nums[2] == (None, None)  # +++
        assert nums[3] == (None, None)  # @@
        assert nums[4] == ("1", "1")  # context
        assert nums[5] == ("2", None)  # remove
        assert nums[6] == (None, "2")  # add
        assert nums[7] == (None, "3")  # add
        assert nums[8] == ("3", "4")  # context

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
    def test_unknown_extension_falls_back_to_text(self):
        lexer = get_lexer("file.xyz_unknown")
        assert "text" in lexer.name.lower()


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


@pytest.mark.parametrize(
    ("old", "new", "ranges"),
    [
        ("hello world", "hello earth", ([(6, 11)], [(6, 11)])),
        ("same text", "same text", ([], [])),
        ("old", "new", ([(0, 3)], [(0, 3)])),
        ("a c", "a b c", ([], [(2, 3)])),
        ("a b c", "a c", ([(2, 3)], [])),
    ],
)
def test_word_diff_ranges(old, new, ranges):
    assert word_diff_ranges(old, new) == ranges


@pytest.mark.parametrize(
    ("lines", "paired"),
    [
        pytest.param(["@@ -1,2 +1,2 @@", "-old line", "+new line"], {1: [(0, 3)], 2: [(0, 3)]}, id="remove-and-add"),
        pytest.param(["@@ -1 +1,2 @@", " context", "+added"], {}, id="no-removal-to-pair-with"),
        pytest.param(
            ["-old1", "-old2", "+new1", "+new2"],
            {0: [(0, 4)], 1: [(0, 4)], 2: [(0, 4)], 3: [(0, 4)]},
            id="pairs-in-order",
        ),
        pytest.param(
            ["-removed1", "-removed2", "+added1"], {0: [(0, 8)], 2: [(0, 6)]}, id="surplus-removal-stays-plain"
        ),
        pytest.param(
            ["@@ -1 +1 @@", "--- old comment", "+-- new comment"], {1: [(3, 6)], 2: [(3, 6)]}, id="removed-dash-comment"
        ),
        pytest.param(["@@ -1 +1 @@", "-i", "+++i"], {1: [(0, 1)], 2: [(0, 3)]}, id="added-line-starting-with-plusses"),
        pytest.param(
            ["--- a/f.lua", "+++ b/f.lua", "@@ -1 +1 @@", "-old", "+new"],
            {3: [(0, 3)], 4: [(0, 3)]},
            id="file-headers-stay-plain",
        ),
    ],
)
def test_pair_diff_lines(lines, paired):
    assert pair_diff_lines(lines) == paired


class TestYamlSeparatorLines:
    def test_removed_separator_is_not_meta(self):
        assert not is_meta_line("----")
        assert classify_line("----") == "remove"

    def test_added_line_starting_with_plusses_is_not_meta(self):
        assert not is_meta_line("+++i")
        assert classify_line("+++i") == "add"

    def test_dev_null_header_is_meta(self):
        assert is_meta_line("--- /dev/null")
        assert is_meta_line("+++ /dev/null")

    def test_line_numbers_survive_a_removed_separator(self):
        diff = (
            "diff --git a/k8s.yaml b/k8s.yaml\n"
            "--- a/k8s.yaml\n"
            "+++ b/k8s.yaml\n"
            "@@ -1,5 +1,5 @@\n"
            " apiVersion: v1\n"
            "----\n"
            "-kind: Service\n"
            "+kind: Deployment\n"
            " metadata:\n"
        )
        nums = parse_line_numbers(diff)
        assert nums[5] == ("2", None)
        assert nums[6] == ("3", None)
        assert nums[8] == ("4", "3")


class TestFileChangeNote:
    @pytest.mark.parametrize(
        ("header", "note"),
        [
            (["diff --git a/f.py b/f.py", "index 1..2 100644", "--- a/f.py", "+++ b/f.py"], ""),
            (["diff --git a/f.py b/f.py", "new file mode 100644", "--- /dev/null", "+++ b/f.py"], "New file"),
            (["diff --git a/f.py b/f.py", "deleted file mode 100644", "--- a/f.py", "+++ /dev/null"], "Deleted file"),
            (["diff --git a/f.py b/f.py", "old mode 100644", "new mode 100755"], "Mode 100644 → 100755"),
            (["diff --git a/f.py b/f.py", "Binary files a/f.py and b/f.py differ"], "Binary file"),
            (
                ["diff --git a/old.py b/new.py", "similarity index 100%", "rename from old.py", "rename to new.py"],
                "Renamed from old.py",
            ),
            (
                ["diff --git a/old.py b/new.py", "similarity index 92%", "rename from old.py", "rename to new.py"],
                "Renamed from old.py (92% similar)",
            ),
        ],
    )
    def test_note(self, header, note):
        assert file_change_note(header) == note
