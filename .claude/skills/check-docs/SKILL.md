---
name: check-docs
description: Check that a branch leaves the docs true, necessary and short, including comments and docstrings. Use this during every code review.
---

Review the prose the diff adds or leaves behind: README.md, AGENTS.md, code comments and docstrings.

Where facts live:

- README.md is for someone using diffui: install, CLI flags, keybindings, state files, development setup.
- AGENTS.md is for someone changing it: architecture, patterns, gotchas that break silently, commands.
- A comment or docstring is for a fact tied to one function, and it must explain what the code can't show.

## What to check

Ask these in order. Check 1 blocks. The rest are suggestions, except a banned tell in check 5, which blocks.

1. Does the diff make an existing doc claim false? Search README.md and AGENTS.md for the names, paths, flags, keybindings, state-file fields and counts (themes, scopes, routes) the diff changes. Check the architecture tree in AGENTS.md for added, moved or deleted files, and the Testing section for added or removed test files. A claim the diff breaks must be fixed or deleted in the same branch.
2. Did the diff change a decision a doc explains? If a page gives the reason for a design choice and the branch changes the choice, update the reason. Changed mechanics under an unchanged decision need nothing.
3. Does the added doc text belong? Flag file maps, route or flag tables the code already shows, function-by-function walks, and changelog wording ("now", "no longer", "previously"). Never flag a missing doc just because code changed.
4. Does each added comment or docstring earn its place? Grep the nearest sibling modules first: diffui comments are sparse and explain a quirk, a git edge case or a reason a reader would "fix" the code wrongly. Flag comments that restate the line below, docstrings for code that doesn't exist yet, and meta text that reads fine with the code deleted (why it was added, what it replaced, who asked).
5. Does added prose sound like Dillon and avoid the AI tells? Read `~/.claude/STYLE.md` and `~/.claude/TROPES.md` if you can. American English, plain, practical, leads with what changed or what to do. Flag em-dashes, "rather than" and "instead of", negative parallelism ("not X, it's Y"), bold-first bullets, "lands in/on" as a placement verb, and the banned vocabulary in TROPES.md (leverage, robust, seamless, streamline and the rest).
6. Is the added text as short as it can be? Flag a point made twice, hedging, a sentence carrying two ideas, and a lead buried under setup. A compressed sentence that takes longer to decode than the code is worse than none.

AGENTS.md loads on every turn, so a paragraph added to it should be something an agent needs while working. A paragraph that only describes how a subsystem works belongs in README.md or a docstring, and one that restates another doc should be cut.

## How to flag

> :warning: Stale doc: `README.md` says [claim], which this branch changes to [new behavior]. Fix or delete that sentence here.

> :warning: Writing tell: `path:42` uses [em-dash / "rather than" / bold-first bullet / ...]. Rewrite: "...".

> :scissors: Doc bloat: the lines added to `AGENTS.md` [describe]. The code shows this, and it goes stale on the next change. Cut it or move it to [place]. Suggestion, not a blocker.

> :pencil2: Doc clarity: `path:42` [restates the code / is meta / says X twice / buries the point]. [Cut it. / Suggested rewrite: "..."] Suggestion, not a blocker.

When there is nothing to flag, report only this line:

> ✅ Docs (check-docs): no changes needed.
