"""Run the review check skills on a branch before it is pushed.

One headless Claude session runs check-docs, check-scope and check-tests against
origin/main and blocks the push when any of them raises a :warning: finding.
The pre-push hook pipes git's `<local ref> <local sha> <remote ref> <remote sha>`
lines to stdin.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys

SKILLS = ("check-docs", "check-scope", "check-tests")
TIMEOUT_SECONDS = 600
VERDICT = re.compile(r"CHECK-SUITE:\W*(PASS|BLOCK)\b")
PROMPT = """Review this branch as a code review. Read each of these skill files \
and follow it: {skills}. Report each one's output in its own format. You can't \
run shell commands, so use the diff below wherever a skill asks for `git diff`, \
and read files directly. Do not edit any files. End with exactly one line: \
`CHECK-SUITE: BLOCK` if any skill raised a :warning: finding, otherwise \
`CHECK-SUITE: PASS`.

Commit messages on the branch, which state its purpose:

{log}

`git diff --stat -M {range}`:

{stat}

`git diff -M {range}`:

{diff}"""


def pushed_sha(hook_input: str) -> str | None:
    """Return the first local sha being pushed, skipping branch deletions."""
    for line in hook_input.splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[1].strip("0"):
            return fields[1]
    return None


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def main() -> int:
    if shutil.which("claude") is None:
        print("check-suite: claude is not installed, skipping.")
        return 0
    hook_input = "" if sys.stdin.isatty() else sys.stdin.read()
    sha = pushed_sha(hook_input)
    if hook_input.strip() and sha is None:
        print("check-suite: the push only deletes refs, skipping.")
        return 0
    tip = sha or "HEAD"
    diff_range = f"origin/main...{tip}"
    diff = git("diff", "-M", diff_range)
    stat = git("diff", "--stat", "-M", diff_range)
    if diff.returncode != 0:
        print(f"check-suite: git diff {diff_range} failed, skipping.\n{diff.stderr}")
        return 0
    if not diff.stdout:
        return 0
    log = git("log", "--format=%B", f"origin/main..{tip}")

    print(f"check-suite: running {', '.join(SKILLS)} on {diff_range}. This takes a few minutes.")
    skill_files = ", ".join(f".claude/skills/{skill}/SKILL.md" for skill in SKILLS)
    prompt = PROMPT.format(skills=skill_files, range=diff_range, log=log.stdout, stat=stat.stdout, diff=diff.stdout)
    try:
        result = subprocess.run(
            ["claude", "-p", "--restricted", "--tools", "Read,Grep,Glob", "--strict-mcp-config"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        print(f"check-suite: no result after {TIMEOUT_SECONDS}s, skipping.")
        return 0
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        print(f"check-suite: claude exited {result.returncode}, skipping.")
        return 0

    verdicts = VERDICT.findall(result.stdout)
    if not verdicts:
        print("check-suite: no CHECK-SUITE verdict in the report, skipping.")
        return 0
    # The prompt quotes a verdict line, so the report can echo one before its own.
    if verdicts[-1] == "BLOCK":
        print("check-suite: fix the :warning: findings above, commit, and push again.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
