# diffui

[![CI](https://github.com/dgsienko/diffui/actions/workflows/ci.yml/badge.svg)](https://github.com/dgsienko/diffui/actions/workflows/ci.yml)

<p align="center">
  <a href="#install">install</a> · <a href="#quick-start">quick start</a> · <a href="#ai-agent-integration">agents</a> · <a href="#terminal-ui">terminal UI</a> · <a href="#keybindings">keybindings</a> · <a href="#development">development</a>
</p>

A local code review UI for a git branch, with optional AI agent integration.

You get syntax-highlighted diffs, inline comment threads and risk scoring. If you have a coding agent installed, you can leave comments on the diff, send them to the agent, watch it respond, and review the next round of changes without leaving the page.

Use it before you push. Review what your agent just wrote while nothing is on a remote yet, or look at your own branch in a real diff UI without opening a draft MR. GitHub or GitLab review still happens after.

It runs as a local web server with a Preact frontend, or as a terminal UI with `diffui --tui`. There is no build step and no accounts. Your code stays on your machine with one exception: a markdown file with a mermaid or plantuml block is rendered by kroki.io, so that block's source is sent there when you preview the file. The web UI loads its frontend libraries from a CDN, so the first paint needs a network.

## Install

diffui needs Python 3.10 or newer. There is no PyPI release, so install from GitHub:

```bash
pipx install git+https://github.com/dgsienko/diffui
```

To work on diffui, install a clone in editable mode so the `diffui` command follows your checkout:

```bash
git clone https://github.com/dgsienko/diffui
cd diffui
pipx install -e .
```

## Quick start

`cd` into a git repo on a feature branch and run:

```bash
diffui
```

This starts a server on a free local port and prints the URL. Open it in a browser, or in a terminal app that renders web content. You'll see every file changed on the branch, plus uncommitted and untracked files, in a syntax-highlighted diff.

The branch is compared with its merge base against `main` or `master`. diffui uses the `origin/` copy when it exists and the local branch otherwise.

When the parent directory holds several git repos, they show up in a dropdown for switching. To review specific repos, pass their paths:

```bash
diffui ~/code/api ~/code/web
```

diffui watches the repo with watchfiles and pushes changes to the page over a WebSocket (SSE as a fallback), so edits from an agent appear without a reload.

### CLI flags

```bash
diffui --open        # Open the URL in your browser
diffui --comments    # Print all comments to stdout
diffui --json        # Print the review session as JSON
diffui --tui         # Review in the terminal (see Terminal UI)
```

## Reviewing changes

- The explorer sidebar lists the changed files, grouped by directory, file type or change status. Click a file or press the left and right arrow keys to move through them in the order the sidebar shows. The Explorer button in the top bar hides and shows it.
- The view dropdown in the top bar switches between all branch changes, uncommitted changes, the agent's last turn (see [Last turn](#last-turn)), and single commits, most recent first.
- A segmented control in the file header switches between unified, split and full file views. Whitespace, Hide reviewed, Blame, More context and Mark reviewed sit next to it.
- Press `r` to mark a file reviewed. The top bar shows reviewed files out of the total, next to the added and removed line counts. If a reviewed file changes on disk, it is unmarked. When everything is reviewed, a completion screen shows your stats. `]` jumps to the next unreviewed file.
- `j` and `k` jump between hunks. Click a hunk header to collapse it. The raw `diff --git`, `index`, `---` and `+++` lines are hidden, and a rename, mode change, new or deleted file, or binary file gets one short line.
- `ctrl+f` searches within the diff and highlights the matches. `ctrl+g` jumps to a line. `ctrl+shift+f`, or the Search files button, filters the file list.
- Files are scored for risk from their path and size: migration, infra, schema and deploy paths, config files, large deletions, high churn and test removal. Medium and high risk files get a colored dot in the file tree, with the level in the tooltip. `s` sorts by risk.
- A `.diffuiignore` file in the repo root hides matching files from the file list and from search. It takes one glob per line, and `#` starts a comment. `diffui --json` still lists them.

## Comments

Right-click a line, or hover it and press `c`, to leave a comment.

- Select text within a line or across several, then click the floating Comment button. The comment references that exact span, and the span stays highlighted in the diff. This works in unified and split views.
- Tag a comment as bug, suggestion, nit or question.
- A suggestion carries a proposed replacement, with an inline before and after preview and an Apply button that patches the file and resolves the comment. Apply refuses if the line changed since you wrote the comment, or if the comment covers more than one line.
- Replies form a thread. User and agent replies show their author in different colors.
- Resolve or reopen a thread with its toggle. Resolved comments are dimmed.
- `n` and `p` jump between comments across files.
- The Comments button in the top bar opens a panel of open comments grouped by file. Resolve all comments in a file, or everywhere, from the panel or the command palette.
- `S` copies a markdown review summary to the clipboard, with file and comment counts, open comments by category, and the status of each file.

## AI agent integration

Comments are stored at `~/.config/diffui/{repo}/{branch}/comments.json`. Each one has the file path, line number, diff context, comment text, author, category, suggestion and status. An agent can read that file and reply to it directly.

- Send to agent builds a prompt from your open comments and writes a context file with the full diffs of the commented files, the review state and the existing threads. It then starts your configured agent CLI in a terminal panel that slides up from the bottom of the page. The panel streams the agent's full TUI, so you can answer permission prompts and use its menus. It shows elapsed time and notices when the agent goes idle. The page refreshes as the agent edits.
- Explain changes starts the agent CLI in the background to write a self-contained HTML walkthrough of the branch: TL;DR, motivation, file-by-file analysis, architecture notes, risk flags and where to focus.

Both are also in the command palette (`ctrl+k`, or `cmd+k` on macOS). Pick the agent in Settings (gear icon): Claude Code, Codex, OpenCode or Cursor Agent.

You can also point your own agent at the comments file.

### Running inside herdr

When you start `diffui` in a [herdr](https://herdr.dev) pane, Send to agent pastes the prompt into the agent already running in that workspace, so you keep its session and context. diffui needs `herdr` on your PATH and detects the pane from `HERDR_WORKSPACE_ID`.

It picks the agent working in the same repo, or the first agent in the workspace if none is. herdr focuses that pane, and you can add to the prompt before pressing Enter. diffui won't paste while the agent is at a permission prompt, because Claude Code throws the paste away there.

diffui also reports two values for the workspace's row in herdr's sidebar: `$comments` (like `3 open`) and `$reviewed` (like `☑ 12/20`). Add them to a row in your herdr config:

```toml
[ui.sidebar.spaces]
rows = [
  ["state_icon", "workspace"],
  ["$comments", "$reviewed"],
]
```

diffui clears both values when it exits.

### Last turn

Last turn shows what the agent changed since its latest turn began. It needs diffui in a herdr pane and an agent working in the same repo in any herdr workspace.

The server polls `herdr agent list` every second. When an agent in the repo goes from idle or done to working, it saves the worktree as a git tree, untracked files included. It builds that tree in a temporary index, so your index and files stay untouched. The tree is stored under `refs/worktree/diffui/last-turn`, so it survives a restart, and each linked worktree keeps its own. The scope diffs that tree against the worktree as it is now.

Without herdr, or before an agent has started a turn, the scope says "No agent turn seen yet". The snapshot is taken when the poll first sees `working`, so a change made before that is already in it and does not show. A turn that changes nothing still replaces the previous baseline.

## Terminal UI

`diffui --tui` runs the review loop in the terminal, so it fits in a herdr split next to your coding agent. It starts the same server on a free port and talks to it over HTTP. Comments, reviewed state, risk scores and your theme are the ones the browser shows. Press `o` to open the web UI at the current file.

The TUI covers the file list, a unified or split diff with syntax highlighting, comment threads, reviewed state, diff scopes, search, find in file and Send to agent. Explain changes, markdown and mermaid preview, blame and the agent terminal stay in the browser.

The file list sits on the right of the diff. Under 110 columns it stacks below the diff, and `z` hides it.

Inside herdr, `A` pastes the prompt into the workspace's agent pane. Anywhere else it shows the prompt, and `c` copies it.

| Key | Action |
| --- | --- |
| `left` / `right`, `h` / `l` | Previous / next file |
| `k` / `j` | Previous / next hunk |
| `p` / `n` | Previous / next comment thread |
| `up` / `down`, `pgup` / `pgdn`, `ctrl+u` / `ctrl+d`, `g` / `G` | Move the cursor |
| `r` | Mark the file reviewed or unreviewed. Marking it reviewed opens the next unreviewed file |
| `]` | Next unreviewed file |
| `s` | Sort files by risk |
| `u` / `b` / `t` | Scope: uncommitted changes / everything on the branch / the agent's last turn |
| `C` | Pick one commit as the scope |
| `/` | Search file names and text, in the scope's files or the whole repo (`tab` switches) |
| `ctrl+f` | Find in this file |
| `n` / `N` | Next / previous find match, while matches are showing |
| `\|` | Switch between unified and split diff |
| `tab` | Split view: move between the old and new line of a replaced pair |
| `c` or `enter` | Comment on the line or range, or reply to the thread |
| `v` | Start a line range at the cursor, then extend it with `up` / `down` |
| `shift+up` / `shift+down` | Start or extend a line range |
| `esc` | Clear the range, then the find matches |
| `x` | Resolve or reopen the thread |
| `A` | Send open comments to the agent |
| `o` | Open this file in the browser |
| `z` | Show or hide the file list |
| `?` | Help |
| `q` | Quit |

The footer shows the keys that fit the row under the cursor.

Clicking a file opens it, and clicking a diff row selects it. Hovering a row swaps its line number for a `[+]`. Click the number column to open the comment box for that line, or drag down it to comment on a range. `ctrl+s` saves the comment. A range comment is stored the way a multi-line text selection is in the browser, so the web UI highlights the same lines.

### Scopes

The header shows the current scope. The browser has the same choices in its view dropdown.

- Uncommitted (`u`) is staged and unstaged changes plus new files.
- Branch (`b`) is everything since the branch left its base, commits included. This is the default.
- Last turn (`t`) is the changes since the agent's latest turn started. See [Last turn](#last-turn).
- Commit (`C`) is the changes of one commit.

### Search and find

`/` opens a search over the files in the current scope. Names match as a substring or as the query's letters in order, and a name with a typo still finds its file, so `rendrer` finds `renderer.py`. Text matches lines of the files as they are on disk, ignoring case, grouped by file with line numbers, up to 200 lines. Enter opens the file at that line. When the diff does not show the line, the cursor goes to the nearest one that it does.

`tab` in the search switches between Changed and All files, and the header shows which is active. All files searches the whole repo through [fff](https://github.com/dmtrKovalenko/fff), which skips `.gitignore`d and binary files and ranks names by fuzzy match. Files that are not in the diff are dimmed and marked "not in diff". Opening one shows it read-only, highlighted and scrolled to the line, with a note at the top. You cannot comment on it or mark it reviewed. `left` / `right` or a pick from the file list returns to the diff's files, and `o` opens it in the browser.

`ctrl+f` finds text in the open file's diff and highlights every match as you type. `enter` and `shift+enter`, or `down` and `up`, step through the matches while the bar is open. `esc` closes the bar and keeps the highlights, and `n` / `N` keep stepping. A second `esc` clears them. Comment threads keep `n` / `p` whenever no matches are showing.

### Split view

`|` puts the old file on the left and the new one on the right, with their own line numbers and tints. It needs a diff pane 100 columns wide. In a narrower pane the TUI stays unified and says so, and hiding the file list with `z` often makes room. A comment on a row goes against the new line, or the old line when it was removed, which is what the browser's split view stores. On a row that replaces one line with another, click the left or right number column, or press `tab`, to choose the side.

## Display

- 16 color themes, with Graphite as the default: Graphite, Catppuccin Mocha, Catppuccin Latte, GitHub Dark, Dracula, One Dark, Solarized Dark, Gruvbox Dark, Nord, Tokyo Night, Rosé Pine, Rosé Pine Moon, Monokai Pro, Kanagawa, Everforest and Ayu Dark.
- The blame gutter shows the author and age of each line.
- `.md` files get a rendered preview and images show inline. Markdown is sanitized before rendering, and diagram blocks go to kroki.io.
- Font size and line wrap are in Settings and the command palette.
- `w` or the Whitespace button toggles ignore whitespace.
- `ctrl+click` (`cmd+click` on macOS) a line to open it in VS Code, Cursor, Vim or Neovim. Pick the editor in Settings.

## Keybindings

| Key | Action |
| --- | --- |
| `ctrl+k` / `cmd+k` | Command palette |
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
| `ctrl+g` / `cmd+g` | Go to line |
| `ctrl+shift+f` | Search files |
| `ctrl+click` / `cmd+click` | Open in editor |
| `right-click` | Comment on line (shows the native menu when text is selected, so you can copy) |
| select text | Floating "Comment" button to comment on the exact substring |
| `escape` | Close panel or dialog |

Most shortcuts are ignored while a dialog is open. `r`, `a`, `c`, `y`, `s`, `S`, `b` and `]` can be rebound in Settings. The terminal UI keys are in [Terminal UI](#terminal-ui).

## State

Review state lives in `~/.config/diffui/`:

- `settings.json` holds theme, editor, agent CLI, display name, font size, line wrap and rebound keys. It is global.
- `{repo}/{branch}/reviewed.json` holds review status.
- `{repo}/{branch}/comments.json` holds comments.
- `{repo}/{branch}/session.json` holds UI session state: the active file, diff mode, scroll positions and the explorer and reviewed-file toggles.

`{repo}` is the repo's full path with `/` replaced by `_`, and `{branch}` is the branch name the same way.

Three things live elsewhere. The last-turn baseline is a git ref in the repo's own git directory. The agent context file (`diffui-agent-context-{branch}.md`) and the Explain output (`diffui-explain-{branch}.html`) go to your system temp directory, and diffui deletes them when it exits. The one working tree write is Apply on a suggestion.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
ruff format --check .
```

AGENTS.md has the architecture.

## License

Copyright (c) 2026 Dillon Sienko. All rights reserved.
