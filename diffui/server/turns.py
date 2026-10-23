"""Last turn: the worktree as it stood when an agent in this repo last went from resting to working."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter

from diffui.git_utils import get_repo_root, snapshot_worktree, write_turn_tree
from diffui.server import terminal_host
from diffui.server.events import _bg_tasks, _broadcast
from diffui.server.routes_diff import clear_diff_cache
from diffui.server.state import app_state

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

POLL_SECONDS = 1.0
_RESTING = {"idle", "done"}


class TurnTracker:
    """Folds the repo's agent statuses into turn starts."""

    def __init__(self) -> None:
        self._resting = False

    def observe(self, statuses: list[str]) -> bool:
        """True on the sample where the repo goes from resting to working."""
        if "working" in statuses:
            started, self._resting = self._resting, False
            return started
        # Blocked and unknown agents are mid-turn, so a working status after them starts nothing.
        self._resting = all(s in _RESTING for s in statuses)
        return False

    def lost(self) -> None:
        """Nobody saw the agents for a sample, so the next working status cannot be an edge."""
        self._resting = False


def start_turn() -> None:
    write_turn_tree(snapshot_worktree())
    app_state.reload_last_turn()
    clear_diff_cache()


def poll_once(tracker: TurnTracker) -> bool:
    statuses = terminal_host.repo_agent_statuses(get_repo_root())
    if statuses is None:
        tracker.lost()
        return False
    if not tracker.observe(statuses):
        return False
    start_turn()
    return True


@router.get("/last-turn")
def last_turn():
    """Why the last-turn view is empty, or None when it has changes to show."""
    turn = app_state.last_turn
    if turn is None:
        tail = (
            ""
            if terminal_host.available()
            else f". Last turn needs diffui in a {terminal_host.NAME} pane with an agent working in this repo"
        )
        return {"reason": "No agent turn seen yet" + tail}
    return {"reason": None if turn.stats else "Nothing has changed since the last turn started"}


async def _poll_loop() -> None:
    loop = asyncio.get_running_loop()
    tracker = TurnTracker()
    root = None
    while True:
        try:
            if (current := get_repo_root()) != root:
                root, tracker = current, TurnTracker()
            if await loop.run_in_executor(None, poll_once, tracker):
                _broadcast(["files_changed"])
        except Exception:
            log.exception("turn poll failed")
        await asyncio.sleep(POLL_SECONDS)


def start_turn_poller() -> asyncio.Task | None:
    if not terminal_host.available():
        return None
    task = asyncio.get_running_loop().create_task(_poll_loop())
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return task
