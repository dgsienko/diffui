from __future__ import annotations

from diffui.themes.theme import Theme


def generate_css(t: Theme) -> str:
    return f"""
    Screen {{
        background: {t.bg};
    }}

    #top-bar {{
        height: 5;
        dock: top;
        padding: 1 1;
        background: {t.bg_dark};
    }}

    #repo-select {{
        height: 3;
        margin: 0 1;
        width: 5fr;
        min-width: 35;
    }}

    #view-select {{
        height: 3;
        margin: 0 1;
        width: 3fr;
    }}

    #comments-select {{
        height: 3;
        margin: 0 1;
        width: 3fr;
    }}

    OptionList {{
        background: {t.bg_dark};
        padding: 0;
    }}

    Select > SelectOverlay > .option-list--option {{
        padding: 0 2;
    }}

    .option-list--separator {{
        color: {t.border};
    }}

    .review-btn-mark {{
        background: {t.add_bg};
        color: {t.fg};
        border: tall {t.add_hover};
    }}

    .review-btn-mark:hover {{
        background: {t.add_hover};
    }}

    .review-btn-unmark {{
        background: {t.warn_bg};
        color: {t.warn_fg};
        border: tall {t.warn_hover};
    }}

    .review-btn-unmark:hover {{
        background: {t.warn_hover};
    }}

    #toggle-reviewed {{
        margin: 0 1;
        min-width: 20;
        background: {t.bg};
        color: {t.fg_muted};
        border: tall {t.border};
    }}

    #toggle-reviewed:hover {{
        background: {t.hover_bg};
        color: {t.fg};
    }}

    #settings-btn {{
        min-width: 5;
        max-width: 5;
        margin: 0 1;
        background: {t.bg};
        color: {t.fg_muted};
        border: solid {t.bg};
        text-align: center;
    }}

    #settings-btn:hover {{
        background: {t.hover_bg};
        color: {t.fg};
    }}

    #settings-btn:focus {{
        background: {t.bg};
        color: {t.fg_muted};
        text-style: none;
    }}

    #top-bar-spacer {{
        width: 1fr;
    }}

    #branch-label {{
        height: 3;
        content-align: center middle;
        color: {t.fg_muted};
        padding: 0 1;
        width: auto;
    }}

    #file-counter {{
        height: 3;
        content-align: center middle;
        color: {t.fg_muted};
        padding: 0 2;
        width: auto;
    }}

    #file-tabs {{
        height: 1fr;
    }}

    TabbedContent ContentSwitcher {{
        background: {t.bg};
    }}

    Tabs {{
        background: {t.bg_dark};
        min-height: 3;
        padding: 1 0 0 0;
    }}

    Tab {{
        background: {t.bg_dark};
        color: {t.fg_muted};
        padding: 0 3;
        margin: 0;
    }}

    Tab:hover {{
        background: {t.hover_bg};
        color: {t.fg};
    }}

    Tab.-active {{
        background: {t.bg};
        color: {t.fg};
        text-style: bold;
    }}

    Underline {{
        color: {t.accent};
    }}

    TabPane {{
        padding: 0;
    }}

    DiffViewer {{
        height: 1fr;
        background: {t.bg};
    }}

    .diff-file-header {{
        width: 1fr;
        height: 4;
        padding: 0 2 1 2;
        background: {t.bg_dark};
        color: {t.fg};
        dock: top;
    }}

    .diff-file-path {{
        width: 1fr;
        height: 3;
        content-align: left middle;
    }}

    #inline-review-btn {{
        margin: 0 1;
        min-width: 20;
        content-align: center middle;
        text-align: center;
    }}

    DiffLine {{
        width: 1fr;
        height: auto;
        padding: 0 1;
        color: {t.fg};
    }}

    .diff-gutter {{
        width: 13;
        min-width: 13;
        max-width: 13;
        height: auto;
    }}

    .diff-code {{
        width: 1fr;
        height: auto;
    }}

    DiffLine:hover {{
        background: {t.hover_bg};
    }}

    .diff-add {{
        background: {t.add_bg};
    }}

    .diff-add:hover {{
        background: {t.add_hover};
    }}

    .diff-remove {{
        background: {t.remove_bg};
    }}

    .diff-remove:hover {{
        background: {t.remove_hover};
    }}

    .diff-hunk {{
        background: {t.hunk_bg};
    }}

    .diff-meta {{
        background: {t.bg};
    }}

    .diff-context {{
        background: {t.bg};
    }}

    .empty-state {{
        text-align: center;
        margin-top: 5;
        color: {t.fg_muted};
    }}

    .search-match {{
        background: {t.warn_bg};
    }}

    Collapsible {{
        height: auto;
        padding: 0;
        border: none;
    }}

    CollapsibleTitle {{
        background: {t.hunk_bg};
        color: {t.hunk_fg};
        padding: 0 1;
    }}

    CollapsibleTitle:hover {{
        background: {t.hover_bg};
    }}

    InlineCommentBox {{
        height: auto;
        background: {t.comment_bg};
        border-left: thick {t.comment_accent};
        padding: 1 2;
        margin: 1 2 1 14;
    }}

    #inline-comment-actions {{
        height: 3;
        align: left middle;
    }}

    #inline-comment-actions Button {{
        margin: 0 1 0 0;
    }}

    InlineCommentDisplay {{
        height: auto;
        background: {t.comment_bg};
        border-left: thick {t.comment_accent};
        padding: 0;
        margin: 1 2 1 14;
    }}

    .comment-header {{
        height: 1;
        background: {t.comment_header_bg};
        padding: 0 1;
    }}

    .comment-label {{
        width: 1fr;
        color: {t.comment_accent};
        text-style: bold;
    }}

    .comment-body {{
        padding: 1 1;
        color: {t.fg};
    }}

    .comment-delete {{
        min-width: 3;
        width: auto;
        height: 1;
        background: {t.delete_bg};
        color: {t.delete_fg};
        border: none;
    }}

    .comment-delete:hover {{
        background: {t.delete_hover};
    }}

    .comment-reply-btn {{
        min-width: 3;
        width: auto;
        height: 1;
        background: transparent;
        color: {t.fg_muted};
        border: none;
    }}

    .comment-reply-btn:hover {{
        color: {t.accent};
    }}

    .comment-reply {{
        color: {t.fg_muted};
        padding: 0 1;
    }}

    .reply-row {{
        height: auto;
        padding: 0 1;
    }}

    .comment-reply-text {{
        width: 1fr;
        color: {t.fg_muted};
    }}

    .reply-edit-btn {{
        min-width: 3;
        width: auto;
        height: 1;
        background: transparent;
        color: {t.fg_muted};
        border: none;
    }}

    .reply-edit-btn:hover {{
        color: {t.accent};
    }}

    .reply-edit-group {{
        height: auto;
        margin: 0 1;
    }}

    .comment-edit-btn {{
        min-width: 3;
        width: auto;
        height: 1;
        background: transparent;
        color: {t.fg_muted};
        border: none;
    }}

    .comment-edit-btn:hover {{
        color: {t.accent};
    }}

    .comment-edit-input {{
        margin: 0 1;
        height: auto;
        max-height: 6;
    }}

    .comment-reply-input {{
        margin: 0 1;
        height: auto;
        max-height: 6;
    }}

    .inline-editing {{
        height: auto;
        max-height: 10;
    }}

    .inline-edit-group {{
        height: auto;
    }}

    .inline-edit-actions {{
        height: 3;
        padding: 0;
    }}

    .inline-edit-actions Button {{
        margin: 0 1 0 0;
    }}



    .comment-input-group {{
        height: auto;
        margin: 0 1;
    }}

    .comment-reply-save, .comment-edit-save {{
        margin: 0 1;
        width: auto;
    }}

    #inline-comment-input {{
        width: 1fr;
        height: auto;
        max-height: 8;
        margin: 0 0 1 0;
    }}

    /* --- File tree --- */

    FileTree {{
        dock: left;
        width: 30;
        min-width: 20;
        max-width: 40;
        background: {t.bg_dark};
        border-right: solid {t.border};
        padding: 1 0;
    }}

    .filetree-title {{
        padding: 0 2 1 2;
        color: {t.fg};
        text-style: bold;
    }}

    .filetree-dir {{
        padding: 1 2 0 2;
        color: {t.fg_muted};
    }}

    .filetree-file {{
        width: 1fr;
        height: 1;
        background: transparent;
        color: {t.fg};
        border: none;
        padding: 0 2 0 4;
        text-align: left;
    }}

    .filetree-file:hover {{
        background: {t.hover_bg};
    }}

    .filetree-active {{
        background: {t.hover_bg};
        color: {t.accent};
        text-style: bold;
    }}

    #view-mode-select {{
        width: 100%;
        margin-bottom: 1;
    }}

    #search-bar {{
        height: 3;
        dock: top;
        background: {t.bg_dark};
        border-bottom: solid {t.border};
        padding: 0 1;
    }}

    #search-label {{
        height: 3;
        content-align: left middle;
        color: {t.fg_muted};
        width: auto;
        padding: 0 1;
    }}

    #search-input {{
        width: 1fr;
    }}

    #search-close {{
        min-width: 3;
        margin: 0 0 0 1;
    }}

    #legend {{
        dock: bottom;
        height: auto;
        max-height: 2;
        background: {t.bg_dark};
        color: {t.fg_muted};
        padding: 0 2;
    }}

    SettingsPanel {{
        dock: right;
        width: 35;
        height: 1fr;
        background: {t.bg_dark};
        border-left: solid {t.border};
        padding: 1 2;
        layer: overlay;
    }}

    #settings-title {{
        margin-bottom: 1;
        color: {t.fg};
        text-style: bold;
    }}

    .settings-label {{
        margin-top: 1;
        color: {t.fg_muted};
    }}

    #theme-select {{
        width: 100%;
        margin-bottom: 1;
    }}

    #editor-select {{
        width: 100%;
        margin-bottom: 1;
    }}

    #settings-close {{
        margin-top: 1;
        width: 100%;
        background: {t.bg};
        color: {t.fg};
        border: tall {t.border};
    }}

    #settings-close:hover {{
        background: {t.hover_bg};
    }}
    """
