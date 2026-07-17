from __future__ import annotations

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    file_path: str
    line_index: int
    line_text: str = ""
    file_line_num: int | None = None
    comment: str
    author: str | None = None
    author_type: str = "user"
    status: str = "open"
    category: str = ""
    suggestion: str = ""
    selected_text: str = ""
    sel_start: int | None = None
    sel_end: int | None = None


class CommentEdit(BaseModel):
    comment: str


class ReplyCreate(BaseModel):
    text: str
    author: str | None = None
    author_type: str = "user"


class BulkResolve(BaseModel):
    file_path: str | None = None
    action: str = Field(default="resolve", pattern="^(resolve|reopen)$")


class RepoSwitch(BaseModel):
    index: int = 0


class SettingsUpdate(BaseModel):
    theme_index: int | None = None
    editor: str | None = None
    view_mode: str | None = None
    user_name: str | None = None
    agent_cli: str | None = None
    font_size: int | None = None
    word_wrap: bool | None = None
    keybindings: dict[str, str] | None = None


class EditorOpen(BaseModel):
    file_path: str
    line_num: int = 1


class SessionUpdate(BaseModel):
    activeFile: str | None = None
    diffMode: str | None = None
    showFileTree: bool | None = None
    showReviewed: bool | None = None
    scrollPositions: dict[str, float] | None = None
