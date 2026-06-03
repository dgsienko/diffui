from __future__ import annotations

import functools
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_active_repo_root: Path | None = None


def set_active_repo(path: Path) -> None:
    global _active_repo_root
    _active_repo_root = path
    get_repo_root.cache_clear()
    _cached_current_branch.cache_clear()


def discover_sibling_repos(current_root: Path) -> list[Path]:
    parent = current_root.parent
    repos = []
    for child in sorted(parent.iterdir()):
        if child.is_dir() and (child / ".git").exists():
            repos.append(child)
    return repos


def resolve_repo_root(path: str | Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Not a git repository: {path}")
    return Path(result.stdout.strip())


def resolve_repos(paths: list[str] | None = None) -> tuple[list[Path], int]:
    if paths:
        seen: set[Path] = set()
        repos: list[Path] = []
        for p in paths:
            root = resolve_repo_root(Path(p).expanduser().resolve())
            if root not in seen:
                seen.add(root)
                repos.append(root)
        return repos, 0
    current = resolve_repo_root(Path.cwd())
    siblings = discover_sibling_repos(current)
    repos = siblings if len(siblings) > 1 else [current]
    return repos, repos.index(current)


def _git_at(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True)


@functools.lru_cache(maxsize=32)
def _detect_main_branch(repo_root: Path) -> str:
    for candidate in ("main", "master"):
        if _git_at(repo_root, "rev-parse", "--verify", f"refs/heads/{candidate}").returncode == 0:
            return candidate
    result = _git_at(repo_root, "rev-parse", "--abbrev-ref", "origin/HEAD")
    if result.returncode == 0:
        branch = result.stdout.strip().replace("origin/", "")
        if branch and branch != "HEAD":
            return branch
    return "main"


def repo_has_changes(repo_root: Path) -> bool:
    main = _detect_main_branch(repo_root)
    base = _git_at(repo_root, "merge-base", main, "HEAD")
    if base.returncode != 0:
        return False
    return _git_at(repo_root, "diff", "--quiet", base.stdout.strip()).returncode != 0


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    cmd = ["git"]
    if _active_repo_root:
        cmd.extend(["-C", str(_active_repo_root)])
    cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def get_git_dir() -> Path:
    result = _git("rev-parse", "--git-dir")
    if result.returncode != 0:
        return get_repo_root() / ".git"
    git_dir = result.stdout.strip()
    return Path(git_dir) if Path(git_dir).is_absolute() else get_repo_root() / git_dir


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    return json.loads(path.read_text())


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


@dataclass
class Commit:
    sha: str
    message: str
    author: str
    files: list[str] = field(default_factory=list)


@functools.lru_cache(maxsize=1)
def get_repo_root() -> Path:
    if _active_repo_root is not None:
        return _active_repo_root
    result = _git("rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise RuntimeError("Not in a git repository")
    return Path(result.stdout.strip())


def get_main_branch() -> str:
    return _detect_main_branch(get_repo_root())


def get_merge_base(main_branch: str) -> str:
    result = _git("merge-base", main_branch, "HEAD")
    if result.returncode != 0:
        raise RuntimeError(f"Could not find merge base with {main_branch}")
    return result.stdout.strip()


def get_branch_commits(merge_base: str) -> list[Commit]:
    result = _git("log", f"{merge_base}..HEAD", "--format=%H\t%s\t%an", "--reverse")
    if result.returncode != 0:
        return []

    commits = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        sha, message, author = parts
        files_result = _git("diff-tree", "--no-commit-id", "-r", "--name-only", sha)
        files = [f for f in files_result.stdout.strip().splitlines() if f]
        commits.append(Commit(sha=sha, message=message, author=author, files=files))

    return commits


def get_full_diff(merge_base: str, path: str, context: int = 3) -> str:
    result = _git("diff", f"-U{context}", merge_base, "--", path).stdout
    if result.strip():
        return result
    return _diff_untracked(path)


def get_working_diff(path: str, context: int = 3) -> str:
    staged = _git("diff", f"-U{context}", "--cached", "--", path).stdout
    unstaged = _git("diff", f"-U{context}", "--", path).stdout
    parts = []
    if staged.strip():
        parts.append(staged)
    if unstaged.strip():
        parts.append(unstaged)
    if parts:
        return "".join(parts)
    return _diff_untracked(path)


def _diff_untracked(path: str) -> str:
    full_path = get_repo_root() / path
    if not full_path.exists():
        return ""
    try:
        content = full_path.read_text()
    except (OSError, UnicodeDecodeError):
        return ""
    if not content:
        return ""
    lines = content.splitlines()
    header = (
        f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n"
    )
    body = "\n".join(f"+{line}" for line in lines) + "\n"
    return header + body


def get_commit_diff(commit_sha: str, path: str, context: int = 3) -> str:
    result = _git("diff", f"-U{context}", f"{commit_sha}~1", commit_sha, "--", path)
    if result.returncode != 0:
        empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        return _git("diff", f"-U{context}", empty_tree, commit_sha, "--", path).stdout
    return result.stdout


def get_changed_files(merge_base: str) -> list[str]:
    result = _git("diff", "--name-only", merge_base)
    return [f for f in result.stdout.strip().splitlines() if f]


def get_diff_numstat(merge_base: str) -> dict[str, tuple[int, int]]:
    result = _git("diff", "--numstat", merge_base)
    stats: dict[str, tuple[int, int]] = {}
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            adds = int(parts[0]) if parts[0] != "-" else 0
            dels = int(parts[1]) if parts[1] != "-" else 0
            stats[parts[2]] = (adds, dels)
    return stats


def get_working_changed_files() -> list[str]:
    unstaged = _git("diff", "--name-only", "HEAD").stdout
    staged = _git("diff", "--name-only", "--cached").stdout
    untracked = _git("ls-files", "--others", "--exclude-standard").stdout
    files = set()
    for output in (unstaged, staged, untracked):
        for f in output.strip().splitlines():
            if f:
                files.add(f)
    return sorted(files)


def get_file_mtime(path: str) -> float:
    try:
        return (get_repo_root() / path).stat().st_mtime
    except FileNotFoundError:
        return 0.0


def get_file_content(path: str) -> str:
    full_path = get_repo_root() / path
    try:
        return full_path.read_text()
    except (OSError, UnicodeDecodeError):
        return ""


def get_blame(path: str) -> list[dict]:
    result = _git("blame", "--porcelain", "--", path)
    if result.returncode != 0:
        return []
    lines: list[dict] = []
    authors: dict[str, str] = {}
    timestamps: dict[str, int] = {}
    current_sha = ""
    for raw_line in result.stdout.splitlines():
        if raw_line[0] not in ("\t", " ") and len(raw_line) >= 40 and " " in raw_line:
            parts = raw_line.split()
            if len(parts[0]) == 40:
                current_sha = parts[0]
        elif raw_line.startswith("author "):
            authors[current_sha] = raw_line[7:]
        elif raw_line.startswith("author-time "):
            try:
                timestamps[current_sha] = int(raw_line[12:])
            except ValueError:
                pass
        elif raw_line.startswith("\t"):
            lines.append(
                {
                    "sha": current_sha[:8],
                    "author": authors.get(current_sha, ""),
                    "timestamp": timestamps.get(current_sha, 0),
                }
            )
    return lines


def get_remote_url() -> str:
    result = _git("remote", "get-url", "origin")
    return result.stdout.strip() if result.returncode == 0 else ""


def get_head_sha() -> str:
    result = _git("rev-parse", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else ""


def get_git_user_name() -> str:
    result = _git("config", "user.name")
    name = result.stdout.strip()
    return name if name else "User"


def short_name(path: str) -> str:
    return path.split("/")[-1]


def current_branch() -> str:
    return _cached_current_branch()


def diff_stat(diff_text: str) -> tuple[int, int]:
    adds = 0
    dels = 0
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            adds += 1
        elif line.startswith("-") and not line.startswith("---"):
            dels += 1
    return adds, dels


# --- State persistence ---

_CONFIG_ROOT = Path.home() / ".config" / "diffui"


@functools.lru_cache(maxsize=1)
def _cached_current_branch() -> str:
    result = _git("rev-parse", "--abbrev-ref", "HEAD")
    return result.stdout.strip() or "HEAD"


def clear_branch_cache() -> None:
    _cached_current_branch.cache_clear()


def _safe_name(s: str) -> str:
    return s.replace("/", "_").replace("\\", "_").replace(":", "_")


def _repo_dir() -> Path:
    repo_key = _safe_name(str(get_repo_root()))
    d = _CONFIG_ROOT / repo_key
    d.mkdir(parents=True, exist_ok=True)
    return d


def _branch_dir() -> Path:
    d = _repo_dir() / _safe_name(_cached_current_branch())
    d.mkdir(exist_ok=True)
    return d


def _reviewed_path() -> Path:
    return _branch_dir() / "reviewed.json"


def _comments_path() -> Path:
    return _branch_dir() / "comments.json"


def _session_path() -> Path:
    return _branch_dir() / "session.json"


def load_session() -> dict[str, Any]:
    return _load_json(_session_path(), {})


def save_session(session: dict[str, Any]) -> None:
    _save_json(_session_path(), session)


def load_reviewed() -> dict[str, float]:
    return _load_json(_reviewed_path(), {})


def save_reviewed(reviewed: dict[str, float]) -> None:
    _save_json(_reviewed_path(), reviewed)


def load_comments() -> dict[str, list[dict]]:
    return _load_json(_comments_path(), {})


def save_comments(comments: dict[str, list[dict]]) -> None:
    _save_json(_comments_path(), comments)


def _settings_path() -> Path:
    _CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
    return _CONFIG_ROOT / "settings.json"


def load_settings() -> dict[str, Any]:
    return _load_json(_settings_path(), {})


def save_settings(settings: dict[str, Any]) -> None:
    _save_json(_settings_path(), settings)
