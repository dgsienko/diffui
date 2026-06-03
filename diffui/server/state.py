from __future__ import annotations

from pathlib import Path

from diffui.git_utils import (
    Commit,
    clear_branch_cache,
    current_branch,
    get_branch_commits,
    get_changed_files,
    get_main_branch,
    get_merge_base,
    load_comments,
    load_reviewed,
    load_settings,
)
from diffui.themes import ALL_THEMES, CATPPUCCIN_MOCHA, get_current_theme, set_current_theme


class AppState:
    def __init__(self) -> None:
        self.repos: list[Path] = []
        self.active_repo_index: int = 0
        self.merge_base: str = ""
        self.commits: list[Commit] = []
        self.all_files: list[str] = []
        self.numstat: dict[str, tuple[int, int]] = {}
        self.reviewed: dict[str, float] = {}
        self.comments: dict[str, list[dict]] = {}
        self.current_view: str = "all"
        self.branch_name: str = ""

        saved = load_settings()
        theme_name = saved.get("theme", CATPPUCCIN_MOCHA.name)
        theme_index = next((i for i, t in enumerate(ALL_THEMES) if t.name == theme_name), 0)
        set_current_theme(ALL_THEMES[theme_index])

        self.editor: str = saved.get("editor", "code")
        self.view_mode: str = saved.get("view_mode", "diff")
        self.user_name: str = saved.get("user_name", "User")
        self.theme_index: int = theme_index

    def reload_repo_state(self) -> None:
        clear_branch_cache()
        self.branch_name = current_branch()
        main_branch = get_main_branch()
        self.merge_base = get_merge_base(main_branch)
        self.commits = get_branch_commits(self.merge_base)
        self.all_files = get_changed_files(self.merge_base)
        from diffui.git_utils import get_diff_numstat

        self.numstat = get_diff_numstat(self.merge_base)
        self.reviewed = load_reviewed()
        self.comments = load_comments()
        self.current_view = "all"

    def reload_branch_name(self) -> str:
        self.branch_name = current_branch()
        return self.branch_name

    @property
    def theme(self):
        return get_current_theme()


app_state = AppState()
