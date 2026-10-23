from __future__ import annotations

import pytest

from diffui.server.routes_diff import _order_files, _score_risk


@pytest.mark.parametrize(
    ("path", "adds", "dels", "expected"),
    [
        pytest.param("alembic/versions/001_init.py", 50, 0, (3, "medium", ["infra/migration"]), id="migration"),
        pytest.param("config/settings.yaml", 10, 5, (2, "low", ["config"]), id="config"),
        pytest.param("infra/values.yaml", 1, 1, (5, "high", ["infra/migration", "config"]), id="infra-config"),
        pytest.param("src/module.py", 0, 100, (3, "medium", ["large deletion"]), id="large-deletion"),
        pytest.param("tests/test_auth.py", 5, 30, (3, "medium", ["test removal"]), id="test-removal"),
        pytest.param("tests/test_auth.py", 30, 5, (0, "low", []), id="test-additions-are-not-removals"),
        pytest.param("src/big_refactor.py", 150, 100, (4, "medium", ["large deletion", "high churn"]), id="churn"),
        pytest.param("src/module.py", 0, 30, (1, "low", []), id="moderate-deletion-scores-without-a-reason"),
        pytest.param("src/module.py", 40, 20, (1, "low", []), id="moderate-churn-scores-without-a-reason"),
        pytest.param("src/utils.py", 10, 5, (0, "low", []), id="plain-source"),
        pytest.param("Makefile", 5, 5, (0, "low", []), id="no-extension"),
    ],
)
def test_score_risk(path, adds, dels, expected):
    assert _score_risk(path, adds, dels) == expected


def _entry(path: str, risk: int = 0) -> dict:
    return {"path": path, "dir": path.rpartition("/")[0] or ".", "risk_score": risk}


def test_order_files_mirrors_the_web_tree():
    files = [_entry("a/z.py"), _entry("b/y.py", 5), _entry("top.py", 3), _entry("a/b/x.py")]
    assert [f["path"] for f in _order_files(files, "tree")] == ["top.py", "a/z.py", "a/b/x.py", "b/y.py"]
    assert [f["path"] for f in _order_files(files, "risk")] == ["b/y.py", "top.py", "a/z.py", "a/b/x.py"]
