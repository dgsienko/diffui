# diffui

UI for reviewing AI agent diffs. FastAPI backend + Preact frontend,
no build step required, plus a Textual terminal client of the same API.

## Tech Stack

- Python 3.10+
- FastAPI + uvicorn (server)
- Preact + HTM (frontend, no build step)
- Pygments for syntax highlighting
- watchfiles for real-time filesystem watching (Rust-backed FSEvents/inotify)
- xterm.js for interactive agent terminal (loaded via ESM importmap)
- Git operations via `subprocess` (no gitpython dependency)
- PTY-based agent process management (`pty` + `select` stdlib)
- Textual + httpx for the terminal UI (`diffui --tui`)
- Installed globally via `pipx install -e .`

## Architecture

```text
diffui/
├── cli.py              # Entry point: starts FastAPI server
├── diff.py             # Pure functions: diff parsing, line classification, syntax
│                       #   highlighting, word-level diff ranges
├── git_utils.py        # Git subprocess helpers, blame, state persistence,
│                       #   repo discovery, session management
├── server/             # FastAPI backend (web UI)
│   ├── app.py          # App factory: mounts routes, static files, starts watcher
│   ├── events.py       # WebSocket + SSE endpoints, watchfiles-based filesystem
│   │                   #   watcher with 400ms debounce
│   ├── herdr.py        # herdr CLI calls: agent paste, sidebar status
│   ├── highlight.py    # Pygments-to-HTML adapter, word highlight overlay
│   ├── routes_comments.py  # Comment CRUD, suggestion apply endpoint
│   ├── routes_diff.py      # Diff, files, blame, preview, risk scoring
│   ├── routes_repo.py      # Repo listing and switching
│   ├── routes_review.py    # Review toggle, summary export, agent/explain
│   │                       #   orchestration (thread-safe process management)
│   ├── routes_agent_terminal.py # PTY-based interactive agent terminal,
│   │                       #   WebSocket streaming, idle detection
│   ├── routes_settings.py  # Settings, editor open, session persistence
│   ├── models.py       # Pydantic request models for all endpoints
│   ├── state.py        # AppState singleton: shared server state
│   └── theme_css.py    # generate_css_vars(theme): CSS custom properties
├── tui/                # Textual client (`diffui --tui`), a thin client of server/
│   ├── app.py          # DiffuiApp: key bindings, review actions, SSE-driven refresh
│   ├── client.py       # LocalServer (uvicorn in a thread) and ApiClient (httpx)
│   ├── diffview.py     # DiffView: virtual-scrolled unified diff with inline threads
│   ├── filelist.py     # FileList: tree or risk-ordered files
│   └── screens.py      # Help, comment composer and agent prompt dialogs
├── static/             # Preact frontend (no build step, ESM imports via importmap)
│   ├── app.js          # Root component, state management, keyboard shortcuts,
│   │                   #   WebSocket client, session restore
│   ├── lib/            # Shared utilities
│   │   ├── markdown.js #   marked.js wrapper with GFM config
│   │   └── utils.js    #   shortName(), mergeRef(), useResize() helpers
│   ├── components/     # TopBar, FileHeader, DiffViewer, SplitDiffViewer,
│   │                   #   FullFileViewer, FileTree, CommentBox,
│   │                   #   CommentDisplay, CommentsPanel, SearchBar,
│   │                   #   FileFilterBar, LineActions, SettingsPanel,
│   │                   #   Minimap, ShortcutOverlay, Toast,
│   │                   #   CommandPalette, CompletionScreen, PreviewViewer,
│   │                   #   AgentStatusBar, AgentConfirmDialog,
│   │                   #   AgentTerminal, GoToLineDialog
│   ├── index.html      # Shell page with importmap for preact/htm CDN
│   └── style.css       # All styles via CSS custom properties (themed)
└── themes/
    ├── __init__.py     # Theme state (get/set_current_theme), re-exports
    ├── theme.py        # Theme dataclass (30+ color fields)
    └── definitions.py  # 16 theme instances with Pygments token color maps
```

### Shared Patterns

- Multi-repo discovery: `resolve_repos()` in `git_utils.py` scans
  the parent directory for sibling git repos.
- Path containment: `repo_path()` in `git_utils.py` joins a path onto the repo
  root and raises `PathOutsideRepo` if the result resolves outside it, symlinks
  included, which `app.py` maps to a 400. Every read and write driven by a
  request goes through it. A route that only hands the path to git calls
  `repo_relative()`, which checks the same way and returns the original string.
  Joining `get_repo_root()` with a request value by hand reaches any file on the
  machine, because pathlib returns an absolute right-hand operand whole.
- Revisions from a client: a `view` that is neither `all` nor `working` is
  looked up in `app_state.commits` before it reaches `git diff`. Git reads a
  leading `--` as an option, so an unchecked value can write files.
- Branch-scoped state: reviewed status, comments, and session stored
  at `~/.config/diffui/{repo}/{branch}/`. `get_repo_root()` and
  `_cached_current_branch()` are `lru_cache`'d. `_save_json` writes a temp
  file and renames it. `_load_json` moves an unparseable file aside to
  `.corrupt`, so the next save cannot overwrite it.
- Comment threads: comments have `id` (UUID), `author`/`author_type`
  fields, `category` (bug/suggestion/nit/question), optional `suggestion`
  (proposed code), and `status` (open/resolved). Replies are structured
  dicts. Edit locking: user content is editable until an agent replies.
  Threads are collapsible in the web UI.
- Multi-agent identity: agent authors get unique colors via a name
  hash. Multiple agents reviewing the same branch appear as distinct
  identities in comment headers and reply threads.
- Word-level diff: `pair_diff_lines` matches consecutive remove/add
  pairs and `word_diff_ranges` uses `difflib.SequenceMatcher` to find
  changed word spans.
- Worktree support: `get_git_dir()` resolves the actual `.git`
  directory for both regular repos and worktrees.

### Web UI Patterns

- WebSocket + SSE: `events.py` provides a WebSocket endpoint
  (`/api/ws`) for bidirectional communication. Client prefers WebSocket
  and falls back to SSE (`/api/events`) if the connection closes.
  Both use `watchfiles` (Rust-backed FSEvents/inotify) for real-time
  filesystem watching with 400ms debounce. Watches repo dir, `.git`
  dir, and comments file. Background tasks use `_bg_tasks` set to
  prevent garbage collection. `start_poller` runs from the lifespan handler,
  so both it and `_do_restart` can use `asyncio.get_running_loop()`.
- Git dir boundary: `_classify_changes` compares against the git dir plus a
  separator. A bare `startswith` also matches `.gitignore` and `.github/`,
  which turns a workflow edit into a full `reload_repo_state()`.
- Watcher follows the branch: comments live in a per-branch dir, and
  `_watch_loop` snapshots that path when it starts, so a branch switch
  (`git_changed`) restarts the watcher. `reload_repo_state()` also re-reads
  comments, so `_apply_state_updates` adds `comments_changed` to the broadcast
  when they actually differ, so the client does not sit on a stale thread
  while the server has the new one.
- Diff caching: server-side `_diff_cache` keyed by
  `(repo, merge_base, path, view, mtime)`. Client-side `diffCache` Map
  for instant file switching with stale-while-revalidate. Numstat is
  cached in `AppState` and refreshed on `reload_repo_state`.
- Virtual scrolling: `FullFileViewer` uses windowed rendering (only
  visible lines + buffer in DOM). Hunk blocks in unified/split views
  use `content-visibility: auto` for browser-native off-screen culling.
- Scroll persistence: client saves/restores scroll positions per
  file in a Map. Comment dropdown navigation scrolls to the exact line
  using `data-line-new` attributes for O(1) DOM lookup.
- Risk scoring: `_score_risk()` in `routes_diff.py` assigns
  risk_level (low/medium/high) based on file patterns (migrations,
  configs, large deletions, test removal, high churn). Shown as colored
  dots on tree items, with the level in the tooltip. Sort-by-risk toggle via command
  palette.
- Agent orchestration: confirmation dialog shows agent name, comment
  count, and behavior summary. `/api/agent/start` spawns the configured
  agent CLI in interactive mode via PTY (`pty.openpty()`). The agent's
  full TUI streams to a slide-up terminal panel (`AgentTerminal`) via
  a dedicated WebSocket (`/api/agent/ws`). Users can answer permission
  prompts, navigate multi-choice menus, and interact directly. Output
  is buffered (64KB ring buffer) for reconnect replay. Idle detection
  (3s of no output after activity) updates status to "Done — waiting
  for input". Stop/Close buttons in terminal header. Context built by
  `_build_agent_context` with full diffs, review state, and thread
  history. Agent CLI configurable in settings (Claude Code, Codex,
  OpenCode, Cursor Agent). Legacy polling endpoints (`/api/agent/run`,
  `/api/agent/status`) still available for non-terminal use.
- herdr: inside a herdr pane (`HERDR_WORKSPACE_ID` set), `/api/agent/prompt`
  returns the workspace's agent as `herdr_agent`, and the confirm dialog
  calls `/api/agent/paste` in place of `/api/agent/start`. The prompt goes to
  that pane as one bracketed paste. `report_status` pushes the open comment
  and reviewed counts to the herdr sidebar after each state change, and
  `clear_status` removes them on shutdown. Tests run a fake `herdr` from
  `PATH`.
- Markdown is sanitized: `renderMd` in `lib/markdown.js` runs marked's output
  through an allowlist of tags, attributes and URL schemes before it reaches
  `dangerouslySetInnerHTML`. marked emits raw HTML, and comment bodies, agent
  replies and previewed `.md` files all come from outside, so without the
  allowlist a branch under review can run script in the diffui origin. Diagram
  blocks are sent to kroki.io, the one call that leaves the machine.
- Explain changes: `/api/explain` spawns the configured agent CLI
  to generate a self-contained HTML walkthrough. `/api/explain/status`
  polls. `/api/explain/view` serves the result as a localhost page
  (path-traversal guarded to tempdir). Top bar button + status bar link.
- Ignore whitespace: `ignore_whitespace` query param on diff
  endpoints passes `-w` to `git diff`. Frontend toggle (`w` key).
- Ignore patterns: `.diffuiignore` file in repo root, fnmatch
  syntax. Files marked `ignored: true` in `/api/files`, hidden by
  default in UI but always included in agent context.
- Bulk resolve: `/api/comments/bulk-resolve` with optional
  `file_path` filter and `action` (resolve/reopen). Used by command
  palette, comments panel header, and the file header.
- Font size / word wrap: `font_size` and `word_wrap` persisted in
  settings. Font size sets `--code-font-size` CSS variable. Word wrap
  adds `.word-wrap-enabled` class to `<html>`, uses `pre-wrap` on
  `.diff-code` with flex-shrink-0 gutter to preserve line numbers.
- Custom keybindings: `keybindings` dict in settings maps action
  IDs to key strings. SettingsPanel has a collapsible rebinding UI with
  key capture. ShortcutOverlay and CommandPalette reflect overrides.
- Blame gutter: toggleable per-file. Fetches `git blame --porcelain`
  via `/api/blame/{path}`. Results cached client-side in a `Map`.
- Preview mode: toggleable for `.md` and image files. Backend uses
  `mimetypes.guess_type` for image detection with 10MB size cap. Markdown
  rendered via `marked.js` through shared `lib/markdown.js`.
- Layout: one top bar (explorer toggle, repo and branch, connection dot, view
  filter, review progress, then Search files, Comments, Explain changes,
  Shortcuts, Settings and Send to agent). `App` renders a single `FileHeader`
  above the active viewer with the path breadcrumb, the Unified/Split/File
  control, Whitespace, Hide reviewed, Blame, context, Resolve all and Mark
  reviewed. The file tree is the only file navigator, and `treeOrder()` in
  `FileTree.js` gives the order that prev/next file and next-unreviewed follow.
  Sort by risk turns the tree into one flat list in risk order.
- Diff file headers: `split_into_hunks` returns the lines before the first `@@`
  as a pseudo hunk. `parse_diff_to_json` does not emit that hunk or the `@@`
  line of each hunk, but both still advance the line `index`, which saved
  comments anchor on. `file_note` (from `file_change_note`) is set when the
  header holds a rename, mode change, new or deleted file, or binary marker.
  The unified view shows each hunk header once, in the collapsible bar. The
  split view prints it in the left pane only.
- Theme switching: server generates CSS custom properties from
  Theme dataclass fields. Client injects a `<style>` tag. All colors
  use CSS variables, with no hardcoded values.
- No build step: Preact + HTM loaded via importmap from CDN. All
  frontend ships as plain `.js`/`.css`/`.html` in the Python package.
- Shared utilities: `lib/markdown.js` provides `renderMd()` used by
  both `CommentDisplay` and `PreviewViewer`. `lib/utils.js` provides
  `shortName()`, `mergeRef()`, and `useResize(initial, min, max, axis)`
  hook used by FileTree, CommentsPanel, and AgentTerminal.
- Auto-unreview: files modified after being marked reviewed are
  automatically unreviewed. `_invalidate_stale_reviews()` in `events.py`
  compares stored mtime against current on both `files_changed` and
  `git_changed` events.
- Error handling: `safeFetch` wrapper shows toast on failed requests.
- Accessibility: ARIA labels on selects, `role="treeitem"` and keyboard
  activation on file tree items, focus trapping in settings dialog, `:focus-visible` outlines on all buttons,
  bold color-coded `+`/`-` diff prefixes for color-blind users.

### Terminal UI Patterns

- Thin client: the TUI holds no review logic. Comments, reviewed state, risk
  scores, file order, next-unreviewed, the agent prompt, the herdr paste and the
  herdr status all stay in `server/`. When the TUI needs data the API lacks, add
  or extend an endpoint. Pygments highlighting of the `text` the diff endpoint
  returns is the one thing computed client-side, because it is presentation.
- `LocalServer` runs `create_app` under uvicorn in a background thread so the
  lifespan starts the watcher and herdr reporting. The client must use
  `http://localhost:<port>`, which `_LocalOriginOnly` accepts.
- File order: `/api/files?order=tree|risk` mirrors `treeOrder()` in
  `FileTree.js`, and `/api/files/next-unreviewed` gives the file the web UI
  advances to after Mark reviewed. `hide_ignored` drops `.diffuiignore` matches.
  Each entry carries `dir` and `open_comment_count`.
- `DiffView` is a `ScrollView` that renders rows on demand. Pygments runs on a
  row the first time it is drawn, so a few thousand lines open at once.
  A comment's `line_index` is the diff line's `index`, the same anchor the web
  UI uses. Threads whose line left the diff are listed after the last hunk.
- Live updates come from the `/api/events` SSE stream. The TUI refetches files,
  the diff or comments per event, so an agent writing `comments.json` shows up
  without a keypress.
- Open in browser writes `activeFile` to `/api/session`, which the web UI
  restores on load.
- Range comments send what the web UI sends for a selection across lines:
  `line_index` is the first diff line's `index`, `sel_end_index` the last,
  `sel_start` 0, `sel_end` the last line's text length, and `selected_text` the
  lines joined by newlines. Threads anchor under the first line. A single line
  sends none of the selection fields.
- Hover and drag state live in `DiffView` (`hover`, `anchor`). Hover changes
  refresh only the affected rows. A press on the number column captures the
  mouse so the drag keeps tracking outside the widget, and the `Click` that
  follows the release is swallowed so it cannot open a second composer.
- The footer's leading hints come from `DiffuiApp.check_action`: bindings share
  a key and differ in their `'range'`, `'thread'`, `'line'` or `'none'`
  parameter, and `DiffView.context` picks the one shown. `ContextFooter` fills
  in the line count, because a `Binding` description is fixed text.

### Design System

All frontend changes must follow these rules:

- Spacing: 4/8pt grid only (4, 8, 12, 16, 24, 32px)
- Border radius: use `--radius-sm`, `--radius-md`, `--radius-lg` tokens
- Shadows: use `--shadow-low`, `--shadow-high` tokens
- Colors: all via CSS variables, zero hex/rgba outside `:root`
- Buttons: consistent padding/font-size within each context. One filled
  `btn-primary` per area ("Send to agent" in the top bar, "Mark reviewed" in the
  file header). Every other action is a quiet `btn`: no border, muted text,
  `--hover-bg` on hover. Mode toggles are one segmented control.
- Fonts: `--font-ui` for chrome (bars, buttons, tree, panels, dialogs, toasts),
  `--font-mono` for code, line numbers, diff paths and comment code blocks
- Borders: only where they carry structure (the bar bottom edge, the tree/diff
  divider). Use spacing or a background shift elsewhere.
- Animations: 0.15s duration, intentional only
- No emoji as UI elements: use text labels or CSS indicators
- Loading states for every async action
- Every interactive element must work

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
- `is_meta_line` in `diff.py` treats a line as a file header only when it has
  the `a/`, `b/` or `/dev/null` shape. A deleted YAML separator arrives as
  `----`, and reading that as a header shifts every line number below it in the
  hunk.
- `apply_suggestion` checks the target line still matches the comment's
  `line_text` and refuses a range that covers more than one line.
- `get_branch_commits` gets every commit's file list from one
  `git log --name-only` call, avoiding an N+1 of `git diff-tree`
  subprocesses.
- File counts and open comments come from `AppState.review_files`,
  `reviewed_count` and `open_comments()`, so the all-changes progress bar,
  the summary, the agent prompt and the herdr sidebar count the same files.
  `diffui --json` builds the same file set without `AppState`.
- `_LocalOriginOnly` in `app.py` returns 403 unless Host is localhost, so
  tests build clients with `base_url="http://localhost"` and connect
  WebSockets to `ws://localhost`.

## Commands

```bash
pipx install -e .                    # Install (editable)
diffui                               # Start server (from any git repo)
diffui --open                        # Start + open in browser
diffui --tui                         # Terminal UI in the current pane
diffui --comments                    # Dump comments to stdout
diffui --json                        # Export review session as JSON
pytest                               # Run tests
ruff check diffui/ tests/           # Lint
```

## Testing

Tests cover the pure-function layers (`diff.py`, `git_utils.py`,
`themes/`), the web server (`server/`) and the terminal UI (`tui/`).

- `tests/test_diff.py`: line classification, number parsing,
  hunk splitting, prefix stripping, lexer selection, token color,
  word diff ranges, pair diff lines, `file_change_note` (rename, mode,
  new, deleted, binary)
- `tests/test_events.py`: change classification (source files,
  git paths, comments, mixed, empty, dedup), watch filter (accept/reject
  for source, pyc, git paths, unrelated dirs), SSE broadcast, WebSocket
  broadcast delivery, `_apply_state_updates` (git/files/comments changed
  paths, numstat refresh, auto-unreview on mtime mismatch, comments
  announced and watcher restarted on branch switch), watcher
  lifecycle (restart, start_poller)
- `tests/test_git_utils.py`: short_name, _safe_name, JSON
  load/save roundtrips, diff_stat counting, resolve_repos,
  get_diff_numstat, get_blame, session persistence, get_file_mtime,
  repo_has_changes, get_file_content error handling
- `tests/test_agent_terminal.py`: PTY helpers (_flush_buffer,
  _read_pty, _write_pty, _resize_pty, _kill_agent, _is_running),
  /api/agent/start endpoint (already running, no comments, unknown CLI,
  spawn success, slave fd cleanup), /api/agent/ws WebSocket (no process,
  buffer replay, output streaming, kill message)
- `tests/test_highlight.py`: highlight_line_html escaping and
  coloring, _apply_word_highlights with spans/entities/malformed HTML,
  parse_diff_to_json structure and line `index` and `file_note`,
  highlight_file_to_json
- `tests/test_server.py`: CSS vars generation, all API routes
  (repos, branch, commits, files, diff, themes, settings, comments CRUD,
  comment resolution toggle, review toggle, static files, JSON export),
  comment categories, code suggestions, blame, preview, review summary
  with comments, session persistence, WebSocket connect and ping/pong,
  risk scoring (migration, config, deletion, test removal, churn),
  agent/explain status and start endpoints, bulk resolve, ignore
  whitespace, pydantic validation, font/wrap/keybinding settings,
  _build_agent_context, _process_status, explain view with temp files,
  repo switch, working files view, diff context/whitespace params,
  editor open endpoint
- `tests/test_tui.py`: runs the real `DiffuiApp` under `App.run_test()` against
  a `LocalServer` on the `temp_repo` fixture. Covers file keys in tree order,
  a comment added from the keyboard stored at the right line, Mark reviewed
  advancing to the next unreviewed file, an external `comments.json` write
  refreshing the view, and `_order_files` for tree and risk order. Tests drive
  the app with `asyncio.run` and poll with `until()`, since the server reaches
  the view through the watcher and SSE.
- `tests/test_themes.py`: all themes have valid hex colors,
  unique names, syntax maps; Graphite first and the default when no theme is
  saved; theme state get/set

## Linting

Uses ruff with: pycodestyle, pyflakes, isort, pyupgrade, bugbear,
simplify, ruff-specific rules.

## State Files

All in `~/.config/diffui/`:

| File | Scope | Format |
| --- | --- | --- |
| `settings.json` | Global | `{theme, editor, view_mode, user_name, agent_cli, font_size, word_wrap, keybindings}` |
| `{repo}/{branch}/reviewed.json` | Per-branch | `{"path": mtime}` |
| `{repo}/{branch}/comments.json` | Per-branch | `{"path": [{...}]}` |
| `{repo}/{branch}/session.json` | Per-branch | `{activeFile, diffMode, ...}` |

Comment objects: `id` (UUID), `file_path`, `file_line_num`, `line_text`,
`comment`, `author`, `author_type`, `timestamp`, `status` (open/resolved),
`category` (bug/suggestion/nit/question), `suggestion` (proposed code),
`replies[]`. Range comments add `selected_text` plus `sel_start`/`sel_end`
(character offsets into the code column) and `sel_end_index`, the diff line
the range ends on when it spans more than one line. `line_index` is always the
line the range starts on, so a multi-line range covers `line_index` at
`sel_start` through `sel_end_index` at `sel_end`.

Reply objects: `text`, `author`, `author_type`.

Session objects: `activeFile`, `diffMode`, `showFileTree`, `showReviewed`,
`scrollPositions` (map of file path to scroll offset).

## Adding a Theme

1. Add a `Theme(...)` instance in `themes/definitions.py`
2. Add it to the `ALL_THEMES` list at the bottom. The first entry (Graphite) is
   the default when settings have no saved theme
3. Run `pytest tests/test_themes.py` to verify colors and CSS generation
