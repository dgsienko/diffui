# diffui

Terminal UI for reviewing AI agent diffs, built with Python + Textual.

## Tech Stack

- **Python 3.10+**, **Textual 8.x** (TUI framework)
- **Pygments** for syntax highlighting (bundled with Textual)
- Git operations via `subprocess` (no gitpython dependency)
- Installed globally via `pipx install -e .`

## Architecture

```text
diffui/
├── cli.py              # Entry point — --comments dumps to stdout, else launches TUI
├── app.py              # DiffUI app — compose, polling, tab management, event handlers
├── widgets.py          # Widget classes — DiffLine, DiffViewer, FullFileViewer, comments,
│                       #   search, settings panel, file tree sidebar
├── diff.py             # Pure functions — diff parsing, line classification, syntax
│                       #   highlighting, word-level diff ranges
├── git_utils.py        # Git subprocess helpers, state persistence, diff_stat
└── themes/
    ├── __init__.py     # Theme state (get/set_current_theme), re-exports
    ├── theme.py        # Theme dataclass (30+ color fields)
    ├── definitions.py  # 10 theme instances with Pygments token color maps
    └── css.py          # generate_css(theme) — Textual CSS template
```

### Key Patterns

- **Lazy tab loading** — only the active tab builds a DiffViewer. Others
  use `LazyPlaceholder` and compose on activation.
- **Diff caching** — `_diff_cache` keyed by `(file, view, mtime)`. Clears
  when files or git state change.
- **Background polling** — `@work(thread=True, exclusive=True)` polls
  `.git/HEAD`, `.git/index`, and `.git/refs/heads/{branch}` mtimes +
  file stats every 3 seconds. Results posted to main thread via
  `call_from_thread`.
- **Incremental refresh** — when the file list hasn't changed, only tab
  labels and counters update (no DOM teardown).
- **Pre-warm** — after activating a tab, the adjacent tab's diff is
  pre-cached so switching is instant.
- **Theme switching** — writes CSS to a temp file, copies+reparses the
  stylesheet, calls `stylesheet.update()` on all screens.
- **Branch-scoped state** — reviewed status and comments stored at
  `~/.config/diffui/{repo}/{branch}/`. `get_repo_root()` and
  `_cached_current_branch()` are `lru_cache`'d.
- **Comment threads** — comments have `author`/`author_type` fields.
  Replies are structured dicts. Edit locking: user content is editable
  until an agent replies to the thread.
- **Word-level diff** — `pair_diff_lines` matches consecutive remove/add
  pairs and `word_diff_ranges` uses `difflib.SequenceMatcher` to find
  changed word spans, highlighted with `bold underline`.
- **DiffLine as Horizontal** — gutter (fixed 13-char) and code (1fr) are
  separate Static children, so wrapped lines indent correctly past the
  gutter. FullFileViewer uses a lighter single-Static per line for
  performance.

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
diffui                               # Run (from any git repo)
diffui --comments                    # Dump comments to stdout
pytest                               # Run tests (81 tests)
ruff check diffui/ tests/           # Lint
```

## Testing

Tests cover the pure-function layers (`diff.py`, `git_utils.py`,
`themes/`). No Textual app tests — would require `app.run_test()` with
a headless terminal.

- `tests/test_diff.py` — 49 tests: line classification, number parsing,
  hunk splitting, prefix stripping, lexer selection, syntax highlighting,
  word diff ranges, pair diff lines
- `tests/test_git_utils.py` — 17 tests: short_name, _safe_name, JSON
  load/save roundtrips, diff_stat counting
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

Comment objects: `file_path`, `file_line_num`, `line_text`, `comment`,
`author`, `author_type`, `timestamp`, `replies[]`.

Reply objects: `text`, `author`, `author_type`.

## Adding a Theme

1. Add a `Theme(...)` instance in `themes/definitions.py`
2. Add it to the `ALL_THEMES` list at the bottom
3. Run `pytest tests/test_themes.py` to verify colors and CSS generation
