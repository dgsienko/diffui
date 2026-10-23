# diffui

UI for reviewing AI agent diffs. A FastAPI server with a Preact web frontend, plus a Textual terminal client (`diffui --tui`) that talks to the same API.

## Stack

- Python 3.10+, FastAPI + uvicorn, Pygments, watchfiles, fff-search (whole-repo search), Textual + httpx (TUI).
- The frontend has no build step. Preact, HTM, marked and xterm.js load through the importmap in `static/index.html`. Don't add a bundler.
- Git runs through `subprocess` (no gitpython). The agent terminal uses `pty` and `select`.
- Install with `pipx install -e .`.

## Architecture

```text
diffui/
├── cli.py              # Entry point: server, --tui, --comments, --json
├── diff.py             # Pure functions: diff parsing, line classification, word-level ranges
├── git_utils.py        # Git subprocess helpers, blame, state persistence, repo discovery
├── server/             # FastAPI backend
│   ├── app.py          # App factory, _LocalOriginOnly middleware, lifespan (watcher, pollers)
│   ├── events.py       # /api/ws and /api/events, watchfiles watcher with 400ms debounce
│   ├── herdr.py        # herdr CLI calls: agent list, paste, sidebar status
│   ├── highlight.py    # Pygments-to-HTML adapter, word highlight overlay
│   ├── routes_comments.py       # Comment CRUD, bulk resolve, suggestion apply
│   ├── routes_diff.py           # /api/files, diff, file, blame, preview, risk scoring
│   ├── routes_repo.py           # Repo listing and switching, branch, commits
│   ├── routes_review.py         # Reviewed toggle, summary, agent prompt/paste/run, explain
│   ├── routes_agent_terminal.py # PTY agent terminal: /api/agent/start, kill, ws
│   ├── routes_search.py         # /api/search: file names and content
│   ├── routes_settings.py       # Settings, editor open, session
│   ├── fff_index.py    # Resident fff index of the active repo behind /api/search
│   ├── turns.py        # Last turn: herdr poll, start snapshot, /api/last-turn
│   ├── models.py       # Pydantic request models
│   ├── state.py        # AppState singleton
│   └── theme_css.py    # generate_css_vars(theme)
├── tui/                # Textual client, a thin client of server/
│   ├── app.py          # DiffuiApp: bindings, scopes, review actions, SSE-driven refresh
│   ├── client.py       # LocalServer (uvicorn in a thread) and ApiClient (httpx)
│   ├── diffview.py     # DiffView: virtual-scrolled diff with inline threads, cursor, mouse
│   ├── rows.py         # Row, build_rows, split_pairs
│   ├── unified.py      # Strip for one unified line row
│   ├── split.py        # Strip for one split line row
│   ├── style.py        # Style cache, tints, marker and prefix_fg, code segments with find spans
│   ├── find.py         # Find (matches over rows) and the FindBar widget
│   ├── search.py       # SearchScreen
│   ├── filelist.py     # FileList: tree or risk-ordered files
│   └── screens.py      # Help, comment composer, agent prompt and commit picker
├── static/             # Preact frontend: app.js, components/, lib/ (markdown.js, utils.js), style.css
└── themes/             # Theme dataclass, 16 themes in definitions.py, current-theme state
```

## Shared patterns

- Multi-repo: `resolve_repos()` takes repo paths from the command line. With none, it scans the parent directory for sibling git repos.
- Path containment: `repo_path()` in `git_utils.py` joins a path onto the repo root and raises `PathOutsideRepo` if the result resolves outside it, symlinks included. `app.py` maps that to a 400. Every read and write driven by a request goes through it. A route that only hands the path to git calls `repo_relative()`, which checks the same way and returns the original string. Joining `get_repo_root()` with a request value by hand reaches any file on the machine, because pathlib returns an absolute right-hand operand whole.
- Revisions from a client: a `view` that is none of `all`, `working` or `last-turn` is looked up in `app_state.commits` before it reaches `git diff`. Git reads a leading `--` as an option, so an unchecked value can write files.
- Branch-scoped state: reviewed status, comments and session live in `~/.config/diffui/{repo}/{branch}/`, where `{repo}` and `{branch}` are `_safe_name()` of the repo path and branch. `get_repo_root()` and `_cached_current_branch()` are `lru_cache`'d. `_save_json` writes a temp file and renames it. `_load_json` moves an unparseable file aside to `.corrupt`, so the next save cannot overwrite it.
- Worktrees: `get_git_dir()` resolves the real git dir for regular repos and linked worktrees.
- Comments: `author_type` is `user` or `agent`. `category` is bug, suggestion, nit or question. `status` is open or resolved. The web UI locks a user's comment for editing once an agent replies (`canEdit` in `CommentDisplay.js`). The server does not enforce that. `agentColor()` hashes the author name, so each agent gets its own color.
- Word-level diff: `pair_diff_lines` pairs consecutive removes and adds, and `word_diff_ranges` uses `difflib.SequenceMatcher` for the changed word spans.
- Diff line `index`: `parse_diff_to_json` numbers every line of the diff text, and saved comments anchor on that number. `split_into_hunks` returns the lines before the first `@@` as a pseudo hunk. `parse_diff_to_json` emits neither that hunk nor the `@@` lines, but both still advance `index`. Skipping the count shifts every anchor. `file_note` (from `file_change_note`) is set when the header holds a rename, mode change, new or deleted file, or binary marker.
- `html=0` on `/api/diff` and `/api/file` skips Pygments HTML and word highlights. The TUI sends it and highlights `text` itself.
- Settings: `SettingsUpdate` in `models.py` limits `editor` to code, cursor, vim or nvim and `agent_cli` to claude, codex, opencode or cursor. A new agent CLI also needs an entry in `_AGENT_CMDS` (`routes_review.py`) and `_INTERACTIVE_CMDS` (`routes_agent_terminal.py`).

## Server patterns

- Events: `events.py` serves a WebSocket (`/api/ws`) and an SSE stream (`/api/events`). The web client uses the WebSocket and falls back to SSE when it closes. Both carry `connected`, `files_changed`, `git_changed` and `comments_changed`. `watchfiles` watches the repo, the git dir and the comments file with a 400ms debounce. `_bg_tasks` keeps background tasks from being garbage collected. `start_poller` runs from the lifespan handler, so it and `_do_restart` can call `asyncio.get_running_loop()`.
- Git dir boundary: `_classify_changes` compares against the git dir plus a separator. A bare `startswith` also matches `.gitignore` and `.github/`, which turns a workflow edit into a full `reload_repo_state()`.
- The watcher follows the branch: `_watch_loop` snapshots the comments path when it starts, so a branch switch (`git_changed`) restarts it. `reload_repo_state()` also re-reads comments, so `_apply_state_updates` adds `comments_changed` to the broadcast when they differ. Without it, clients keep a stale thread.
- Diff caching: server-side `_diff_cache` is keyed by `(repo, merge_base, path, view:context:whitespace, mtime)` and holds one entry per path and view key. The web client keeps a `diffCache` Map and clears it on `files_changed` and `git_changed`. `AppState.numstat` refreshes on `reload_repo_state` and on `files_changed`.
- Auto-unreview: `_invalidate_stale_reviews()` in `events.py` unreviews files whose mtime no longer matches the stored one, on both `files_changed` and `git_changed`.
- Risk scoring: `_score_risk()` in `routes_diff.py` turns path patterns, config extensions, deletions, churn and test removal into a `risk_level`. `/api/files?order=risk` sorts by its score.
- Review counts: `AppState.review_files`, `reviewed_count` and `open_comments()` feed the progress bar, the summary, the agent prompt and the herdr sidebar, so they all count the same files. `diffui --json` builds the same file set without `AppState`.
- Ignore patterns: `.diffuiignore` in the repo root uses fnmatch syntax. `/api/files` marks matches `ignored: true` and drops them when `hide_ignored` is set. The agent context still includes them.
- Agent orchestration: the confirm dialog calls `/api/agent/start`, which only queues a start. The agent spawns when the client opens `/api/agent/ws` and sends `init` with the terminal size, so the PTY begins at the right dimensions. The agent's TUI streams to the `AgentTerminal` panel. Output goes into a 64KB buffer that replays on reconnect. Three seconds without output after activity sends an `idle` message. `_build_agent_context` writes the prompt context file. `/api/agent/run` and `/api/agent/status` are the non-terminal path. The web UI does not call them.
- herdr: inside a herdr pane (`HERDR_WORKSPACE_ID` set), `/api/agent/prompt` returns the workspace's agent as `herdr_agent`, and the confirm dialog calls `/api/agent/paste` in place of `/api/agent/start`. The prompt goes to that pane as one bracketed paste. `report_status` sets two sidebar tokens after each state change: `comments=N open` and `reviewed=☑ N/M`. An empty value clears a token. `clear_status` removes both on shutdown. Tests run a fake `herdr` from `PATH`.
- Last turn: `view=last-turn` diffs the tree saved when an agent's latest turn started against the worktree as it is now. `turns.py` polls `herdr agent list` every second, only when `HERDR_WORKSPACE_ID` is set and `herdr` is on `PATH`. It counts the agents whose `foreground_cwd` (else `cwd`) is inside the repo, in any workspace. `TurnTracker` fires on the sample where the repo goes from resting (`idle`, `done`, or no agent) to `working`. A `blocked` or unknown agent is mid-turn, so working after it starts nothing, and the first sample after startup never fires. On the edge `snapshot_worktree` copies the real index to a temp file, runs `git add -A` and `git write-tree` against the copy, and `write_turn_tree` stores the tree under `refs/worktree/diffui/last-turn`. That ref is per linked worktree and survives a restart. `AppState.last_turn` holds the base tree, a fresh tree of the worktree and `git diff --numstat` between them. `reload_last_turn` only marks it stale. The next read of `last_turn` snapshots, so file events while an agent writes cost nothing until a client asks for the view. Each file list and diff comes from one pair of trees, untracked files included. `GET /api/last-turn` returns the reason an empty view is empty. Limits: herdr flips to `working` a moment after the agent starts writing, and the poll adds up to a second, so those first writes sit in the base tree and do not show. A turn that changes nothing still replaces the previous base.
- Search: `GET /api/search?q=&view=&scope=` returns `files`, `hits` (`path`, `line`, `text`, read from the working tree, case-insensitive, at most `MAX_HITS` = 200) and `truncated`. Files and hits both carry `changed`, whether `view` lists the file. `scope=changed`, the default, covers the files `view_files(view)` lists, minus `.diffuiignore` matches. It matches names as a substring or in-order letters, best first, adds fff's fuzzy matches so a typo still finds its file, reads the first 1 MB of each file and skips binary ones. `scope=all` searches the whole repo through fff, which skips `.gitignore`d and binary files and does not apply `.diffuiignore`. fff's fuzzy name matches are capped at `FILE_CAP` = 30.
- fff index: `fff_index.finder()` hands out one `FileFinder` for the active repo under a lock, since sync routes run in a threadpool. The first search that needs it builds it, never startup, with `watch=False`, because `events.py` already watches the tree. `_apply_state_updates` calls `mark_stale()` on `files_changed` and `git_changed`, and the next `finder()` rescans before it hands the index out. The index is dropped when the repo changes (`switch_repo`, or a different `get_repo_root()`) and closed in the lifespan shutdown. A search that arrives inside the 400ms debounce misses the write, and the next keystroke finds it. `/api/search` lowercases the query because fff matches a lowercase query case-insensitively. `multi_grep` takes it as plain text where `grep` would read a `*.py` word as a path filter. fff's fuzzy name match returns something for almost any query, so `_fuzzy_names` keeps only scores within 75% of the best and above 8 per character of the longest word.
- Markdown is sanitized: `renderMd` in `lib/markdown.js` runs marked's output through an allowlist of tags, attributes and URL schemes before it reaches `dangerouslySetInnerHTML`. marked emits raw HTML, and comment bodies, agent replies and previewed `.md` files all come from outside. Without the allowlist, a branch under review can run script in the diffui origin. Diagram blocks go to kroki.io, the one call that leaves the machine.
- Explain: `/api/explain` spawns the configured agent CLI to write an HTML walkthrough to the temp dir. `/api/explain/status` polls it. `/api/explain/view` serves the result and refuses a path outside the temp dir.
- `_LocalOriginOnly` in `app.py` returns 403 (1008 on a WebSocket) unless Host is `localhost` or `127.0.0.1` and any Origin matches Host. Tests build clients with `base_url="http://localhost"` and connect WebSockets to `ws://localhost`.

## Web UI patterns

- `treeOrder()` in `FileTree.js` gives the file order that prev/next file and next-unreviewed follow. `_order_files` in `routes_diff.py` mirrors it for the TUI. Sort by risk turns the tree into one flat list.
- The top bar holds navigation and global actions. `FileHeader` above the active viewer holds the per-file ones (view mode, whitespace, blame, resolve all, Mark reviewed).
- `FullFileViewer` renders a window of lines. Hunk blocks use `content-visibility: auto`.
- Search is `SearchDialog`, opened with `/` or the command palette. It calls `/api/search` 150ms after the last keystroke, aborts the request it replaces, and `tab` switches `scope`. `handleSearchOpen` in `app.js` opens a hit in the diff and scrolls to the line the diff shows nearest to it (`nearestNewLine`). A file outside the diff sets `browsing` and opens in `FullFileViewer` with `readOnly`, because the server reports an unchanged file as all added. `browsing` swaps `FileHeader` for a short one, makes `handleToggleReview` return, stops `fetchFiles` from resetting the active file, and keeps `activeFile` out of the session save. It ends when the file joins the diff or another file is picked.
- Keep the accessibility basics: `role="treeitem"` on tree items, focus trapping in the settings dialog, `:focus-visible` outlines on buttons, and `+`/`-` prefixes next to the diff colors.

### Design system

Frontend changes follow these rules:

- Spacing: 4/8pt grid only (4, 8, 12, 16, 24, 32px).
- Border radius: `--radius-sm`, `--radius-md`, `--radius-lg`.
- Shadows: `--shadow-low`, `--shadow-high`.
- Colors: all through CSS variables, no hex or rgba outside `:root`. The server generates them from the `Theme` fields.
- Buttons: consistent padding and font size within each context. One filled `btn-primary` per area ("Send to agent" in the top bar, "Mark reviewed" in the file header). Every other action is a quiet `btn`: no border, muted text, `--hover-bg` on hover. Mode toggles are one segmented control.
- Fonts: `--font-ui` for chrome (bars, buttons, tree, panels, dialogs, toasts), `--font-mono` for code, line numbers, diff paths and comment code blocks.
- Borders: only where they carry structure (the bar bottom edge, the tree/diff divider). Use spacing or a background shift elsewhere.
- Animations: 0.15s, only where they mean something.
- No emoji as UI elements. Use text labels or CSS indicators.
- Every async action has a loading state. Every interactive element works.

After a change:

1. Add or update tests for new endpoints or logic.
2. Update README.md and AGENTS.md.
3. Bump the version in `pyproject.toml` (patch for fixes, minor for features).
4. Check CSS against the design tokens.

## Terminal UI patterns

- Thin client: the TUI holds no review logic. Comments, reviewed state, risk scores, file order, the agent prompt, the herdr paste and the herdr status all stay in `server/`. When the TUI needs data the API lacks, add or extend an endpoint. Pygments highlighting of the `text` the diff endpoint returns is the one thing computed client-side, because it is presentation. `_next_unreviewed()` in `tui/app.py` is the exception: it takes the first unreviewed file in the order `/api/files` returned.
- Everything the server returns passes through `_clean` in `client.py`, which strips control characters. Diff text and comments come from the branch under review, and an escape sequence in them would reach the terminal as a command. A new `ApiClient` method must return through `_json`.
- `LocalServer` runs `create_app` under uvicorn in a background thread so the lifespan starts the watcher and herdr reporting. The client uses `http://localhost:<port>`, which `_LocalOriginOnly` accepts.
- Layout: the diff is on the left and `FileList` on the right. `z` hides the list. Below 110 columns, `HORIZONTAL_BREAKPOINTS` on `DiffuiApp` adds `-narrow` to the screen and the list stacks below the diff. `DiffuiApp.view` is the scope (`all`, `working`, `last-turn` or a commit sha) and goes to `/api/files`, `/api/diff`, `/api/file` and `/api/search` as `view`. `u`, `b` and `t` switch it and `C` picks a commit. The header shows it, and an empty last-turn scope shows the server's reason.
- File order: `/api/files?order=tree|risk`. `hide_ignored` drops `.diffuiignore` matches. Each entry carries `dir` and `open_comment_count`.
- `DiffView` is a `ScrollView` that renders rows on demand. Pygments runs on a row the first time it is drawn, so a few thousand lines open at once. A comment's `line_index` is the diff line's `index`, the same anchor the web UI uses. Threads whose line left the diff are listed after the last hunk.
- Live updates come from the `/api/events` SSE stream. The TUI refetches files, the diff or comments per event, so an agent writing `comments.json` shows up without a keypress.
- Open in browser (`o`) writes `activeFile` to `/api/session`, which the web UI restores on load.
- Range comments send what the web UI sends for a selection across lines: `line_index` is the first diff line's `index`, `sel_end_index` the last, `sel_start` 0, `sel_end` the last line's text length, and `selected_text` the lines joined by newlines. Threads anchor under the first line. A single line sends none of the selection fields.
- Split view: `build_rows(..., split=True)` uses `split_pairs` to pair a run of removes with the run of adds that follows, as `splitHunkLines` does in `SplitDiffViewer.js`. A split `Row` has `old` and `new` (a context line is both), and `row.line` is the new one when there is one. `DiffView.target` picks the line a comment goes against. `side` is None for the keyboard (new side), and `tab` or the pointer position sets it. The old side is used for a removed line. A range follows one side and sorts its lines by `index`, since paired rows are not in diff order. Split needs `SPLIT_MIN_WIDTH` columns in the diff pane. Below that, `|` keeps unified and says so, and a resize that crosses the width rebuilds the rows. Long lines are cut at the side's edge, because split has no horizontal scroll.
- Find in file is client-side: `Find` matches `code_of(line)` of each row, case-insensitive, and `code_segments` draws the spans. Once the bar closes with a query still set, `n` / `N` step the matches and `esc` clears them. The `find_step` and `clear_find` bindings sit before the thread ones, and `check_action` enables them only while matches show, so `n` is next thread otherwise.
- Search is `SearchScreen`, which calls `/api/search` 150ms after the last keystroke. `tab` switches `scope` between `changed` and `all`. A hit opens the file, and `DiffView.goto_line` moves to the nearest new-side line when the diff does not show the hit's line.
- Files outside the diff: a result whose path is not in the view's file list sets `DiffuiApp.browsing`. `_load_diff` takes the file from `/api/file` (its `text` per line, since `html` is for the web UI) and wraps it as one hunk of context lines. `DiffView.readonly` then makes `context` return `readonly`, which matches no `c`, `x` or `v` binding, and turns off hover, gutter presses, range selection and split. `check_action` hides Reviewed and Hunks. `_refresh_files` leaves a browsed file open on file events and stops browsing once the file joins the diff. A scope change, or `left` / `right`, returns to the diff's files.
- Hover and drag state live in `DiffView` (`hover`, `range_start`). Hover changes refresh only the affected rows. A press on the number column captures the mouse so the drag keeps tracking outside the widget, and the `Click` that follows the release is swallowed so it cannot open a second composer.
- The footer's leading hints come from `DiffuiApp.check_action`. Bindings share a key and differ in their `'range'`, `'thread'`, `'line'` or `'none'` parameter, and `DiffView.context` picks the one shown. `ContextFooter` fills in the line count, because a `Binding` description is fixed text.

## Things to know

- `is_meta_line` in `diff.py` treats a line as a file header only when it has the `a/`, `b/` or `/dev/null` shape. A deleted YAML separator arrives as `----`, and reading that as a header shifts every line number below it in the hunk.
- `apply_suggestion` checks the target line still matches the comment's `line_text` and refuses a range that covers more than one line.
- `get_branch_commits` gets every commit's file list from one `git log --name-only` call, which avoids an N+1 of `git diff-tree` subprocesses.
- `_parse_numstat` parses every `git diff --numstat` output. `_path_diff` builds every per-path `git diff` call (commit and tree diffs). Reuse them for a new diff variant.
- The default theme is the first entry of `ALL_THEMES` (Graphite). A settings file with no saved theme gets it.

## Commands

```bash
pipx install -e .                    # Install (editable)
diffui                               # Start the server in the current repo
diffui ~/code/a ~/code/b             # Review specific repos
diffui --open                        # Start and open the browser
diffui --tui                         # Terminal UI in the current pane
diffui --comments                    # Dump comments to stdout
diffui --json                        # Export the review session as JSON
pytest                               # Run tests
ruff check .                         # Lint
ruff format --check .                # Format check
git config core.hooksPath .githooks  # Once per clone: enables the pre-push hook
```

CI (`.github/workflows/ci.yml`) runs `ruff check`, `ruff format --check` and `pytest` on Ubuntu and macOS, Python 3.10 and 3.13. The checkout is full-depth because some tests diff the repo against `origin/main`.

`.githooks/pre-push` runs the same three checks, then `scripts/check_suite.py` (the README's Development section describes it). Change what the review looks for in the skills, not in the script.

## Testing

- `tests/conftest.py` points `_CONFIG_ROOT` at a temp dir for the whole session, clears `HERDR_WORKSPACE_ID`, and builds the `temp_repo` fixture (a `feature` branch with a dirty tree and an untracked file). Server tests use a `TestClient` with `base_url="http://localhost"`.
- `tests/test_server.py` covers the routes. Its `fake_herdr` fixture puts a fake `herdr` on `PATH`.
- `tests/test_tui.py` runs the real `DiffuiApp` under `App.run_test()` against a `LocalServer` on `temp_repo`. Tests drive the app with `asyncio.run` and wait with `until()`, because the server reaches the view through the watcher and SSE.
- `test_diff.py`, `test_highlight.py`, `test_git_utils.py`, `test_events.py`, `test_agent_terminal.py` and `test_themes.py` cover the matching modules.
- `test_check_suite.py` covers the verdict parsing and skip paths of `scripts/check_suite.py` with `subprocess` patched. It never starts `claude`.

## State files

All in `~/.config/diffui/`:

| File | Scope | Format |
| --- | --- | --- |
| `settings.json` | Global | `{theme, editor, view_mode, user_name, agent_cli, font_size, word_wrap, keybindings}` |
| `{repo}/{branch}/reviewed.json` | Per branch | `{"path": mtime}` |
| `{repo}/{branch}/comments.json` | Per branch | `{"path": [{...}]}` |
| `{repo}/{branch}/session.json` | Per branch | `{activeFile, diffMode, showFileTree, showReviewed, scrollPositions}` |

Comment objects: `id` (UUID), `file_path`, `line_index`, `file_line_num`, `line_text`, `comment`, `author`, `author_type`, `timestamp`, `status`, `category`, `suggestion` (proposed code), `replies[]`. Range comments add `selected_text`, `sel_start` and `sel_end` (character offsets into the code column), and `sel_end_index`, the diff line the range ends on when it spans more than one line. `line_index` is always the line the range starts on, so a multi-line range covers `line_index` at `sel_start` through `sel_end_index` at `sel_end`.

Reply objects: `text`, `author`, `author_type`.

## Adding a theme

1. Add a `Theme(...)` instance in `themes/definitions.py`.
2. Add it to `ALL_THEMES` at the bottom of that file.
3. Run `pytest tests/test_themes.py` to check colors and CSS generation.
