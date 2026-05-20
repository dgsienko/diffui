# diffui

Terminal UI for reviewing AI agent diffs. Inspired by the diff review
experience in GitHub, GitLab, Supacode, and similar tools — but in your
terminal.

## Install

```bash
pipx install -e ~/code/diffui
```

## Usage

`cd` into any git repo on a feature branch and run:

```bash
diffui
```

diffui shows all files changed on the current branch (vs the merge base
with main/master) in a tabbed, syntax-highlighted diff viewer.

### CLI flags

```bash
diffui --comments    # Dump all comments to stdout (no TUI)
```

## Features

- **Tabbed file navigation** — arrow keys or click to switch files
- **Syntax highlighting** — language-aware via Pygments
- **Word-level diff highlighting** — changed words within lines are
  underlined
- **File header** — pinned bar showing full file path, additions, and
  deletions with an inline review button
- **Collapsible hunks** — click hunk headers to collapse/expand
- **Review tracking** — mark files as reviewed; auto-unmarks when the
  file changes (tracked by file modification time)
- **Comment threads** — right-click a line to leave a comment; reply to
  comments; named authors (user vs agent); edit your comments inline
- **Comment navigation** — `n`/`p` to jump between comments across files
- **Search** — ctrl+f to search across the current diff (debounced)
- **Open in editor** — ctrl+click to open the line in VS Code, Cursor,
  Vim, or Neovim (configurable in settings)
- **View modes** — diff view (default) or full file view, switchable in
  settings
- **View selector** — switch between all branch changes, individual
  commits (most recent first), or uncommitted working changes
- **Untracked files** — new files not yet added to git are shown
- **File tree sidebar** — press `b` to toggle a collapsible file tree
- **Branch name** — displayed in the top bar
- **10 color themes** — Catppuccin Mocha, GitHub Dark, Dracula, One Dark,
  Solarized Dark, Gruvbox Dark, Nord, Tokyo Night, Rose Pine, Monokai Pro
- **Auto-refresh** — detects file changes, new commits, and comment edits
  every 3 seconds (polling runs off the main thread)
- **Settings persistence** — theme, editor, view mode, and display name
  saved across sessions
- **Scroll position persistence** — switching tabs preserves your scroll
  position

## Keybindings

| Key | Action |
| --- | --- |
| `r` | Toggle reviewed status on current file |
| `a` | Show all / hide reviewed files |
| `n` / `p` | Next / previous comment |
| `j` / `k` | Next / previous hunk |
| `left` / `right` | Previous / next file tab |
| `y` | Copy current file path to clipboard |
| `b` | Toggle file tree sidebar |
| `ctrl+f` | Open search |
| `escape` | Close settings panel or search bar |
| `ctrl+click` | Open line in editor |
| `right-click` | Add comment on a line |
| `q` | Quit |

## AI Agent Integration

Comments are stored at `~/.config/diffui/{repo}/{branch}/comments.json`.
Each comment includes the file path, line number, diff context, comment
text, author name, and author type. AI agents can read this file to
address review feedback and reply to comments.

To have an agent address your comments, just ask:

> "Go address the diffui comments"

The agent will read the comments, reply with what it did, make the
changes, and remove addressed comments from the file. diffui
auto-refreshes when the file changes.

## State

All state lives in `~/.config/diffui/` — nothing is written to repo
directories.

- `~/.config/diffui/settings.json` — theme, editor, view mode, display
  name (global)
- `~/.config/diffui/{repo}/{branch}/reviewed.json` — review status
  (per-branch)
- `~/.config/diffui/{repo}/{branch}/comments.json` — comments
  (per-branch)

## Development

```bash
# Install with dev deps
pipx inject diffui pytest ruff

# Run tests (81 tests)
cd ~/code/diffui && pytest

# Lint
ruff check diffui/ tests/
```

## Project Structure

```text
diffui/
├── cli.py              # Entry point, --comments flag
├── app.py              # DiffUI app class
├── widgets.py          # UI widgets (DiffLine, DiffViewer, comments,
│                       #   search, settings, file tree)
├── diff.py             # Diff parsing, syntax highlighting, word diff
├── git_utils.py        # Git operations and state persistence
├── themes/
│   ├── __init__.py     # Theme state management and re-exports
│   ├── theme.py        # Theme dataclass
│   ├── definitions.py  # 10 theme definitions
│   └── css.py          # CSS template generator
└── tests/
    ├── test_diff.py    # Diff parsing tests (49 tests)
    ├── test_git_utils.py # Persistence and utility tests (17 tests)
    └── test_themes.py  # Theme definitions and CSS tests (16 tests)
```
