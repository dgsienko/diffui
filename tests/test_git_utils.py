from __future__ import annotations

from pathlib import Path

import pytest

from diffui.git_utils import (
    PathOutsideRepo,
    _load_json,
    _safe_name,
    _save_json,
    diff_stat,
    discover_sibling_repos,
    get_changed_files,
    get_diff_numstat,
    get_file_content,
    get_file_mtime,
    get_merge_base,
    repo_has_changes,
    repo_relative,
    resolve_repos,
    set_active_repo,
    short_name,
)
from tests.conftest import _git


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
    @pytest.mark.parametrize(("args", "expected"), [((), {}), (({},), {}), (([],), [])])
    def test_load_missing_file_returns_the_default(self, tmp_path: Path, args, expected):
        assert _load_json(tmp_path / "missing.json", *args) == expected

    def test_save_and_load(self, tmp_path: Path):
        p = tmp_path / "data.json"
        data = {"key": "value", "num": 42}
        _save_json(p, data)
        loaded = _load_json(p, {})
        assert loaded == data


@pytest.mark.parametrize(
    ("diff", "expected"),
    [
        pytest.param(
            "diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1,3 +1,4 @@\n line1\n-line2\n+line2_new\n+line2_extra\n line3\n",
            (2, 1),
            id="mixed",
        ),
        pytest.param("", (0, 0), id="empty"),
        pytest.param("--- a/file\n+++ b/file\n@@ -1 +1 @@\n-old\n+new\n", (1, 1), id="file-headers-are-not-counted"),
        pytest.param(
            "diff --git a/k8s.yaml b/k8s.yaml\n--- a/k8s.yaml\n+++ b/k8s.yaml\n@@ -1,3 +1,2 @@\n----\n-kind: Service\n+kind: Deployment\n",
            (1, 2),
            id="removed-yaml-separator-is-a-deletion",
        ),
    ],
)
def test_diff_stat(diff, expected):
    assert diff_stat(diff) == expected


class TestResolveRepos:
    @pytest.mark.parametrize("copies", [1, 2])
    def test_explicit_paths_resolve_once(self, temp_repo, copies):
        assert resolve_repos([str(temp_repo)] * copies) == ([temp_repo.resolve()], 0)


class TestDiscoverSiblingRepos:
    def test_no_git_dirs_returns_empty(self, tmp_path: Path):

        (tmp_path / "parent").mkdir()
        child = tmp_path / "parent" / "child"
        child.mkdir()
        assert discover_sibling_repos(child) == []

    def test_finds_sibling_git_repos(self, tmp_path: Path):

        parent = tmp_path / "workspace"
        parent.mkdir()
        for name in ("repo_a", "repo_b"):
            repo = parent / name
            repo.mkdir()
            (repo / ".git").mkdir()
        plain = parent / "not_a_repo"
        plain.mkdir()

        current = parent / "repo_a"
        result = discover_sibling_repos(current)
        assert sorted(p.name for p in result) == ["repo_a", "repo_b"]


class TestRepoHasChanges:
    def test_branch_with_commits_has_changes(self, temp_repo):

        assert repo_has_changes(temp_repo) is True

    def test_untracked_file_alone_counts(self, tmp_path):

        repo = tmp_path / "untracked-only"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "commit", "-qm", "init", "--allow-empty")
        assert repo_has_changes(repo) is False
        (repo / "brand_new.py").write_text("x = 1\n")
        assert repo_has_changes(repo) is True


class TestMergeBase:
    def test_stale_local_main_does_not_count_merged_commits(self, tmp_path):

        repo = tmp_path / "stale-main"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "commit", "-qm", "init", "--allow-empty")
        (repo / "merged.py").write_text("x = 1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "merged on origin")
        _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        _git(repo, "reset", "-q", "--hard", "HEAD~1")
        _git(repo, "checkout", "-qb", "feature", "origin/main")
        (repo / "feature.py").write_text("y = 2\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "feature work")

        set_active_repo(repo)
        assert get_changed_files(get_merge_base("main")) == ["feature.py"]


class TestGetFileMtime:
    def test_missing_file_returns_zero(self, temp_repo):
        set_active_repo(temp_repo)
        assert get_file_mtime("_definitely_missing_file_.xyz") == 0.0

    def test_existing_file_returns_its_mtime(self, temp_repo):
        set_active_repo(temp_repo)
        assert get_file_mtime("app.py") == (temp_repo / "app.py").stat().st_mtime


class TestGetFileContent:
    def test_missing_file_returns_empty(self, temp_repo):
        set_active_repo(temp_repo)
        assert get_file_content("_definitely_missing_file_.xyz") == ""

    def test_binary_file_returns_empty(self, tmp_path: Path):

        set_active_repo(tmp_path)
        binary = tmp_path / "data.bin"
        binary.write_bytes(b"\xff\xfe\x00\x01\x80")
        assert get_file_content("data.bin") == ""

    def test_text_file_returns_content(self, tmp_path: Path):

        set_active_repo(tmp_path)
        (tmp_path / "hello.txt").write_text("hi there\n")
        assert get_file_content("hello.txt") == "hi there\n"


class TestGetDiffNumstat:
    def test_counts_committed_and_working_changes_but_not_untracked_files(self, temp_repo):
        set_active_repo(temp_repo)
        assert get_diff_numstat(get_merge_base("main")) == {"app.py": (3, 2), "extra.py": (1, 0)}


class TestRepoRelative:
    def test_in_repo_path_returned_unchanged(self, temp_repo):

        set_active_repo(temp_repo)
        assert repo_relative("app.py") == "app.py"

    def test_absolute_path_outside_repo_raises(self, temp_repo, tmp_path):

        set_active_repo(temp_repo)
        outside = tmp_path / "secret.txt"
        outside.write_text("secret\n")
        with pytest.raises(PathOutsideRepo):
            repo_relative(str(outside))

    def test_dotdot_escape_raises(self, temp_repo):

        set_active_repo(temp_repo)
        with pytest.raises(PathOutsideRepo):
            repo_relative("../../etc/hostname")

    def test_symlink_pointing_outside_raises(self, temp_repo, tmp_path):

        set_active_repo(temp_repo)
        outside = tmp_path / "target.txt"
        outside.write_text("secret\n")
        link = temp_repo / "link.txt"
        link.symlink_to(outside)
        try:
            with pytest.raises(PathOutsideRepo):
                repo_relative("link.txt")
        finally:
            link.unlink()

    def test_symlink_inside_repo_allowed(self, temp_repo):

        set_active_repo(temp_repo)
        link = temp_repo / "alias.py"
        link.symlink_to(temp_repo / "app.py")
        try:
            assert repo_relative("alias.py") == "alias.py"
        finally:
            link.unlink()


class TestJsonPersistence:
    def test_corrupt_file_is_moved_aside_and_default_returned(self, tmp_path):

        path = tmp_path / "comments.json"
        path.write_text('{"a": [{"id"')
        assert _load_json(path, {}) == {}
        assert not path.exists()
        assert (tmp_path / "comments.json.corrupt").read_text() == '{"a": [{"id"'

    def test_save_leaves_no_temp_file(self, tmp_path):

        path = tmp_path / "comments.json"
        _save_json(path, {"a.py": [{"id": "1"}]})
        assert _load_json(path, {}) == {"a.py": [{"id": "1"}]}
        assert list(p.name for p in tmp_path.iterdir()) == ["comments.json"]
