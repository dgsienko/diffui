# diffui

UI for reviewing AI agent diffs. FastAPI backend + Preact frontend,
no build step required.

## Tech Stack

- **Python 3.10+**
- **FastAPI + uvicorn** (server)
- **Preact + HTM** (frontend, no build step)
- **Pygments** for syntax highlighting
- **watchfiles** for real-time filesystem watching (Rust-backed FSEvents/inotify)
- Git operations via `subprocess` (no gitpython dependency)
- Installed globally via `pipx install -e .`

## Architecture

```text
diffui/
├── cli.py              # Entry point — starts FastAPI server
├── diff.py             # Pure functions — diff parsing, line classification, syntax
│                       #   highlighting, word-level diff ranges
├── git_utils.py        # Git subprocess helpers, blame, state persistence,
│                       #   repo discovery, session management
├── server/             # FastAPI backend (web UI)
│   ├── app.py          # App factory — mounts routes, static files, starts watcher
│   ├── events.py       # WebSocket + SSE endpoints, watchfiles-based filesystem
│   │                   #   watcher with 400ms debounce
│   ├── highlight.py    # Pygments-to-HTML adapter, word highlight overlay
│   ├── routes_comments.py  # Comment CRUD, suggestion apply endpoint
│   ├── routes_diff.py      # Diff, files, blame, preview, risk scoring
│   ├── routes_repo.py      # Repo listing and switching
│   ├── routes_review.py    # Review toggle, summary export, agent/explain
│   │                       #   orchestration (thread-safe process management)
│   ├── routes_settings.py  # Settings, editor open, session persistence
│   ├── state.py        # AppState singleton — shared server state
│   └── theme_css.py    # generate_css_vars(theme) — CSS custom properties
├── static/             # Preact frontend (no build step, ESM imports via importmap)
│   ├── app.js          # Root component, state management, keyboard shortcuts,
│   │                   #   WebSocket client, session restore
│   ├── lib/            # Shared utilities
│   │   ├── markdown.js #   marked.js wrapper with GFM config
│   │   └── utils.js    #   shortName(), mergeRef() helpers
│   ├── components/     # TopBar, FileTabs, DiffViewer, SplitDiffViewer,
│   │                   #   FullFileViewer, FileTree, CommentBox,
│   │                   #   CommentDisplay, CommentsPanel, SearchBar,
│   │                   #   FileFilterBar, LineActions, SettingsPanel,
│   │                   #   Minimap, ShortcutOverlay, Toast,
│   │                   #   CommandPalette, CompletionScreen, PreviewViewer,
│   │                   #   AgentStatusBar, AgentConfirmDialog
│   ├── index.html      # Shell page with importmap for preact/htm CDN
│   └── style.css       # All styles via CSS custom properties (themed)
└── themes/
    ├── __init__.py     # Theme state (get/set_current_theme), re-exports
    ├── theme.py        # Theme dataclass (30+ color fields)
    └── definitions.py  # 15 theme instances with Pygments token color maps
```

### Shared Patterns

- **Multi-repo discovery** — `resolve_repos()` in `git_utils.py` scans
  the parent directory for sibling git repos. Both frontends use this.
- **Branch-scoped state** — reviewed status, comments, and session stored
  at `~/.config/diffui/{repo}/{branch}/`. `get_repo_root()` and
  `_cached_current_branch()` are `lru_cache`'d.
- **Comment threads** — comments have `id` (UUID), `author`/`author_type`
  fields, `category` (bug/suggestion/nit/question), optional `suggestion`
  (proposed code), and `status` (open/resolved). Replies are structured
  dicts. Edit locking: user content is editable until an agent replies.
  Threads are collapsible in the web UI.
- **Multi-agent identity** — agent authors get unique colors via a name
  hash. Multiple agents reviewing the same branch appear as distinct
  identities in comment headers and reply threads.
- **Word-level diff** — `pair_diff_lines` matches consecutive remove/add
  pairs and `word_diff_ranges` uses `difflib.SequenceMatcher` to find
  changed word spans.
- **Worktree support** — `get_git_dir()` resolves the actual `.git`
  directory for both regular repos and worktrees.

### Web UI Patterns

- **WebSocket + SSE** — `events.py` provides a WebSocket endpoint
  (`/api/ws`) for bidirectional communication. Client prefers WebSocket
  and falls back to SSE (`/api/events`) if the connection closes.
  Both use `watchfiles` (Rust-backed FSEvents/inotify) for real-time
  filesystem watching with 400ms debounce. Watches repo dir, `.git`
  dir, and comments file. Background tasks use `_bg_tasks` set to
  prevent garbage collection.
- **Diff caching** — server-side `_diff_cache` keyed by
  `(repo, merge_base, path, view, mtime)`. Client-side `diffCache` Map
  for instant tab switching with stale-while-revalidate. Numstat is
  cached in `AppState` and refreshed on `reload_repo_state`.
- **Virtual scrolling** — `FullFileViewer` uses windowed rendering (only
  visible lines + buffer in DOM). Hunk blocks in unified/split views
  use `content-visibility: auto` for browser-native off-screen culling.
- **Scroll persistence** — client saves/restores scroll positions per
  file in a Map. Comment dropdown navigation scrolls to the exact line
  using `data-line-new` attributes for O(1) DOM lookup.
- **Session persistence** — `session.json` per branch saves active file,
  diff mode, file tree state, show-reviewed toggle, and scroll positions.
  Restored on page load; saved with 1-second debounce.
- **Risk scoring** — `_score_risk()` in `routes_diff.py` assigns
  risk_level (low/medium/high) based on file patterns (migrations,
  configs, large deletions, test removal, high churn). Shown as colored
  dots on file tabs and tree items. Sort-by-risk toggle via command
  palette.
- **Agent orchestration** — confirmation dialog shows agent name, comment
  count, and behavior summary. `/api/agent/run` spawns the configured
  agent CLI with a rich context file (`_build_agent_context`) containing
  full diffs, review state, and thread history. `/api/agent/status` polls.
  Agent CLI is configurable in settings (Claude Code, Codex, OpenCode,
  Cursor Agent). Process management uses `_process_lock` for thread
  safety and `_process_status` for reaping. `AgentStatusBar` shows live
  elapsed timer during execution.
- **Explain changes** — `/api/explain` spawns the configured agent CLI
  to generate a self-contained HTML walkthrough. `/api/explain/status`
  polls. `/api/explain/view` serves the result as a localhost page
  (path-traversal guarded to tempdir). Toolbar button + status bar link.
- **Blame gutter** — toggleable per-file. Fetches `git blame --porcelain`
  via `/api/blame/{path}`. Results cached client-side in a `Map`.
- **Preview mode** — toggleable for `.md` and image files. Backend uses
  `mimetypes.guess_type` for image detection with 10MB size cap. Markdown
  rendered via `marked.js` through shared `lib/markdown.js`.
- **Theme switching** — server generates CSS custom properties from
  Theme dataclass fields. Client injects a `<style>` tag. All colors
  use CSS variables — no hardcoded values.
- **No build step** — Preact + HTM loaded via importmap from CDN. All
  frontend ships as plain `.js`/`.css`/`.html` in the Python package.
- **Shared utilities** — `lib/markdown.js` provides `renderMd()` used by
  both `CommentDisplay` and `PreviewViewer`. `lib/utils.js` provides
  `shortName()` and `mergeRef()`.
- **Two-row header** — row 1 has repo/view selects and branch pill;
  row 2 (toolbar) has mode toggle, review controls, panel toggles
  (Explorer, Search files, Comments), agent button, and diff stats.
- **Inline hover actions** — `LineActions` component shows `+` (comment)
  and `↗` (open in editor) buttons on diff line hover.
- **Comments panel** — `CommentsPanel` sidebar shows all open comments
  grouped by file. Click to jump.
- **File filter** — `FileFilterBar` toggled via `Ctrl+Shift+F`. Filters
  `visibleFiles` by path substring.
- **Explorer sidebar** — `FileTree` with grouping modes (directory, type,
  status), resizable via drag handle, open by default.
- **Review progress** — visual progress bar + count in toolbar.
- **CSS design system** — `--radius-sm/md/lg`, `--shadow-low/high` CSS
  variables. All spacing on 4/8pt grid. No hardcoded colors.
- **Error handling** — `safeFetch` wrapper shows toast on failed requests.
- **Accessibility** — ARIA labels on selects, `role="tab"` and keyboard
  activation on file tabs, `role="treeitem"` on file tree items, focus
  trapping in settings dialog.

### Design System

All frontend changes must follow these rules:

- **Spacing:** 4/8pt grid only (4, 8, 12, 16, 24, 32px)
- **Border radius:** use `--radius-sm`, `--radius-md`, `--radius-lg` tokens
- **Shadows:** use `--shadow-low`, `--shadow-high` tokens
- **Colors:** all via CSS variables, no hardcoded hex
- **Buttons:** consistent padding/font-size within each context
- **Animations:** 0.15s duration, intentional only
- **No emoji as UI elements** — use text labels or CSS indicators
- **Loading states** for every async action
- **Every interactive element must work**

After making changes, always:
1. Add/update tests for new endpoints or logic
2. Update README.md and AGENTS.md
3. Bump version (patch for fixes, minor for features)
4. Verify CSS consistency against the design tokens

### Things to Know

- The `_current_theme` global lives in `themes/__init__.py` and is
  accessed via `get_current_theme()`. No circular imports.
- Search is debounced at 400ms. Comment navigation uses `commentNavRef`
  index cycling through a flat comment list.
- `get_branch_commits` uses a single `git log --name-only` call instead
  of N+1 `git diff-tree` subprocesses.

## Commands

```bash
pipx install -e .                    # Install (editable)
diffui                               # Start server (from any git repo)
diffui --open                        # Start + open in browser
diffui --comments                    # Dump comments to stdout
diffui --json                        # Export review session as JSON
pytest                               # Run tests (177 tests)
ruff check diffui/ tests/           # Lint
```

## Testing

Tests cover the pure-function layers (`diff.py`, `git_utils.py`,
`themes/`) and the web server (`server/`).

- `tests/test_diff.py` — 46 tests: line classification, number parsing,
  hunk splitting, prefix stripping, lexer selection, token color,
  word diff ranges, pair diff lines
- `tests/test_events.py` — 24 tests: change classification (source files,
  git paths, comments, mixed, empty, dedup), watch filter (accept/reject
  for source, pyc, git paths, unrelated dirs), SSE broadcast, WebSocket
  broadcast delivery
- `tests/test_git_utils.py` — 31 tests: short_name, _safe_name, JSON
  load/save roundtrips, diff_stat counting, resolve_repos,
  get_diff_numstat, get_blame, session persistence
- `tests/test_highlight.py` — 18 tests: highlight_line_html escaping and
  coloring, _apply_word_highlights with spans/entities/malformed HTML,
  parse_diff_to_json structure, highlight_file_to_json
- `tests/test_server.py` — 50 tests: CSS vars generation, all API routes
  (repos, branch, commits, files, diff, themes, settings, comments CRUD,
  comment resolution toggle, review toggle, static files, JSON export),
  comment categories, code suggestions, blame, preview, review summary,
  session persistence, WebSocket connect and ping/pong, risk scoring
  (migration, config, deletion, test removal, churn patterns), agent
  and explain status endpoints
- `tests/test_themes.py` — 8 tests: all themes have valid hex colors,
  unique names, syntax maps; theme state get/set

## Linting

Uses ruff with: pycodestyle, pyflakes, isort, pyupgrade, bugbear,
simplify, ruff-specific rules.

## State Files

All in `~/.config/diffui/`:

| File | Scope | Format |
| --- | --- | --- |
| `settings.json` | Global | `{theme, editor, view_mode, user_name, agent_cli}` |
| `{repo}/{branch}/reviewed.json` | Per-branch | `{"path": mtime}` |
| `{repo}/{branch}/comments.json` | Per-branch | `{"path": [{...}]}` |
| `{repo}/{branch}/session.json` | Per-branch | `{activeFile, diffMode, ...}` |

Comment objects: `id` (UUID), `file_path`, `file_line_num`, `line_text`,
`comment`, `author`, `author_type`, `timestamp`, `status` (open/resolved),
`category` (bug/suggestion/nit/question), `suggestion` (proposed code),
`replies[]`.

Reply objects: `text`, `author`, `author_type`.

Session objects: `activeFile`, `diffMode`, `showFileTree`, `showReviewed`,
`scrollPositions` (map of file path to scroll offset).

## Adding a Theme

1. Add a `Theme(...)` instance in `themes/definitions.py`
2. Add it to the `ALL_THEMES` list at the bottom
3. Run `pytest tests/test_themes.py` to verify colors and CSS generation
