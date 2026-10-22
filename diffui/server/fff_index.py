from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fff import FileFinder

from diffui.git_utils import get_repo_root

_SCAN_TIMEOUT_MS = 10_000

_lock = threading.Lock()
_finder: FileFinder | None = None
_root: Path | None = None
_stale = False


def mark_stale() -> None:
    """The next `finder()` rescans. Called from the filesystem watcher, which fff's own watcher replaces."""
    global _stale
    _stale = True


@contextmanager
def finder() -> Iterator[FileFinder]:
    """The resident index of the active repo, built on first use and rescanned when stale.

    Sync routes run in a threadpool, so the lock stays held while the caller uses the handle.
    """
    global _finder, _root, _stale
    root = get_repo_root()
    with _lock:
        if _finder is not None and _root != root:
            _close()
        if _finder is None:
            _finder = FileFinder(root, watch=False)
            _finder.wait_for_scan_blocking(_SCAN_TIMEOUT_MS)
            _root, _stale = root, False
        elif _stale:
            # Cleared first so a change that arrives mid-scan marks the index stale again.
            _stale = False
            _finder.scan_files()
            _finder.wait_for_scan_blocking(_SCAN_TIMEOUT_MS)
        yield _finder


def _close() -> None:
    global _finder, _root
    if _finder is not None:
        _finder.close()
    _finder = _root = None


def close() -> None:
    with _lock:
        _close()
