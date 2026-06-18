from __future__ import annotations

import asyncio
import collections
import os
import pty
import select
import struct
import subprocess
import termios

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from diffui.server.routes_review import _build_agent_context
from diffui.server.state import app_state

_INTERACTIVE_CMDS: dict[str, list[str]] = {
    "claude": ["claude"],
    "codex": ["codex"],
    "opencode": ["opencode"],
    "cursor": ["cursor-agent"],
}

router = APIRouter(prefix="/api")

_agent_proc: subprocess.Popen | None = None
_agent_master_fd: int | None = None
_agent_lock = asyncio.Lock()
_output_buffer: collections.deque[bytes] = collections.deque(maxlen=4096)
_BUFFER_MAX_BYTES = 65536
_IDLE_THRESHOLD = 100


def _flush_buffer() -> bytes:
    chunks = list(_output_buffer)
    total = b"".join(chunks)
    if len(total) > _BUFFER_MAX_BYTES:
        total = total[-_BUFFER_MAX_BYTES:]
    return total


def _is_running() -> bool:
    return _agent_proc is not None and _agent_proc.poll() is None


@router.post("/agent/start")
async def start_agent():
    global _agent_proc, _agent_master_fd

    async with _agent_lock:
        if _is_running():
            return {"ok": False, "error": "Agent already running"}

        result = _build_agent_context()
        if result[0] is None:
            return {"ok": False, "error": result[1]}
        prompt, repo_root, _, _ = result

        agent = app_state.agent_cli
        cmd = _INTERACTIVE_CMDS.get(agent)
        if not cmd:
            return {"ok": False, "error": f"Unknown agent CLI: {agent}"}

        master_fd, slave_fd = pty.openpty()

        _resize_pty(master_fd, 24, 120)

        env = {**os.environ, "TERM": "xterm-256color", "COLUMNS": "120", "LINES": "24"}

        try:
            proc = subprocess.Popen(
                [*cmd, prompt],
                cwd=repo_root,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                close_fds=True,
            )
        finally:
            os.close(slave_fd)

        _agent_proc = proc
        _agent_master_fd = master_fd
        _output_buffer.clear()

    return {"ok": True, "pid": proc.pid, "agent": agent}


def _read_pty(master_fd: int, timeout: float = 0.1) -> bytes | None:
    try:
        ready, _, _ = select.select([master_fd], [], [], timeout)
        if ready:
            return os.read(master_fd, 4096)
    except OSError:
        return None
    return None


def _write_pty(master_fd: int, data: str) -> None:
    try:
        os.write(master_fd, data.encode())
    except OSError:
        pass


def _resize_pty(master_fd: int, rows: int, cols: int) -> None:
    import fcntl

    try:
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    except OSError:
        pass


def _kill_agent() -> int | None:
    global _agent_proc, _agent_master_fd
    if _agent_proc is None:
        return None
    _agent_proc.terminate()
    try:
        _agent_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _agent_proc.kill()
        _agent_proc.wait(timeout=2)
    code = _agent_proc.returncode
    if _agent_master_fd is not None:
        try:
            os.close(_agent_master_fd)
        except OSError:
            pass
    _agent_proc = None
    _agent_master_fd = None
    return code


@router.websocket("/agent/ws")
async def agent_ws(ws: WebSocket):
    await ws.accept()

    if _agent_proc is None or _agent_master_fd is None:
        await ws.send_json({"type": "error", "message": "No agent running"})
        await ws.close()
        return

    master_fd = _agent_master_fd
    proc = _agent_proc

    replay = _flush_buffer()
    if replay:
        await ws.send_json({"type": "output", "data": replay.decode("utf-8", errors="replace")})

    await ws.send_json({"type": "started", "pid": proc.pid})

    loop = asyncio.get_event_loop()
    incoming: asyncio.Queue[dict | None] = asyncio.Queue()

    async def _pump_ws():
        while True:
            msg = await _recv_or_none(ws)
            await incoming.put(msg)
            if msg is None:
                return

    pump_task = asyncio.create_task(_pump_ws())

    had_output = False
    idle_ticks = 0
    sent_idle = False

    try:
        while True:
            data = await loop.run_in_executor(None, _read_pty, master_fd, 0.03)
            if data:
                _output_buffer.append(data)
                await ws.send_json({"type": "output", "data": data.decode("utf-8", errors="replace")})
                had_output = True
                idle_ticks = 0
                sent_idle = False
            elif proc.poll() is not None:
                await ws.send_json({"type": "exit", "code": proc.returncode})
                return
            else:
                idle_ticks += 1
                if had_output and not sent_idle and idle_ticks >= _IDLE_THRESHOLD:
                    await ws.send_json({"type": "idle"})
                    sent_idle = True

            while not incoming.empty():
                msg = incoming.get_nowait()
                if msg is None:
                    return
                if msg.get("type") == "stdin":
                    await loop.run_in_executor(None, _write_pty, master_fd, msg["data"])
                elif msg.get("type") == "resize":
                    await loop.run_in_executor(None, _resize_pty, master_fd, msg.get("rows", 24), msg.get("cols", 80))
                elif msg.get("type") == "kill":
                    code = await loop.run_in_executor(None, _kill_agent)
                    await ws.send_json({"type": "exit", "code": code})
                    return

    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()


async def _recv_or_none(ws: WebSocket) -> dict | None:
    try:
        return await ws.receive_json()
    except (WebSocketDisconnect, RuntimeError):
        return None
