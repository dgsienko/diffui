---
name: check-tests
description: Check that a branch covers the behavior it changes, and that every test it adds earns its pipeline time. Use this during every code review.
---

Review the behavior the non-test code changes and every test the diff adds or edits. Read each changed test next to the code it calls. Open an unchanged test only to confirm a redundant finding. Don't run the tests.

A test earns its place by catching a named bug that no existing test catches. If you can't name the bug, it is a finding. Tests live in `tests/`: `test_server.py`, `test_comments.py` and `test_search.py` drive the routes through a `TestClient`, `test_tui.py` drives the real `DiffuiApp` under `run_test()`, and the rest cover one module each.

## What to check

Ask these in order. The first two block. The rest are suggestions.

1. Is a behavior change untested? For each behavior the diff adds or fixes, find the test that fails without it. A new route, branch or error path nothing drives is a gap. A bug fix needs its regression test. Don't ask for tests of code the branch didn't change.
2. Can each test fail? Flag a test that passes however the code behaves: a body that never asserts, a status check that accepts a 500, an `or` clause that is always true, an assertion on only `is not None`, `isinstance` or `len(x) > 0`, a check against a fixture that never held the thing it asserts is absent, an ordering check against a fake that sorts its own rows. If deleting the line under test or stubbing the function to return None leaves it green, it can't fail.
3. Is it tied to the implementation? Flag assertions on mock call counts, `call_args`, substrings of generated git arguments or HTML, and private state. Assert what a caller sees: a return value, a response body, a file written, an error raised.
4. Does it test a library? Pydantic validation and defaults, FastAPI's 422s, Textual's own behavior, Pygments tokenizing and `pty` mechanics aren't ours to test.
5. Is it redundant? Name the test that already drives the same path (`file:line`) or it isn't a finding. Prefer a parametrize case on the existing test over a new test or file.
6. Is it the wrong kind? Default to a feature test that exercises the code the way its caller does: a real request against `temp_repo`, or the real app under `run_test()`. Keep unit tests for pure, intricate logic such as diff parsing and line numbering. Flag a unit test that mocks away the thing a feature test would cover cheaply.
7. Is it slow or flaky? A real `sleep` where the `until()` helper exists, a fresh server per test where a session fixture would do, or a wait on a fixed delay.

When one change needs many tests, question the code before the tests: a helper whose cache and fallback paths need six tests is usually a helper that shouldn't cache or fall back. When a change makes a test obsolete or a new test subsumes an old one, the old test should be deleted in the same diff.

Judge tests of path containment and anything that writes to the working tree on duplication only, however simple they look. Don't flag length or style. When several tests share a fix, list them on one finding.

## How to flag

> :warning: Untested change: `path/module.py:42` [behavior], and no test fails without it. Add a [feature] test that [does X and asserts Y].

> :warning: Can't fail: `tests/test_x.py:88` `test_name` [why it passes regardless]. Fix the assertion or delete the test.

> :scissors: Test to cut: `tests/test_x.py:120` `test_name` [repeats `tests/test_y.py:40` / tests Pydantic's required-field check]. Delete it or fold it into the parametrize at `tests/test_x.py:100`. Suggestion, not a blocker.

> :link: Tied to the implementation: `tests/test_x.py:60` `test_name` asserts [a mock call count / a substring / private state]. Assert [the response / the file written] instead. Suggestion, not a blocker.

> :turtle: Slow or flaky: `tests/test_x.py:30` [sleep / per-test server]. Use [`until()` / the session fixture]. Suggestion, not a blocker.

When there is nothing to flag, report only this line:

> ✅ Tests (check-tests): no changes needed.

Suggest, never edit. The author makes the fix.
