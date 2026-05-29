from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from diffui.git_utils import (
    _comments_path,
    get_file_mtime,
    get_git_dir,
    load_comments,
)
from diffui.server.state import app_state

router = APIRouter(prefix="/api")

_clients: set[asyncio.Queue] = set()


def _stat_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except (FileNotFoundError, NotADirectoryError):
        return 0.0


class Poller:
    def __init__(self) -> None:
        self.git_dir = get_git_dir()
        self.git_head_mtime = 0.0
        self.git_index_mtime = 0.0
        self.git_ref_mtime = 0.0
        self.comments_mtime = 0.0
        self.file_mtimes: dict[str, float] = {}
        self.snapshot()

    def snapshot(self) -> None:
        self.git_dir = get_git_dir()
        self.git_head_mtime = _stat_mtime(self.git_dir / "HEAD")
        self.git_index_mtime = _stat_mtime(self.git_dir / "index")
        branch = app_state.reload_branch_name()
        self.git_ref_mtime = _stat_mtime(self.git_dir / "refs" / "heads" / branch)
        self.comments_mtime = _stat_mtime(_comments_path())
        self.file_mtimes = {f: get_file_mtime(f) for f in app_state.all_files}

    def check(self) -> list[str]:
        events: list[str] = []

        head = _stat_mtime(self.git_dir / "HEAD")
        index = _stat_mtime(self.git_dir / "index")
        ref = _stat_mtime(self.git_dir / "refs" / "heads" / app_state.branch_name)
        comments = _stat_mtime(_comments_path())

        git_changed = head != self.git_head_mtime or index != self.git_index_mtime or ref != self.git_ref_mtime
        comments_changed = comments != self.comments_mtime

        if git_changed:
            app_state.reload_repo_state()
            from diffui.server.routes_diff import clear_diff_cache

            clear_diff_cache()
            self.git_dir = get_git_dir()
            self.file_mtimes = {f: get_file_mtime(f) for f in app_state.all_files}
            events.append("git_changed")
            events.append("files_changed")
        else:
            file_mtimes = {f: get_file_mtime(f) for f in app_state.all_files}
            if file_mtimes != self.file_mtimes:
                self.file_mtimes = file_mtimes
                events.append("files_changed")

        if comments_changed:
            app_state.comments = load_comments()
            events.append("comments_changed")

        self.git_head_mtime = head
        self.git_index_mtime = index
        self.git_ref_mtime = ref
        self.comments_mtime = comments

        return events


_poller: Poller | None = None


async def _poll_loop() -> None:
    global _poller
    _poller = Poller()
    while True:
        await asyncio.sleep(3)
        try:
            events = await asyncio.get_event_loop().run_in_executor(None, _poller.check)
            if events and _clients:
                data = json.dumps({"events": events})
                msg = f"data: {data}\n\n"
                for q in list(_clients):
                    try:
                        q.put_nowait(msg)
                    except asyncio.QueueFull:
                        pass
        except Exception:
            pass


async def _event_stream(queue: asyncio.Queue):
    try:
        while True:
            msg = await queue.get()
            yield msg
    except asyncio.CancelledError:
        pass


@router.get("/events")
async def sse_events():
    queue: asyncio.Queue = asyncio.Queue(maxsize=32)
    _clients.add(queue)

    async def generate():
        try:
            yield 'data: {"events": ["connected"]}\n\n'
            async for msg in _event_stream(queue):
                yield msg
        finally:
            _clients.discard(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def start_poller(loop: asyncio.AbstractEventLoop) -> None:
    loop.create_task(_poll_loop())
