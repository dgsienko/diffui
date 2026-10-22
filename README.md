# diffui

A local code review UI tool with optional AI agent integration.

Review any branch with syntax-highlighted diffs, inline comments, and risk scoring. If you have a coding agent installed locally, you can leave feedback directly on the diff, watch the agent respond, and review the next round of changes in a tight loop without leaving the browser. There is also an AI-powered explain feature that walks you through what the branch does.

Runs as a local web server with a Preact frontend. No build step and no accounts. Your code stays on your machine, with one exception: a markdown file containing a mermaid or plantuml block is rendered by kroki.io, so that block's source is sent there when you preview the file. Frontend libraries load from a CDN, so the first paint needs a network.

## Who is this for

If you use Claude Code, Codex, Cursor, or similar tools, diffui beats scrolling terminal diffs or waiting for a pushed MR. Review locally, leave comments, and send feedback back to the agent before anything hits a remote.

For reviewing your own work before pushing, it saves you opening a draft MR just to see your changes in a proper diff UI. Useful when your IDE's diff view doesn't cut it for larger changes, or when you want risk scoring, comment threads, or a cross-file overview.

If you spend most of your time in a terminal, diffui fits that flow. It runs locally, prints a URL, and works well in terminal browsers or apps that support inline web content.

Use diffui *before* pushing, to catch issues early and iterate with agents locally. GitHub/GitLab review still happens after.

## Install

```bash
pipx install -e .
```

## Quick start

`cd` into any git repo on a feature branch and run:

```bash
diffui
```

This starts a local server and prints the URL. Open that URL via an external browser or within your terminal application (if supported). You'll see every file changed on the current branch (vs the merge base with `origin/main` or `origin/master`, falling back to the local branch when there's no remote) in a tabbed, syntax-highlighted diff viewer.

Sibling repos in the same parent directory are auto-discovered and available via a dropdown for easy repository switching.

### CLI flags

```bash
diffui --open        # Automatically open the URL in an external browser
diffui --comments    # Dump all comments to stdout
diffui --json        # Export review session as structured JSON
diffui --tui         # Review in the terminal instead of the browser
```

## Reviewing changes

- Navigation: the explorer sidebar lists the changed files, grouped by directory, file type, or change status. Click a file or use the arrow keys to move through them in the order the sidebar shows. The Explorer button in the top bar hides and shows it. `]` jumps to the next unreviewed file.
- Diff modes: toggle between unified diff, side-by-side split, or full file view using the segmented control in the file header above the diff. Whitespace, Hide reviewed, Blame, More context and Mark reviewed sit next to it.
- View filter: a dropdown in the top bar switches between all branch changes, individual commits (most recent first), or uncommitted working changes.
- Reviewing: press `r` or use the dedicated button to mark a file as reviewed. The top bar shows how many files you've reviewed next to the total added and removed lines. If a reviewed file changes on disk, it's automatically unmarked. When everything is reviewed, a completion screen appears with stats.
- Hunk navigation: `j`/`k` to jump between hunks. Hunk headers show their own +/- counts and can be collapsed by clicking. The raw `diff --git`/`index`/`---`/`+++` lines are hidden. A rename, mode change, new or deleted file, or binary file gets one short line instead.
- Search: `ctrl+f` to search within the current diff with match highlighting and navigation. `ctrl+g` to jump to a specific line. `ctrl+shift+f` (or the "Search files" button) to filter the file list.
- Risk scoring: files are scored by risk factors (migrations, config changes, large deletions, test removal, high churn). Medium and high risk files show colored dots in the file tree, with the level in the tooltip. Sort by risk via the command palette.

## Comments

Right-click a line or press `c` to leave a comment. Comments support:

- Text selection: highlight text, within a line or across several, and click the floating "Comment" button to leave a comment that references that exact span; the referenced text stays highlighted in the diff (works in unified and split views)
- Categories: tag as bug, suggestion, nit, or question (colored badges)
- Code suggestions: attach a proposed code change with inline before/after preview and an Apply button that patches the file. Apply refuses if the line has changed since you wrote the comment, or if the comment covers more than one line
- Threads: reply to comments; named authors (user vs agent) with color-coded identities
- Resolution: resolve/reopen with a toggle; resolved comments appear dimmed
- Navigation: `n`/`p` to jump between comments across files
- Comments panel: click "Comments" in the top bar to see all open comments grouped by file
- Bulk resolve: resolve all comments in a file or globally from the command palette or comments panel
- Export: `Shift+S` copies a formatted markdown review summary to clipboard with stats and open comments by category

## AI agent integration

Comments are stored at `~/.config/diffui/{repo}/{branch}/comments.json` as structured JSON (file path, line number, diff context, comment text, author, category, code suggestion, and resolution status). AI agents can read and reply to this file directly.

- Send to agent: click the button in the top bar to spawn your configured agent CLI (Claude Code, Codex, OpenCode, or Cursor Agent) with a context file containing full diffs, review state, and existing comment threads. An interactive terminal panel slides up from the bottom, streaming the agent's full TUI output in real time. You can answer permission prompts, navigate multi-choice menus, and interact with the agent directly. The terminal shows elapsed time and detects when the agent goes idle. diffui auto-refreshes as the agent makes changes.
- Explain changes: click the button in the top bar to generate a self-contained HTML walkthrough of the branch (TL;DR, file-by-file analysis, architecture notes, risk flags).

Both actions are also available in the command palette (`ctrl+k`).

Or tell your agent directly: "Go address the diffui comments."

Configure your preferred agent CLI in Settings (gear icon).

### Running inside herdr

When you start the `diffui` server in a [herdr](https://herdr.dev) pane, Send to agent in the browser pastes the prompt into the agent already running in that workspace, so you keep its session and context. It picks the agent working in the same repo, or the first agent in the workspace if none is. herdr then focuses that pane, and you can add to the prompt before pressing Enter. diffui won't paste while the agent is sitting at a permission prompt, because Claude Code throws the paste away there.

diffui also reports two values for the workspace's row in herdr's sidebar: `$comments` (like `3 open`) and `$reviewed` (like `12/20 reviewed`). Add them to your herdr config to show them:

```toml
[ui.sidebar.spaces]
rows = [
  ["state_icon", "workspace"],
  ["branch", "git_status"],
  ["$comments", "$reviewed"],
]
```

## Terminal UI

`diffui --tui` runs the review loop in the terminal, so it fits in a herdr split next to the coding agent. It starts the same server on a free port and talks to it over HTTP, which means comments, reviewed state and risk scores are the ones the browser shows. Press `o` to open the web UI at the current file.

The TUI covers the file list, a unified diff with syntax highlighting, comment threads, reviewed state, and Send to agent. Inside herdr, Send to agent pastes the prompt into the workspace's agent pane. Anywhere else it shows the prompt so you can copy it with `c`. Explain changes, markdown and mermaid preview, blame, split view and the agent terminal stay in the browser.

| Key | Action |
| --- | --- |
| `left` / `right`, `h` / `l` | Previous / next file |
| `k` / `j` | Previous / next hunk |
| `p` / `n` | Previous / next comment thread |
| `up` / `down`, `pgup` / `pgdn`, `g` / `G` | Move the cursor |
| `r` | Mark the file reviewed or unreviewed, then open the next unreviewed file |
| `]` | Next unreviewed file |
| `s` | Sort files by risk |
| `c` or `enter` | Comment on the line, or reply to the thread |
| `x` | Resolve or reopen the thread |
| `A` | Send open comments to the agent |
| `o` | Open this file in the browser |
| `b` | Show or hide the file list |
| `?` | Help |
| `q` | Quit |

Clicking a file opens it. Clicking the selected line opens the comment box, and `ctrl+s` saves it.

## Display

- 16 color themes, with Graphite as the default: Graphite, Catppuccin Mocha/Latte, GitHub Dark, Dracula, One Dark, Solarized Dark, Gruvbox Dark, Nord, Tokyo Night, Rose Pine, Rose Pine Moon, Monokai Pro, Kanagawa, Everforest, Ayu Dark
- Blame gutter: toggleable git blame showing author and age
- Markdown/image preview: rendered preview for `.md` files, inline display for images. Markdown is sanitized before rendering, and diagram blocks go to kroki.io
- Font size and line wrap: adjustable in settings or via command palette
- Ignore whitespace: toggle via the file header button or `w` key
- Open in editor: `ctrl+click` a line to open it in VS Code, Cursor, Vim, or Neovim (configurable in settings)

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

All state lives in `~/.config/diffui/`. Nothing is written to repo directories.

- `settings.json`: theme, editor, agent CLI, display name (global)
- `{repo}/{branch}/reviewed.json`: review status (per-branch)
- `{repo}/{branch}/comments.json`: comments (per-branch)
- `{repo}/{branch}/session.json`: UI session state (per-branch)

## Other features

- `.diffuiignore` file to hide files from review (still visible to agents)
- `diffui --json` for programmatic agent workflows
- Auto-refresh via WebSocket (SSE fallback) powered by watchfiles; the terminal UI uses the SSE stream
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
