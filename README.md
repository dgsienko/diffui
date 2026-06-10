# diffui

UI for reviewing AI agent diffs. Runs as a local web server with a
Preact frontend — no build step required.

## Install

```bash
pipx install -e .
```

## Usage

`cd` into any git repo on a feature branch and run:

```bash
diffui              # Starts a local server, prints the URL
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
- **Comment threads** — right-click a line or press `c` to leave a
  comment; reply to comments; named authors (user vs agent); edit your
  comments inline; collapse/expand threads
- **Comment categories** — tag comments as bug, suggestion, nit, or
  question with colored badges
- **Code suggestions** — comments can carry a proposed code change with
  an Apply button that patches the file directly
- **Multi-agent support** — multiple named agents get unique
  color-coded identities in comment threads
- **Comment resolution** — resolve/reopen comments with a toggle; resolved
  comments appear dimmed with a status badge
- **Comment navigation** — `n`/`p` to jump between comments across files;
  comments panel shows all open comments grouped by file
- **Inline hover actions** — `+` button to comment and `↗` to open in
  editor appear on hover over any diff line
- **Command palette** — `ctrl+k` to search and execute any command
- **Search** — `ctrl+f` to search across the current diff with match count
  and Enter/Shift+Enter to cycle through matches
- **Go to line** — `ctrl+g` to jump to a specific line number
- **File search** — `ctrl+shift+f` to filter the file list by path
- **Open in editor** — `ctrl+click` or hover action to open the line in
  VS Code, Cursor, Vim, or Neovim (configurable in settings)
- **View modes** — unified diff (default), split (side-by-side), or full
  file view
- **View selector** — switch between all branch changes, individual
  commits (most recent first), or uncommitted working changes
- **Review progress** — visual progress bar with file count in the toolbar
- **Risk scoring** — files scored by risk (migrations, configs, large
  deletions, test removal) with colored dots on tabs and tree; sort by
  risk via command palette
- **Agent orchestration** — "Send to agent" button with confirmation
  dialog showing what the agent will do. Spawns the configured agent CLI
  (Claude Code, Codex, OpenCode, or Cursor Agent) with a rich context
  file containing diffs, review state, and existing comment threads.
  Status bar with live elapsed timer while agent is running
- **Explain changes** — generate a self-contained HTML walkthrough of
  branch changes via command palette (TL;DR, file-by-file analysis,
  architecture notes, risk flags) using the configured agent CLI
- **Blame gutter** — toggleable git blame column showing author and age
  with aligned columns
- **Markdown/image preview** — toggleable rendered preview for `.md`
  files and inline display for images
- **Review summary export** — `Shift+S` copies a formatted markdown
  summary to clipboard with stats and open comments by category
- **Ignore whitespace** — toggle to hide whitespace-only changes (`w` key)
- **Ignore patterns** — `.diffuiignore` file to hide files from review
  (still visible to agents)
- **Bulk resolve** — resolve all open comments in a file or globally
  from the command palette or comments panel
- **Expand/collapse all hunks** — via command palette
- **Hunk statistics** — each hunk header shows its own +/- counts
- **Inline suggestion preview** — before/after diff for code suggestions
- **Font size control** — adjustable in settings or via command palette
- **Word wrap** — toggleable, dynamic with window width, preserves line
  numbers
- **Custom keybindings** — rebind action shortcuts in settings
- **Connection status** — live/offline indicator in the footer
- **Untracked files** — new files not yet added to git are shown
- **Explorer sidebar** — file tree with grouping modes (directory, type,
  status) and resizable via drag handle; open by default
- **Comments panel** — sidebar showing all open comments grouped by file;
  click to jump to the comment
- **Completion screen** — overlay when all files are reviewed with stats
- **Branch name** — displayed in the top bar
- **15 color themes** — Catppuccin Mocha, Catppuccin Latte, GitHub Dark,
  Dracula, One Dark, Solarized Dark, Gruvbox Dark, Nord, Tokyo Night,
  Rose Pine, Rose Pine Moon, Monokai Pro, Kanagawa, Everforest, Ayu Dark
- **Auto-refresh** — real-time updates via WebSocket (SSE fallback)
  powered by watchfiles (FSEvents/inotify)
- **Virtual scrolling** — windowed rendering for large files; browser-
  native content-visibility for hunk blocks
- **Session persistence** — active file, diff mode, scroll positions,
  and UI state restored on reload
- **JSON export** — `diffui --json` outputs structured review data for
  agent/CLI integration
- **Settings persistence** — theme, editor, view mode, and display name
  saved across sessions
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
| `c` | Comment on hovered line |
| `y` | Copy current file path to clipboard |
| `Y` | Copy GitLab link to clipboard |
| `s` | Toggle sort by risk |
| `S` | Copy review summary to clipboard |
| `]` | Jump to next unreviewed file |
| `b` | Toggle explorer sidebar |
| `w` | Toggle ignore whitespace |
| `ctrl+f` | Search in diff |
| `ctrl+g` | Go to line |
| `ctrl+shift+f` | Search files |
| `escape` | Close any open panel or dialog |
| `ctrl+click` | Open line in editor |
| `right-click` | Add comment on a line |

## AI Agent Integration

Comments are stored at `~/.config/diffui/{repo}/{branch}/comments.json`.
Each comment includes the file path, line number, diff context, comment
text, author name, author type, category, optional code suggestion, and
status (open/resolved). AI agents can read this file to address review
feedback and reply to comments.

`diffui --json` exports the full review session as structured JSON
including branch info, per-file review status, comments, and a summary
with open/resolved counts — useful for programmatic agent workflows.

To have an agent address your comments:

- Click **"Send to agent"** in the toolbar — a confirmation dialog
  shows the configured agent, comment count, and what the agent will do.
  Confirm to spawn the agent with a rich context file containing full
  diffs, review state, and existing comment threads
- Or tell your agent directly: "Go address the diffui comments"

The agent will reply to comments explaining what it did, ask clarifying
questions when unsure, and leave unresolved comments in place. A status
bar shows live elapsed time while the agent is running. diffui
auto-refreshes as the agent works.

Configure your preferred agent CLI in Settings (gear icon).

Use **"Explain changes"** from the command palette to generate a
self-contained HTML walkthrough of the branch (TL;DR, file-by-file
analysis, architecture notes, risk flags).

## State

All state lives in `~/.config/diffui/` — nothing is written to repo
directories.

- `~/.config/diffui/settings.json` — theme, editor, view mode, display
  name, agent CLI (global)
- `~/.config/diffui/{repo}/{branch}/reviewed.json` — review status
  (per-branch)
- `~/.config/diffui/{repo}/{branch}/comments.json` — comments
  (per-branch)
- `~/.config/diffui/{repo}/{branch}/session.json` — UI session state
  (per-branch)

## Development

```bash
# Install with dev deps
pipx inject diffui pytest ruff

# Run tests (187 tests)
cd ~/code/diffui && pytest

# Lint
ruff check diffui/ tests/
```

## Project Structure

```text
diffui/
├── cli.py              # Entry point — starts FastAPI server
├── diff.py             # Diff parsing, syntax highlighting, word diff
├── git_utils.py        # Git operations, blame, state persistence
├── server/             # FastAPI backend (web UI)
│   ├── app.py          # FastAPI app factory
│   ├── events.py       # WebSocket + SSE endpoints, watchfiles watcher
│   ├── highlight.py    # Pygments-to-HTML adapter
│   ├── models.py       # Pydantic request models
│   ├── routes_*.py     # API routes (repos, diffs, blame, preview,
│   │                   #   comments, review, settings, session)
│   ├── state.py        # Shared app state
│   └── theme_css.py    # CSS custom property generator
├── static/             # Preact frontend (web UI, no build step)
│   ├── app.js          # Main app component
│   ├── lib/            # Shared utilities
│   │   ├── markdown.js #   Markdown renderer (marked.js wrapper)
│   │   └── utils.js    #   shortName, mergeRef helpers
│   ├── components/     # TopBar, FileTabs, DiffViewer, SplitDiffViewer,
│   │                   #   FullFileViewer, FileTree, CommentBox,
│   │                   #   CommentDisplay, CommentsPanel, SearchBar,
│   │                   #   FileFilterBar, LineActions, SettingsPanel,
│   │                   #   Minimap, ShortcutOverlay, Toast,
│   │                   #   CommandPalette, CompletionScreen,
│   │                   #   PreviewViewer, AgentStatusBar,
│   │                   #   AgentConfirmDialog, GoToLineDialog
│   ├── index.html      # Shell page with importmap
│   └── style.css       # Styles using CSS custom properties
├── themes/
│   ├── theme.py        # Theme dataclass
│   └── definitions.py  # 15 theme definitions
└── tests/
    ├── test_diff.py        # Diff parsing tests (46 tests)
    ├── test_events.py      # Watcher + broadcast tests (24 tests)
    ├── test_git_utils.py   # Blame, session, utility tests (29 tests)
    ├── test_highlight.py   # HTML highlight adapter tests (18 tests)
    ├── test_server.py      # API routes, WebSocket, risk scoring,
    │                       #   agent/explain endpoints, settings, export,
    │                       #   bulk resolve, pydantic validation (62 tests)
    └── test_themes.py      # Theme definitions and state tests (8 tests)
```
