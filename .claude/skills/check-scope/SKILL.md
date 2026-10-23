---
name: check-scope
description: Check that a branch's changes trace to its stated purpose, contain nothing speculative, and are small enough to review safely. Use this during every code review.
---

Judge whether every change serves the stated purpose, and whether the branch is too big to review safely. Analyze and suggest only. Never split, branch, cherry-pick or edit.

The stated purpose is the commit messages on the branch, given in the prompt. When the messages are too thin to judge from, say so and judge on coherence alone.

## What to check

Ask these in order. Checks 1 and 2 block. The rest are suggestions.

1. Does a change fail to trace to the stated purpose? Flag drive-by fixes, reformatting or comment edits in lines the purpose doesn't touch, renames of adjacent code, and dependency bumps. Match the style of the surrounding code even where another style would be better. Name the hunk and the purpose it doesn't serve.
2. Is anything speculative? Flag helpers with no caller, config knobs nobody sets, retries, fallbacks, caches and guards for states the callers can't produce, abstractions for a second case that doesn't exist, and docstrings for code that isn't there. A not-yet-called module is fine only when it is the branch's stated deliverable and names its consumer. "To be safe" is not a requirement.
3. Did the change leave dead code behind? Code, imports, tests or docs the branch made obsolete should go in the same diff.
4. Does it add structure the request didn't imply? A new file, class or dependency when an edit to an existing file would do, a bundler or build step for the frontend (diffui has none and must not gain one), or a wrapper around a single call. Inline a helper until it has three real callers.
5. Is it bigger than the problem? Flag 200 lines that could be 50, and an abstraction for two call sites that inlining would shorten.
6. Is it too large to review? Count substantive lines, excluding tests, docs, renames and formatter output. Over about 15 files or 800 substantive lines, or more than one unrelated concern at any size, look for a split. Concerns matter more than line count: one refactor plus its one consumer is a good branch, and a small one mixing a bug fix, a UI tweak and a dependency bump is not.

## Splits

Cut only along real seams: pure refactor before behavior change, new module before wiring, drive-by fixes lifted out, dead-code removal. Never cut by line count, file count or directory. Each part must pass the suite alone, revert alone, deliver something real and carry its own tests. Suggest at most three parts. If no seam survives, report the branch as it is, since a bad split costs the author time to reject.

## How to flag

> :warning: Out of scope: `path:42` [what changed], which doesn't serve [purpose]. Drop it or move it to its own branch.

> :warning: Speculative: `path:42` [helper / knob / fallback / guard] has [no caller / no setter / no reachable trigger]. Delete it, or name the requirement that needs it.

> :mag: Simplification: `path:42` [what is unnecessary and what to do instead]. Removes about [N] lines. Suggestion, not a blocker.

> :scissors: Split suggestion: this branch changes [N] files and about [M] substantive lines across [concerns]. Consider [Part 1: files, what it delivers alone] then [Part 2: files, depends on Part 1]. Suggestion, not a blocker.

When there is nothing to flag, report only this line:

> ✅ Scope (check-scope): no changes needed.
