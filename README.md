# diffui

A local code review UI tool with optional AI agent integration.

Review any branch with syntax-highlighted diffs, inline comments, and risk scoring. If you have a coding agent installed locally, you can leave feedback directly on the diff, watch the agent respond, and review the next round of changes in a tight loop without leaving the browser. Better understand changes within your branch via an ai-powered explain feature, as well.

Runs as a local web server with a Preact frontend. No build step, no accounts, and no network required; everything stays on your machine.

## Who is this for

**Working with AI coding agents** — if you use Claude Code, Codex, Cursor, or similar tools and want a better way to review their output than scrolling terminal diffs or waiting for a pushed MR. diffui lets you review locally, leave comments, and send feedback back to the agent before anything hits a remote.

**Reviewing your own work before pushing** — a lightweight local alternative to opening a draft MR just to see your changes in a proper diff UI. Useful when your IDE's diff view doesn't cut it for larger changes or when you want risk scoring, comment threads, or a cross-file overview.

**Terminal-first workflows** — if you spend most of your time in a terminal and want a review UI that fits that flow. diffui runs locally, prints a URL, and works well in terminal browsers or apps that support inline web content.

diffui is not a replacement for GitHub/GitLab code review — it's what you use *before* pushing, to catch issues early and iterate with agents locally.

## Install

```bash
pipx install -e .
```

## Quick start

`cd` into any git repo on a feature branch and run:

```bash
diffui
```

This starts a local server and prints the URL. Open that URL via an external browser or within your terminal application (if supported). You'll see every file changed on the current branch (vs the merge base with main/master) in a tabbed, syntax-highlighted diff viewer.

Sibling repos in the same parent directory are auto-discovered and available via a dropdown for easy repository switching.

### CLI flags

```bash
diffui --open        # Automatically open the URL in an external browser
diffui --comments    # Dump all comments to stdout
diffui --json        # Export review session as structured JSON
```

## Reviewing changes

**Navigation** — files appear as tabs along the top and in a collapsible explorer sidebar (grouped by directory, file type, or change status). Use the arrow keys or click to switch files. `]` jumps to the next unreviewed file.

**Diff modes** — toggle between unified diff, side-by-side split, or full file view using buttons in the toolbar.

**View filter** — a dropdown in the toolbar switches between all branch changes, individual commits (most recent first), or uncommitted working changes.

**Reviewing** — press `r` or use the dedicated button to mark a file as reviewed. A progress bar in the toolbar tracks how many files you've reviewed. If a reviewed file changes on disk, it's automatically unmarked. When everything is reviewed, a completion screen appears with stats.

**Hunk navigation** — `j`/`k` to jump between hunks. Hunk headers show their own +/- counts and can be collapsed by clicking.

**Search** — `ctrl+f` to search within the current diff with match highlighting and navigation. `ctrl+g` to jump to a specific line. `ctrl+shift+f` (or the "Search files" button) to filter the file list.

**Risk scoring** — files are scored by risk factors (migrations, config changes, large deletions, test removal, high churn). Medium and high risk files show colored dots on their tabs and in the file tree. Sort by risk via the command palette.

## Comments

Right-click a line or press `c` to leave a comment. Comments support:

- **Text selection** — highlight text within a line and click the floating "Comment" button to leave a comment that references that exact substring; the referenced text stays highlighted in the diff (works in unified and split views)
- **Categories** — tag as bug, suggestion, nit, or question (colored badges)
- **Code suggestions** — attach a proposed code change with inline before/after preview and an Apply button that patches the file
- **Threads** — reply to comments; named authors (user vs agent) with color-coded identities
- **Resolution** — resolve/reopen with a toggle; resolved comments appear dimmed
- **Navigation** — `n`/`p` to jump between comments across files
- **Comments panel** — click "Comments" in the toolbar to see all open comments grouped by file
- **Bulk resolve** — resolve all comments in a file or globally from the command palette or comments panel
- **Export** — `Shift+S` copies a formatted markdown review summary to clipboard with stats and open comments by category

## AI agent integration

Comments are stored at `~/.config/diffui/{repo}/{branch}/comments.json` as structured JSON (file path, line number, diff context, comment text, author, category, code suggestion, and resolution status). AI agents can read and reply to this file directly.

**Send to agent** — click the button in the toolbar to spawn your configured agent CLI (Claude Code, Codex, OpenCode, or Cursor Agent) with a context file containing full diffs, review state, and existing comment threads. An interactive terminal panel slides up from the bottom, streaming the agent's full TUI output in real time. You can answer permission prompts, navigate multi-choice menus, and interact directly — no more black-box agent runs. The terminal shows elapsed time and detects when the agent goes idle. diffui auto-refreshes as the agent makes changes.

**Explain changes** — click the button in the toolbar to generate a self-contained HTML walkthrough of the branch (TL;DR, file-by-file analysis, architecture notes, risk flags).

Both actions are also available in the command palette (`ctrl+k`).

Or tell your agent directly: "Go address the diffui comments."

Configure your preferred agent CLI in Settings (gear icon).

## Display

- **15 color themes** — Catppuccin Mocha/Latte, GitHub Dark, Dracula, One Dark, Solarized Dark, Gruvbox Dark, Nord, Tokyo Night, Rose Pine, Rose Pine Moon, Monokai Pro, Kanagawa, Everforest, Ayu Dark
- **Blame gutter** — toggleable git blame showing author and age
- **Markdown/image preview** — rendered preview for `.md` files, inline display for images
- **Font size and line wrap** — adjustable in settings or via command palette
- **Ignore whitespace** — toggle via toolbar button or `w` key
- **Open in editor** — `ctrl+click` a line to open it in VS Code, Cursor, Vim, or Neovim (configurable in settings)

## Keybindings

| Key | Action |
| --- | --- |
| `ctrl+k` | Command palette |
| `?` | Keyboard shortcuts overlay |
| `left` / `right` | Previous / next file |
| `j` / `k` | Next / previous hunk |
| `]` | Next unreviewed file |
| `r` | Toggle reviewed |
| `a` | Show all / hide reviewed files |
| `n` / `p` | Next / previous comment |
| `c` | Comment on hovered line |
| `b` | Toggle explorer sidebar |
| `w` | Toggle ignore whitespace |
| `s` | Toggle sort by risk |
| `S` | Copy review summary |
| `y` | Copy file path |
| `Y` | Copy GitLab link |
| `ctrl+f` | Search in diff |
| `ctrl+g` | Go to line |
| `ctrl+shift+f` | Search files |
| `ctrl+click` | Open in editor |
| `right-click` | Comment on line (shows the native menu when text is selected, so you can copy) |
| select text | Floating "Comment" button to comment on the exact substring |
| `escape` | Close panel or dialog |

All shortcuts can be rebound in Settings.

## State

All state lives in `~/.config/diffui/` — nothing is written to repo directories.

- `settings.json` — theme, editor, agent CLI, display name (global)
- `{repo}/{branch}/reviewed.json` — review status (per-branch)
- `{repo}/{branch}/comments.json` — comments (per-branch)
- `{repo}/{branch}/session.json` — UI session state (per-branch)

## Other features

- `.diffuiignore` file to hide files from review (still visible to agents)
- `diffui --json` for programmatic agent workflows
- Auto-refresh via WebSocket (SSE fallback) powered by watchfiles
- Virtual scrolling for large files
- Session persistence (active file, scroll positions, UI state)
- Context-aware keybindings (suppressed when dialogs are open)
- Untracked files shown alongside committed changes

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```
