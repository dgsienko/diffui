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
├── git_utils.py        # Git subprocess helpers, state persistence, repo discovery
├── server/             # FastAPI backend (web UI)
│   ├── app.py          # App factory — mounts routes, static files, SSE poller
│   ├── events.py       # SSE endpoint + background poller (3s git/file/comment mtime checks)
│   ├── highlight.py    # Pygments-to-HTML adapter, word highlight overlay
│   ├── routes_*.py     # API routes (repos, diffs, comments, review, settings)
│   ├── state.py        # AppState singleton — shared server state
│   └── theme_css.py    # generate_css_vars(theme) — CSS custom properties
├── static/             # Preact frontend (no build step, ESM imports via importmap)
│   ├── app.js          # Root component, state management, SSE client, keyboard shortcuts
│   ├── components/     # TopBar, FileTabs, DiffViewer, SplitDiffViewer,
│   │                   #   FullFileViewer, FileTree, CommentBox, CommentDisplay,
│   │                   #   SearchBar, SettingsPanel, Minimap, ShortcutOverlay, Toast
│   ├── index.html      # Shell page with importmap for preact/htm CDN
│   └── style.css       # All styles via CSS custom properties (themed)
└── themes/
    ├── __init__.py     # Theme state (get/set_current_theme), re-exports
    ├── theme.py        # Theme dataclass (30+ color fields)
    ├── definitions.py  # 10 theme instances with Pygments token color maps
    └── css.py          # generate_css(theme) — Textual CSS template
```

### Shared Patterns

- **Multi-repo discovery** — `resolve_repos()` in `git_utils.py` scans
  the parent directory for sibling git repos. Both frontends use this.
- **Branch-scoped state** — reviewed status and comments stored at
  `~/.config/diffui/{repo}/{branch}/`. `get_repo_root()` and
  `_cached_current_branch()` are `lru_cache`'d.
- **Comment threads** — comments have `id` (UUID), `author`/`author_type`
  fields. Replies are structured dicts. Edit locking: user content is
  editable until an agent replies to the thread.
- **Word-level diff** — `pair_diff_lines` matches consecutive remove/add
  pairs and `word_diff_ranges` uses `difflib.SequenceMatcher` to find
  changed word spans.
- **Worktree support** — `get_git_dir()` resolves the actual `.git`
  directory for both regular repos and worktrees.

### Web UI Patterns

- **SSE live updates** — `events.py` polls git state every 3s in a
  background thread, pushes events to connected `EventSource` clients.
- **Diff caching** — server-side `_diff_cache` keyed by
  `(repo, merge_base, path, view, mtime)`. Client-side `diffCache` Map
  for instant tab switching with stale-while-revalidate.
- **Scroll persistence** — client saves/restores scroll positions per
  file in a Map.
- **Theme switching** — server generates CSS custom properties from
  Theme dataclass fields. Client injects a `<style>` tag.
- **No build step** — Preact + HTM loaded via importmap from CDN. All
  frontend ships as plain `.js`/`.css`/`.html` in the Python package.

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
- Search is debounced at 400ms. Comment navigation uses a simple index
  counter (`_comment_nav_index`).
- `FullFileViewer` uses `_FileLineStatic` (single Static per line) for
  performance. `DiffViewer` uses `DiffLine` (Horizontal with gutter +
  code split) for proper line wrapping.

## Commands

```bash
pipx install -e .                    # Install (editable)
diffui                               # Web UI (from any git repo)
diffui --open                        # Web UI + open in browser
diffui-tui                           # Terminal UI
diffui --comments                    # Dump comments to stdout
pytest                               # Run tests (122 tests)
ruff check diffui/ tests/           # Lint
```

## Testing

Tests cover the pure-function layers (`diff.py`, `git_utils.py`,
`themes/`) and the web server (`server/`). No Textual app tests —
would require `app.run_test()` with a headless terminal.

- `tests/test_diff.py` — 49 tests: line classification, number parsing,
  hunk splitting, prefix stripping, lexer selection, syntax highlighting,
  word diff ranges, pair diff lines
- `tests/test_git_utils.py` — 24 tests: short_name, _safe_name, JSON
  load/save roundtrips, diff_stat counting, resolve_repos, get_diff_numstat
- `tests/test_highlight.py` — 19 tests: highlight_line_html escaping and
  coloring, _apply_word_highlights with spans/entities/malformed HTML,
  parse_diff_to_json structure, highlight_file_to_json
- `tests/test_server.py` — 14 tests: CSS vars generation, all API routes
  (repos, branch, commits, files, diff, themes, settings, comments CRUD,
  review toggle, static files)
- `tests/test_themes.py` — 16 tests: all themes have valid hex colors,
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

Comment objects: `id` (UUID), `file_path`, `file_line_num`, `line_text`,
`comment`, `author`, `author_type`, `timestamp`, `replies[]`.

Reply objects: `text`, `author`, `author_type`.

## Adding a Theme

1. Add a `Theme(...)` instance in `themes/definitions.py`
2. Add it to the `ALL_THEMES` list at the bottom
3. Run `pytest tests/test_themes.py` to verify colors and CSS generation
