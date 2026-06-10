from __future__ import annotations

import json
from pathlib import Path

import pytest

from diffui.git_utils import (
    _load_json,
    _safe_name,
    _save_json,
    diff_stat,
    short_name,
)


class TestShortName:
    def test_simple_path(self):
        assert short_name("src/main.py") == "main.py"

    def test_deep_path(self):
        assert short_name("a/b/c/d/file.tf") == "file.tf"

    def test_no_slash(self):
        assert short_name("file.py") == "file.py"

    def test_trailing_slash(self):
        assert short_name("dir/") == ""


class TestSafeName:
    def test_forward_slashes(self):
        assert _safe_name("feature/branch") == "feature_branch"

    def test_backslashes(self):
        assert _safe_name("a\\b") == "a_b"

    def test_colons(self):
        assert _safe_name("C:/path") == "C__path"

    def test_no_special_chars(self):
        assert _safe_name("simple") == "simple"


class TestLoadSaveJson:
    def test_load_missing_file(self, tmp_path: Path):
        result = _load_json(tmp_path / "missing.json", {})
        assert result == {}

    def test_load_missing_with_default(self, tmp_path: Path):
        result = _load_json(tmp_path / "missing.json", [])
        assert result == []

    def test_load_missing_no_default(self, tmp_path: Path):
        result = _load_json(tmp_path / "missing.json")
        assert result == {}

    def test_save_and_load(self, tmp_path: Path):
        p = tmp_path / "data.json"
        data = {"key": "value", "num": 42}
        _save_json(p, data)
        loaded = _load_json(p, {})
        assert loaded == data

    def test_save_creates_file(self, tmp_path: Path):
        p = tmp_path / "new.json"
        assert not p.exists()
        _save_json(p, {"a": 1})
        assert p.exists()

    def test_save_format(self, tmp_path: Path):
        p = tmp_path / "fmt.json"
        _save_json(p, {"x": 1})
        content = p.read_text()
        assert content.endswith("\n")
        parsed = json.loads(content)
        assert parsed == {"x": 1}

    def test_roundtrip_reviewed(self, tmp_path: Path):
        p = tmp_path / "reviewed.json"
        data: dict[str, float] = {"file.py": 1234567890.123}
        _save_json(p, data)
        loaded = _load_json(p, {})
        assert loaded["file.py"] == pytest.approx(1234567890.123)

    def test_roundtrip_comments(self, tmp_path: Path):
        p = tmp_path / "comments.json"
        data = {
            "file.py": [
                {
                    "file_path": "file.py",
                    "file_line_num": 10,
                    "line_text": "+new code",
                    "comment": "looks good",
                    "timestamp": "2024-01-01T00:00:00Z",
                }
            ]
        }
        _save_json(p, data)
        loaded = _load_json(p, {})
        assert loaded["file.py"][0]["comment"] == "looks good"
        assert loaded["file.py"][0]["file_line_num"] == 10


class TestDiffStat:
    def test_simple_diff(self):
        diff = (
            "diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1,3 +1,4 @@\n line1\n-line2\n+line2_new\n+line2_extra\n line3\n"
        )
        adds, dels = diff_stat(diff)
        assert adds == 2
        assert dels == 1

    def test_no_changes(self):
        adds, dels = diff_stat("")
        assert adds == 0
        assert dels == 0

    def test_only_adds(self):
        diff = "@@ -1 +1,3 @@\n+a\n+b\n+c\n"
        adds, dels = diff_stat(diff)
        assert adds == 3
        assert dels == 0

    def test_only_deletes(self):
        diff = "@@ -1,3 +1 @@\n-a\n-b\n-c\n"
        adds, dels = diff_stat(diff)
        assert adds == 0
        assert dels == 3

    def test_ignores_meta_lines(self):
        diff = "--- a/file\n+++ b/file\n@@ -1 +1 @@\n-old\n+new\n"
        adds, dels = diff_stat(diff)
        assert adds == 1
        assert dels == 1


class TestResolveRepos:
    def test_from_current_dir(self):
        from diffui.git_utils import resolve_repos

        repos, idx = resolve_repos()
        assert len(repos) >= 1
        assert 0 <= idx < len(repos)

    def test_explicit_paths(self):
        from diffui.git_utils import resolve_repos

        repo_path = str(Path(__file__).parent.parent)
        repos, idx = resolve_repos([repo_path])
        assert len(repos) == 1
        assert idx == 0
        assert repos[0].name == "diffui"

    def test_deduplicates(self):
        from diffui.git_utils import resolve_repos

        repo_path = str(Path(__file__).parent.parent)
        repos, _idx = resolve_repos([repo_path, repo_path])
        assert len(repos) == 1


class TestGetBlame:
    def test_returns_list_of_dicts(self):
        from diffui.git_utils import get_blame, set_active_repo

        root = Path(__file__).parent.parent
        set_active_repo(root)
        result = get_blame("diffui/__init__.py")
        assert isinstance(result, list)
        if result:
            assert "sha" in result[0]
            assert "author" in result[0]
            assert "timestamp" in result[0]

    def test_sha_is_8_chars(self):
        from diffui.git_utils import get_blame, set_active_repo

        root = Path(__file__).parent.parent
        set_active_repo(root)
        result = get_blame("diffui/__init__.py")
        for entry in result:
            assert len(entry["sha"]) == 8

    def test_unknown_file_returns_empty(self):
        from diffui.git_utils import get_blame, set_active_repo

        root = Path(__file__).parent.parent
        set_active_repo(root)
        assert get_blame("does_not_exist.py") == []


class TestSessionPersistence:
    def test_save_overwrites_not_merges(self, tmp_path: Path):
        from diffui.git_utils import _load_json, _save_json

        p = tmp_path / "session.json"
        _save_json(p, {"a": 1})
        _save_json(p, {"b": 2})
        assert _load_json(p, {}) == {"b": 2}


class TestGetDiffNumstat:
    def test_returns_dict(self):
        from diffui.git_utils import get_diff_numstat, get_merge_base, set_active_repo

        root = Path(__file__).parent.parent
        set_active_repo(root)
        try:
            from diffui.git_utils import get_main_branch

            main = get_main_branch()
            base = get_merge_base(main)
            stats = get_diff_numstat(base)
            assert isinstance(stats, dict)
            for path, (adds, dels) in stats.items():
                assert isinstance(path, str)
                assert isinstance(adds, int)
                assert isinstance(dels, int)
        except RuntimeError:
            pytest.skip("No merge base available")
