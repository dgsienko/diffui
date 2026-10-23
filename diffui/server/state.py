from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from diffui.git_utils import (
    Commit,
    clear_branch_cache,
    current_branch,
    get_branch_commits,
    get_changed_files,
    get_diff_numstat,
    get_main_branch,
    get_merge_base,
    get_repo_root,
    get_tree_numstat,
    get_working_changed_files,
    is_comment_open,
    load_comments,
    load_reviewed,
    load_settings,
    read_turn_tree,
    snapshot_worktree,
)
from diffui.themes import ALL_THEMES, DEFAULT_THEME

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LastTurn:
    """The tree an agent's latest turn started from, the worktree's tree now, and what differs between them."""

    base: str
    now: str
    stats: dict[str, tuple[int, int]]


class AppState:
    def __init__(self) -> None:
        self.repos: list[Path] = []
        self.active_repo_index: int = 0
        self.merge_base: str = ""
        self.commits: list[Commit] = []
        self.all_files: list[str] = []
        self.working_files: list[str] = []
        self.numstat: dict[str, tuple[int, int]] = {}
        self._last_turn: LastTurn | None = None
        self._last_turn_stale = True
        self.reviewed: dict[str, float] = {}
        self.comments: dict[str, list[dict]] = {}
        self.branch_name: str = ""

        saved = load_settings()
        theme_name = saved.get("theme", DEFAULT_THEME.name)
        theme_index = next((i for i, t in enumerate(ALL_THEMES) if t.name == theme_name), 0)

        self.editor: str = saved.get("editor", "code")
        self.user_name: str = saved.get("user_name", "User")
        self.agent_cli: str = saved.get("agent_cli", "claude")
        self.font_size: int = saved.get("font_size", 13)
        self.word_wrap: bool = saved.get("word_wrap", False)
        self.keybindings: dict[str, str] = saved.get("keybindings", {})
        self.ignore_patterns: list[str] = []
        self.theme_index: int = theme_index

    def reload_repo_state(self) -> None:
        clear_branch_cache()
        self.branch_name = current_branch()
        main_branch = get_main_branch()
        self.merge_base = get_merge_base(main_branch)
        self.commits = get_branch_commits(self.merge_base)
        self.all_files = get_changed_files(self.merge_base)
        self.numstat = get_diff_numstat(self.merge_base)
        self.working_files = get_working_changed_files()
        self.reload_last_turn()
        self.reviewed = load_reviewed()
        self.comments = load_comments()
        self._load_ignore_patterns(get_repo_root())

    def reload_last_turn(self) -> None:
        self._last_turn_stale = True

    @property
    def last_turn(self) -> LastTurn | None:
        # Snapshotting runs `git add -A` over the worktree, so it waits until a client asks
        # for the last-turn view; file events while an agent writes only mark it stale.
        if self._last_turn_stale:
            self._last_turn_stale = False
            self._last_turn = None
            base = read_turn_tree()
            if base is not None:
                try:
                    now = snapshot_worktree()
                except RuntimeError:
                    log.exception("could not snapshot the worktree for last-turn")
                else:
                    self._last_turn = LastTurn(base, now, get_tree_numstat(base, now))
        return self._last_turn

    def _load_ignore_patterns(self, repo_root: Path) -> None:
        ignore_file = repo_root / ".diffuiignore"
        if ignore_file.exists():
            self.ignore_patterns = [
                line.strip()
                for line in ignore_file.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
        else:
            self.ignore_patterns = []

    @property
    def review_files(self) -> list[str]:
        return sorted(set(self.all_files) | set(self.working_files))

    @property
    def reviewed_count(self) -> int:
        return sum(1 for f in self.review_files if f in self.reviewed)

    def open_comments(self) -> list[dict]:
        return [{**c, "_file": f} for f, cs in self.comments.items() for c in cs if is_comment_open(c)]

    @property
    def theme(self):
        return ALL_THEMES[self.theme_index]

    def settings(self) -> dict:
        return {
            "theme": self.theme.name,
            "editor": self.editor,
            "user_name": self.user_name,
            "agent_cli": self.agent_cli,
            "font_size": self.font_size,
            "word_wrap": self.word_wrap,
            "keybindings": self.keybindings,
        }


app_state = AppState()
