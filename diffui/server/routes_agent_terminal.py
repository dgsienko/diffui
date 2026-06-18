from __future__ import annotations

import asyncio
import codecs
import collections
import fcntl
import os
import pty
import select
import struct
import subprocess
import termios
import tty

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
_agent_pty_fd: int | None = None
_agent_lock = asyncio.Lock()
_output_buffer: collections.deque[bytes] = collections.deque(maxlen=4096)
_BUFFER_MAX_BYTES = 65536
_IDLE_THRESHOLD = 100
_pending_start: dict | None = None


def _flush_buffer() -> bytes:
    chunks = list(_output_buffer)
    total = b"".join(chunks)
    if len(total) > _BUFFER_MAX_BYTES:
        total = total[-_BUFFER_MAX_BYTES:]
    return total


def _is_running() -> bool:
    return _agent_proc is not None and _agent_proc.poll() is None


def _spawn_agent(rows: int, cols: int) -> dict:
    global _agent_proc, _agent_pty_fd, _pending_start
    pending = _pending_start
    if not pending:
        return {"ok": False, "error": "No pending agent start"}

    pty_fd, child_fd = pty.openpty()
    child_tty = os.ttyname(child_fd)
    tty.setraw(child_fd)
    _resize_pty(pty_fd, rows, cols)

    env = {**os.environ, "TERM": "xterm-256color", "COLUMNS": str(cols), "LINES": str(rows)}

    def _child_setup():
        os.setsid()
        ctty = os.open(child_tty, os.O_RDWR)
        os.close(ctty)

    try:
        proc = subprocess.Popen(
            [*pending["cmd"], pending["prompt"]],
            cwd=pending["repo_root"],
            stdin=child_fd,
            stdout=child_fd,
            stderr=child_fd,
            env=env,
            close_fds=True,
            preexec_fn=_child_setup,
        )
    finally:
        os.close(child_fd)

    _agent_proc = proc
    _agent_pty_fd = pty_fd
    _output_buffer.clear()
    _pending_start = None
    return {"ok": True, "pid": proc.pid, "agent": pending["agent"]}


@router.post("/agent/start")
async def start_agent():
    global _pending_start

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

        _pending_start = {"prompt": prompt, "repo_root": repo_root, "agent": agent, "cmd": cmd}

    return {"ok": True, "agent": agent}


@router.post("/agent/kill")
def kill_agent_endpoint():
    if not _is_running():
        return {"ok": False, "error": "No agent running"}
    code = _kill_agent()
    return {"ok": True, "code": code}


def _read_pty(pty_fd: int, timeout: float = 0.1) -> bytes | None:
    try:
        ready, _, _ = select.select([pty_fd], [], [], timeout)
        if ready:
            return os.read(pty_fd, 16384)
    except OSError:
        return None
    return None


def _write_pty(pty_fd: int, data: str) -> None:
    try:
        os.write(pty_fd, data.encode())
    except OSError:
        pass


def _resize_pty(pty_fd: int, rows: int, cols: int) -> None:

    try:
        fcntl.ioctl(pty_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    except OSError:
        pass


def _kill_agent() -> int | None:
    global _agent_proc, _agent_pty_fd
    proc = _agent_proc
    fd = _agent_pty_fd
    if proc is None:
        return None
    _agent_proc = None
    _agent_pty_fd = None
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)
    if fd is not None:
        try:
            os.close(fd)
        except OSError:
            pass
    return proc.returncode


@router.websocket("/agent/ws")
async def agent_ws(ws: WebSocket):
    await ws.accept()

    if _agent_proc is not None and _agent_pty_fd is not None:
        pty_fd = _agent_pty_fd
        proc = _agent_proc
        replay = _flush_buffer()
        if replay:
            await ws.send_json({"type": "output", "data": replay.decode("utf-8", errors="replace")})
        await ws.send_json({"type": "started", "pid": proc.pid})
    elif _pending_start is not None:
        init_msg = await _recv_or_none(ws)
        if init_msg is None or init_msg.get("type") != "init":
            await ws.send_json({"type": "error", "message": "Expected init message with dimensions"})
            await ws.close()
            return

        rows = init_msg.get("rows", 24)
        cols = init_msg.get("cols", 80)
        result = await asyncio.get_event_loop().run_in_executor(None, _spawn_agent, rows, cols)
        if not result.get("ok"):
            await ws.send_json({"type": "error", "message": result.get("error", "Failed to start")})
            await ws.close()
            return

        pty_fd = _agent_pty_fd
        proc = _agent_proc
        await ws.send_json({"type": "started", "pid": result["pid"]})
    else:
        await ws.send_json({"type": "error", "message": "No agent running"})
        await ws.close()
        return

    if pty_fd is None or proc is None:
        await ws.send_json({"type": "error", "message": "Agent failed to start"})
        await ws.close()
        return

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

    utf8_decoder = codecs.getincrementaldecoder("utf-8")("replace")

    try:
        while True:
            data = await loop.run_in_executor(None, _read_pty, pty_fd, 0.03)
            if data:
                _output_buffer.append(data)
                text = utf8_decoder.decode(data)
                if text:
                    await ws.send_json({"type": "output", "data": text})
                had_output = True
                if not sent_idle:
                    idle_ticks = 0
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
                    await loop.run_in_executor(None, _write_pty, pty_fd, msg["data"])
                    sent_idle = False
                    idle_ticks = 0
                    had_output = False
                elif msg.get("type") == "resize":
                    await loop.run_in_executor(None, _resize_pty, pty_fd, msg.get("rows", 24), msg.get("cols", 80))
                elif msg.get("type") == "kill":
                    code = await loop.run_in_executor(None, _kill_agent)
                    await ws.send_json({"type": "exit", "code": code})
                    return

    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        pump_task.cancel()


async def _recv_or_none(ws: WebSocket) -> dict | None:
    try:
        return await ws.receive_json()
    except (WebSocketDisconnect, RuntimeError):
        return None
