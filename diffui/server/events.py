from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.responses import StreamingResponse
from watchfiles import awatch

from diffui.git_utils import (
    _comments_path,
    get_git_dir,
    get_repo_root,
    load_comments,
)
from diffui.server.state import app_state

router = APIRouter(prefix="/api")

_sse_clients: set[asyncio.Queue] = set()
_ws_clients: set[WebSocket] = set()
_bg_tasks: set[asyncio.Task] = set()

DEBOUNCE_MS = 400


def _broadcast(events: list[str]) -> None:
    if not events:
        return
    data = json.dumps({"events": events})

    if _sse_clients:
        msg = f"data: {data}\n\n"
        for q in list(_sse_clients):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    for ws in list(_ws_clients):
        try:
            task = asyncio.create_task(ws.send_text(data))
            _bg_tasks.add(task)
            task.add_done_callback(_bg_tasks.discard)
        except Exception:
            _ws_clients.discard(ws)


def _classify_changes(changes: set[tuple], git_dir: str, comments_path: str) -> list[str]:
    events: set[str] = set()
    for _change_type, path in changes:
        if path == comments_path:
            events.add("comments_changed")
        elif path.startswith(git_dir):
            events.add("git_changed")
        else:
            events.add("files_changed")
    return list(events)


def _apply_state_updates(events: list[str]) -> list[str]:
    if "git_changed" in events:
        app_state.reload_repo_state()
        from diffui.server.routes_diff import clear_diff_cache

        clear_diff_cache()
        if "files_changed" not in events:
            events = [*events, "files_changed"]

    if "comments_changed" in events:
        app_state.comments = load_comments()

    return events


def make_watch_filter(git_dir_str: str):
    def _watch_filter(_change, path: str) -> bool:
        if "/.git/" in path or path.endswith("/.git"):
            if not path.startswith(git_dir_str):
                return False
            rel = path[len(git_dir_str) :]
            return rel.startswith("/HEAD") or rel.startswith("/index") or rel.startswith("/refs/")
        return not (path.endswith(".pyc") or "/__pycache__/" in path)

    return _watch_filter


async def _watch_loop() -> None:
    repo_root = get_repo_root()
    git_dir = get_git_dir()
    comments_file = _comments_path()

    watch_paths = [str(repo_root)]
    if not str(git_dir).startswith(str(repo_root)):
        watch_paths.append(str(git_dir))
    comments_dir = comments_file.parent
    if comments_dir.exists() and not str(comments_dir).startswith(str(repo_root)):
        watch_paths.append(str(comments_dir))

    watch_filter = make_watch_filter(str(git_dir))
    git_dir_str = str(git_dir)
    comments_path_str = str(comments_file)

    async for changes in awatch(
        *watch_paths,
        debounce=DEBOUNCE_MS,
        step=100,
        watch_filter=watch_filter,
        recursive=True,
    ):
        try:
            events = _classify_changes(changes, git_dir_str, comments_path_str)
            if events:
                events = await asyncio.get_event_loop().run_in_executor(None, _apply_state_updates, events)
                _broadcast(events)
        except Exception:
            pass


# --- SSE fallback ---


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
    _sse_clients.add(queue)

    async def generate():
        try:
            yield 'data: {"events": ["connected"]}\n\n'
            async for msg in _event_stream(queue):
                yield msg
        finally:
            _sse_clients.discard(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- WebSocket ---


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        await ws.send_text(json.dumps({"events": ["connected"]}))
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except (json.JSONDecodeError, KeyError):
                pass
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


def start_poller(loop: asyncio.AbstractEventLoop) -> None:
    loop.create_task(_watch_loop())
