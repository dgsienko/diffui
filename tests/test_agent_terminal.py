from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import diffui.server.routes_agent_terminal as rat
from diffui.server.routes_agent_terminal import (
    _BUFFER_MAX_BYTES,
    _kill_agent,
    _read_pty,
    _resize_pty,
    _write_pty,
)


@pytest.fixture(autouse=True)
def _reset_module_state():
    saved_proc = rat._agent_proc
    saved_fd = rat._agent_pty_fd
    saved_buffer = list(rat._output_buffer)
    saved_pending = rat._pending_start
    rat._agent_proc = None
    rat._agent_pty_fd = None
    rat._output_buffer.clear()
    rat._pending_start = None
    try:
        yield
    finally:
        rat._agent_proc = saved_proc
        rat._agent_pty_fd = saved_fd
        rat._output_buffer.clear()
        rat._output_buffer.extend(saved_buffer)
        rat._pending_start = saved_pending


class TestAppendOutput:
    def test_buffer_stays_under_max_as_output_arrives(self):
        rat._output_buffer.clear()
        chunk = b"x" * 1000
        for _ in range(_BUFFER_MAX_BYTES // len(chunk) + 10):
            rat._append_output(chunk)
        result = b"".join(rat._output_buffer)
        assert len(result) <= _BUFFER_MAX_BYTES
        assert result.endswith(chunk)


class TestPtyHelpers:
    def test_read_returns_available_bytes_or_none(self):
        r, w = os.pipe()
        try:
            assert _read_pty(r, timeout=0.01) is None
            os.write(w, b"data")
            assert _read_pty(r, timeout=1) == b"data"
        finally:
            os.close(r)
            os.close(w)

    def test_closed_descriptors_are_swallowed(self):
        r, w = os.pipe()
        os.close(r)
        try:
            assert _read_pty(r) is None
            _write_pty(w, "hi")
            _resize_pty(r, 40, 120)
        finally:
            os.close(w)


class TestKillAgent:
    def test_no_process_returns_none(self):
        assert _kill_agent() is None

    @pytest.mark.parametrize("fd_already_closed", [False, True])
    def test_terminates_the_process_and_releases_the_pty(self, fd_already_closed):
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        r, w = os.pipe()
        os.close(w)
        if fd_already_closed:
            os.close(r)
        rat._agent_proc, rat._agent_pty_fd = proc, r

        assert _kill_agent() == -signal.SIGTERM

        assert proc.poll() is not None
        assert (rat._agent_proc, rat._agent_pty_fd) == (None, None)
        with pytest.raises(OSError):
            os.fstat(r)

    def test_kills_a_process_that_ignores_terminate(self):
        proc = MagicMock()
        proc.wait.side_effect = [subprocess.TimeoutExpired("cmd", 5), None]
        proc.returncode = -9
        rat._agent_proc = proc

        assert _kill_agent() == -9
        proc.kill.assert_called_once()


@pytest.fixture(scope="class")
def _server_app():
    from diffui.git_utils import resolve_repo_root, set_active_repo
    from diffui.server.app import create_app

    root = resolve_repo_root(Path(__file__).parent.parent)
    set_active_repo(root)
    app = create_app([root])

    from fastapi.testclient import TestClient

    return TestClient(app, base_url="http://localhost")


class TestStartAgentEndpoint:
    def test_already_running(self, _server_app):
        proc = MagicMock()
        proc.poll.return_value = None
        with patch.object(rat, "_agent_proc", proc):
            r = _server_app.post("/api/agent/start")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert "already running" in body["error"].lower()

    def test_no_open_comments(self, _server_app):
        with (
            patch.object(rat, "_agent_proc", None),
            patch.object(rat, "_build_agent_context", return_value=(None, "No open comments", "", 0)),
        ):
            r = _server_app.post("/api/agent/start")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["error"] == "No open comments"

    def test_unknown_agent_cli(self, _server_app):
        with (
            patch.object(rat, "_agent_proc", None),
            patch.object(
                rat,
                "_build_agent_context",
                return_value=("prompt text", "/repo", "branch", 1),
            ),
            patch.object(rat.app_state, "agent_cli", "bogus-agent"),
        ):
            r = _server_app.post("/api/agent/start")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert "Unknown agent CLI" in body["error"]
        assert "bogus-agent" in body["error"]

    def test_start_stores_pending(self, _server_app):
        with (
            patch.object(rat, "_agent_proc", None),
            patch.object(
                rat,
                "_build_agent_context",
                return_value=("prompt text", "/repo", "branch", 1),
            ),
            patch.object(rat.app_state, "agent_cli", "claude"),
        ):
            r = _server_app.post("/api/agent/start")

        assert r.status_code == 200
        body = r.json()
        assert body == {"ok": True, "agent": "claude"}
        assert rat._pending_start is not None
        assert rat._pending_start["prompt"] == "prompt text"
        assert rat._pending_start["repo_root"] == "/repo"

    def test_spawned_agent_runs_in_its_own_session_on_a_sized_terminal(self, temp_repo):
        script = (
            "import os, sys; "
            "print(os.getsid(0) == os.getpid(), *os.get_terminal_size(0), os.environ['COLUMNS'], os.environ['LINES'], "
            "sys.argv[1])"
        )
        rat._pending_start = {
            "prompt": "the-prompt",
            "repo_root": str(temp_repo),
            "agent": "claude",
            "cmd": [sys.executable, "-c", script],
        }
        result = rat._spawn_agent(30, 100)
        output = b""
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not output.endswith(b"\n"):
            output += rat._read_pty(rat._agent_pty_fd) or b""
        rat._kill_agent()

        assert result["ok"] is True
        assert output.decode().split() == ["True", "100", "30", "100", "30", "the-prompt"]

    def test_spawn_closes_child_fd_on_popen_failure(self):
        rat._pending_start = {"prompt": "test", "repo_root": "/repo", "agent": "claude", "cmd": ["claude"]}
        with (
            patch.object(rat.pty, "openpty", return_value=(10, 11)),
            patch.object(rat.os, "ttyname", return_value="/dev/pts/99"),
            patch.object(rat.tty, "setraw"),
            patch.object(rat.subprocess, "Popen", side_effect=OSError("no exec")),
            patch.object(rat.os, "close") as mock_close,
            pytest.raises(OSError),
        ):
            rat._spawn_agent(24, 80)

        mock_close.assert_called_once_with(11)


class TestAgentWebSocket:
    def test_no_process_sends_error(self, _server_app):
        with (
            patch.object(rat, "_agent_proc", None),
            patch.object(rat, "_agent_pty_fd", None),
            _server_app.websocket_connect("ws://localhost/api/agent/ws") as ws,
        ):
            msg = ws.receive_json()
        assert msg == {"type": "error", "message": "No agent running"}

    def test_replays_buffer_and_started_then_exit(self, _server_app):
        proc = MagicMock()
        proc.pid = 555
        proc.poll.return_value = 0  # already exited
        proc.returncode = 0

        rat._output_buffer.clear()
        rat._output_buffer.append(b"previous output")

        with (
            patch.object(rat, "_agent_proc", proc),
            patch.object(rat, "_agent_pty_fd", 10),
            patch.object(rat, "_read_pty", return_value=None),
            _server_app.websocket_connect("ws://localhost/api/agent/ws") as ws,
        ):
            replay = ws.receive_json()
            started = ws.receive_json()
            exit_msg = ws.receive_json()

        assert replay == {"type": "output", "data": "previous output"}
        assert started == {"type": "started", "pid": 555}
        assert exit_msg == {"type": "exit", "code": 0}

    def test_streams_output_then_exits(self, _server_app):
        proc = MagicMock()
        proc.pid = 777
        # First poll (after output) still running, second poll exited.
        proc.poll.side_effect = [None, 3]
        proc.returncode = 3

        rat._output_buffer.clear()

        reads = [b"chunk one", None]

        def fake_read(fd, timeout):
            return reads.pop(0) if reads else None

        with (
            patch.object(rat, "_agent_proc", proc),
            patch.object(rat, "_agent_pty_fd", 10),
            patch.object(rat, "_read_pty", side_effect=fake_read),
            _server_app.websocket_connect("ws://localhost/api/agent/ws") as ws,
        ):
            ws.receive_json()  # started (no replay since buffer empty)
            output = ws.receive_json()
            exit_msg = ws.receive_json()

        assert output == {"type": "output", "data": "chunk one"}
        assert exit_msg == {"type": "exit", "code": 3}
        # Streamed output is appended to the replay buffer.
        assert b"chunk one" in b"".join(rat._output_buffer)

    def test_kill_message_terminates(self, _server_app):
        proc = MagicMock()
        proc.pid = 888
        proc.poll.return_value = None  # stays running until killed

        rat._output_buffer.clear()

        with (
            patch.object(rat, "_agent_proc", proc),
            patch.object(rat, "_agent_pty_fd", 10),
            patch.object(rat, "_read_pty", return_value=None),
            patch.object(rat, "_kill_agent", return_value=-15) as mock_kill,
            _server_app.websocket_connect("ws://localhost/api/agent/ws") as ws,
        ):
            ws.receive_json()  # started
            ws.send_json({"type": "kill"})
            exit_msg = ws.receive_json()

        assert exit_msg == {"type": "exit", "code": -15}
        mock_kill.assert_called_once()


class TestPendingStart:
    @pytest.mark.parametrize(
        ("age", "stale"),
        [(None, True), (0, False), (rat._PENDING_TTL + 1, True)],
        ids=["missing", "fresh", "abandoned"],
    )
    def test_pending_start_goes_stale_after_its_ttl(self, age, stale):
        rat._pending_start = None if age is None else {"created": time.monotonic() - age}
        assert rat._pending_is_stale() is stale
