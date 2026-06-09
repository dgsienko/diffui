# diffui

UI for reviewing AI agent diffs. Two frontends sharing the same backend:
- **Web UI** (`diffui`) — FastAPI + Preact, opens in browser
- **TUI** (`diffui-tui`) — Textual, runs in terminal

## Tech Stack

- **Python 3.10+**
- **FastAPI + uvicorn** (web UI server)
- **Preact + HTM** (web UI frontend, no build step)
- **Textual** (TUI framework)
- **Pygments** for syntax highlighting
- **watchfiles** for real-time filesystem watching (Rust-backed FSEvents/inotify)
- Git operations via `subprocess` (no gitpython dependency)
- Installed globally via `pipx install -e .`

## Architecture

```text
diffui/
├── cli.py              # Web UI entry point — starts FastAPI server
├── cli_tui.py          # TUI entry point — launches Textual app
├── app.py              # Textual TUI app class
├── widgets.py          # TUI widget classes
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
│   ├── routes_diff.py      # Diff, files, blame, and preview endpoints
│   ├── routes_repo.py      # Repo listing and switching
│   ├── routes_review.py    # Review toggle and summary export
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
│   │                   #   CommentDisplay, SearchBar, SettingsPanel,
│   │                   #   Minimap, ShortcutOverlay, Toast,
│   │                   #   CommandPalette, CompletionScreen, PreviewViewer
│   ├── index.html      # Shell page with importmap for preact/htm CDN
│   └── style.css       # All styles via CSS custom properties (themed)
└── themes/
    ├── __init__.py     # Theme state (get/set_current_theme), re-exports
    ├── theme.py        # Theme dataclass (30+ color fields)
    ├── definitions.py  # 15 theme instances with Pygments token color maps
    └── css.py          # generate_css(theme) — Textual CSS template
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
- **Agent orchestration** — `/api/agent/run` spawns `claude -p` with
  open comments. `/api/agent/status` polls for completion. Frontend
  shows a pulsing "Send to agent" button with status. The agent modifies
  `comments.json` and source files; watchfiles picks up changes.
- **Explain changes** — `/api/explain` spawns `claude -p` to generate
  a self-contained HTML walkthrough at `/tmp/diffui-explain-{branch}.html`.
  `/api/explain/status` polls. Includes TL;DR, file-by-file analysis,
  architecture notes, and risk flags.
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
- **Error handling** — `safeFetch` wrapper shows toast on failed requests.
- **Accessibility** — ARIA labels on selects, `role="tab"` and keyboard
  activation on file tabs, `role="treeitem"` on file tree items, focus
  trapping in settings dialog.

### TUI Patterns

- **Lazy tab loading** — only the active tab builds a DiffViewer. Others
  use `LazyPlaceholder` and compose on activation.
- **Background polling** — `@work(thread=True, exclusive=True)` polls
  git mtimes every 3 seconds. Results posted to main thread via
  `call_from_thread`.
- **Theme switching** — writes CSS to a temp file, copies+reparses the
  stylesheet, calls `stylesheet.update()` on all screens.

### Things to Know

- `_SENTINEL = object()` is used as the default for
  `_refresh_tabs(restore_file=)` to distinguish "auto-detect current
  tab" from "don't restore any tab" (`None`).
- The `_current_theme` global lives in `themes/__init__.py` and is
  accessed by widgets via `get_current_theme()`. No circular imports.
- `_poll_worker` snapshots `self.all_files` at entry to avoid race
  conditions with the main thread.
- Textual's `OptionList` renders options as Rich renderables in a single
  panel, not as individual widgets. CSS on dropdown options is limited.
- The review button inside DiffViewer (`#inline-review-btn`) uses
  `variant="default"` with explicit CSS classes to avoid Textual's
  built-in variant styling.
- Search is debounced at 400ms. Comment navigation uses `commentNavRef`
  index cycling through a flat comment list.
- `FullFileViewer` uses `_FileLineStatic` (single Static per line) for
  performance. `DiffViewer` uses `DiffLine` (Horizontal with gutter +
  code split) for proper line wrapping.
- `get_branch_commits` uses a single `git log --name-only` call instead
  of N+1 `git diff-tree` subprocesses.

## Commands

```bash
pipx install -e .                    # Install (editable)
diffui                               # Web UI (from any git repo)
diffui --open                        # Web UI + open in browser
diffui-tui                           # Terminal UI
diffui --comments                    # Dump comments to stdout
diffui --json                        # Export review session as JSON
pytest                               # Run tests (167 tests)
ruff check diffui/ tests/           # Lint
```

## Testing

Tests cover the pure-function layers (`diff.py`, `git_utils.py`,
`themes/`) and the web server (`server/`). No Textual app tests —
would require `app.run_test()` with a headless terminal.

- `tests/test_diff.py` — 48 tests: line classification, number parsing,
  hunk splitting, prefix stripping, lexer selection, syntax highlighting,
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
- `tests/test_server.py` — 34 tests: CSS vars generation, all API routes
  (repos, branch, commits, files, diff, themes, settings, comments CRUD,
  comment resolution toggle, review toggle, static files, JSON export),
  comment categories, code suggestions, blame, preview, review summary,
  session persistence, WebSocket connect and ping/pong
- `tests/test_themes.py` — 12 tests: all themes have valid hex colors,
  unique names, syntax maps; CSS generation; theme state get/set

## Linting

Uses ruff with: pycodestyle, pyflakes, isort, pyupgrade, bugbear,
simplify, ruff-specific rules. Intentional ignores:

- `SIM105` — `try/except/pass` preferred over `contextlib.suppress` for
  single-line Textual queries
- `RUF012` — `BINDINGS` as mutable class attr is a Textual convention

## State Files

All in `~/.config/diffui/`:

| File | Scope | Format |
| --- | --- | --- |
| `settings.json` | Global | `{theme, editor, view_mode, user_name}` |
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
