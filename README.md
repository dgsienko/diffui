# diffui

UI for reviewing AI agent diffs. Comes in two flavors: a web UI
(default) and a terminal TUI.

## Install

```bash
pipx install -e ~/code/diffui
```

## Usage

`cd` into any git repo on a feature branch and run:

```bash
diffui              # Web UI — starts a local server, prints the URL
diffui-tui          # Terminal UI — runs in the terminal via Textual
```

diffui shows all files changed on the current branch (vs the merge base
with main/master) in a tabbed, syntax-highlighted diff viewer.

Sibling repos in the same parent directory are auto-discovered and
available via a dropdown switcher.

### CLI flags

```bash
diffui --comments    # Dump all comments to stdout
diffui --json        # Export review session as structured JSON
diffui --open        # Web UI: also open the URL in a browser
```

## Features

- **Tabbed file navigation** — arrow keys or click to switch files
- **Syntax highlighting** — language-aware via Pygments
- **Word-level diff highlighting** — changed words within lines are
  underlined
- **File header** — pinned bar showing full file path, additions, and
  deletions with an inline review button
- **Collapsible hunks** — click hunk headers to collapse/expand
- **Review tracking** — mark files as reviewed; auto-advances to next
  unreviewed file; auto-unmarks when the file changes (tracked by mtime)
- **Comment threads** — right-click a line to leave a comment; reply to
  comments; named authors (user vs agent); edit your comments inline;
  collapse/expand threads
- **Comment resolution** — resolve/reopen comments with a toggle; resolved
  comments appear dimmed with a status badge
- **Comment navigation** — `n`/`p` to jump between comments across files
- **Command palette** — `ctrl+k` to search and execute any command
- **Search** — `ctrl+f` to search across the current diff (debounced)
- **Open in editor** — `ctrl+click` to open the line in VS Code, Cursor,
  Vim, or Neovim (configurable in settings)
- **View modes** — unified diff (default), split (side-by-side), or full
  file view
- **View selector** — switch between all branch changes, individual
  commits (most recent first), or uncommitted working changes
- **Untracked files** — new files not yet added to git are shown
- **File tree sidebar** — press `b` to toggle a collapsible file tree
- **Completion screen** — celebratory overlay when all files are reviewed,
  with stats and open comment count
- **Branch name** — displayed in the top bar
- **15 color themes** — Catppuccin Mocha, Catppuccin Latte, GitHub Dark,
  Dracula, One Dark, Solarized Dark, Gruvbox Dark, Nord, Tokyo Night,
  Rose Pine, Rose Pine Moon, Monokai Pro, Kanagawa, Everforest, Ayu Dark
- **Auto-refresh** — real-time filesystem watching via watchfiles
  (FSEvents/inotify) with 400ms debounce
- **JSON export** — `diffui --json` outputs structured review data for
  agent/CLI integration
- **Settings persistence** — theme, editor, view mode, and display name
  saved across sessions
- **Scroll position persistence** — switching tabs preserves your scroll
  position
- **Context-aware keybindings** — shortcuts are suppressed when dialogs
  are open

## Keybindings

| Key | Action |
| --- | --- |
| `ctrl+k` | Open command palette |
| `?` | Show keyboard shortcuts overlay |
| `left` / `right` | Previous / next file tab |
| `j` / `k` | Next / previous hunk |
| `r` | Toggle reviewed (auto-advances to next unreviewed) |
| `a` | Show all / hide reviewed files |
| `n` / `p` | Next / previous comment |
| `y` | Copy current file path to clipboard |
| `Y` | Copy GitLab link to clipboard |
| `b` | Toggle file tree sidebar |
| `ctrl+f` | Open search |
| `escape` | Close any open panel or dialog |
| `ctrl+click` | Open line in editor |
| `right-click` | Add comment on a line |
| `q` | Quit |

## AI Agent Integration

Comments are stored at `~/.config/diffui/{repo}/{branch}/comments.json`.
Each comment includes the file path, line number, diff context, comment
text, author name, author type, and status (open/resolved). AI agents
can read this file to address review feedback and reply to comments.

`diffui --json` exports the full review session as structured JSON
including branch info, per-file review status, comments, and a summary
with open/resolved counts — useful for programmatic agent workflows.

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

# Run tests (145 tests)
cd ~/code/diffui && pytest

# Lint
ruff check diffui/ tests/
```

## Project Structure

```text
diffui/
├── cli.py              # Web UI entry point
├── cli_tui.py          # TUI entry point
├── app.py              # Textual TUI app class
├── widgets.py          # TUI widgets
├── diff.py             # Diff parsing, syntax highlighting, word diff
├── git_utils.py        # Git operations and state persistence
├── server/             # FastAPI backend (web UI)
│   ├── app.py          # FastAPI app factory
│   ├── events.py       # SSE endpoint + watchfiles-based filesystem watcher
│   ├── highlight.py    # Pygments-to-HTML adapter
│   ├── routes_*.py     # API routes (repos, diffs, comments, review, settings)
│   ├── state.py        # Shared app state
│   └── theme_css.py    # CSS custom property generator
├── static/             # Preact frontend (web UI)
│   ├── app.js          # Main app component
│   ├── components/     # TopBar, FileTabs, DiffViewer, SplitDiffViewer,
│   │                   #   FullFileViewer, FileTree, CommentBox,
│   │                   #   CommentDisplay, SearchBar, SettingsPanel,
│   │                   #   Minimap, ShortcutOverlay, Toast,
│   │                   #   CommandPalette, CompletionScreen
│   ├── index.html      # Shell page
│   └── style.css       # Styles using CSS custom properties
├── themes/
│   ├── theme.py        # Theme dataclass
│   ├── definitions.py  # 15 theme definitions
│   └── css.py          # Textual CSS template generator
└── tests/
    ├── test_diff.py        # Diff parsing tests (48 tests)
    ├── test_events.py      # Filesystem watcher tests (22 tests)
    ├── test_git_utils.py   # Persistence and utility tests (25 tests)
    ├── test_highlight.py   # HTML highlight adapter tests (18 tests)
    ├── test_server.py      # API route and JSON export tests (20 tests)
    └── test_themes.py      # Theme definitions and CSS tests (12 tests)
```
