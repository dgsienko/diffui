from __future__ import annotations

import os
import pty
import select
import struct
import subprocess
import termios
import tty
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import diffui.server.routes_agent_terminal as rat
from diffui.server.routes_agent_terminal import (
    _BUFFER_MAX_BYTES,
    _flush_buffer,
    _is_running,
    _kill_agent,
    _read_pty,
    _resize_pty,
    _write_pty,
)


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Snapshot and restore module globals around each test."""
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


class TestFlushBuffer:
    def test_empty_buffer(self):
        rat._output_buffer.clear()
        assert _flush_buffer() == b""

    def test_small_buffer_joined(self):
        rat._output_buffer.clear()
        rat._output_buffer.append(b"hello ")
        rat._output_buffer.append(b"world")
        assert _flush_buffer() == b"hello world"

    def test_buffer_exceeding_max_is_truncated_to_tail(self):
        rat._output_buffer.clear()
        # Append more than _BUFFER_MAX_BYTES total.
        chunk = b"x" * 1000
        total_len = 0
        while total_len <= _BUFFER_MAX_BYTES:
            rat._output_buffer.append(chunk)
            total_len += len(chunk)
        result = _flush_buffer()
        assert len(result) == _BUFFER_MAX_BYTES
        assert result == b"x" * _BUFFER_MAX_BYTES


class TestIsRunning:
    def test_none_process(self):
        rat._agent_proc = None
        assert _is_running() is False

    def test_exited_process(self):
        proc = MagicMock()
        proc.poll.return_value = 0
        rat._agent_proc = proc
        assert _is_running() is False

    def test_running_process(self):
        proc = MagicMock()
        proc.poll.return_value = None
        rat._agent_proc = proc
        assert _is_running() is True


class TestReadPty:
    def test_data_available(self):
        with (
            patch.object(rat.select, "select", return_value=([5], [], [])),
            patch.object(rat.os, "read", return_value=b"data") as mock_read,
        ):
            assert _read_pty(5, timeout=0.1) == b"data"
            mock_read.assert_called_once_with(5, 16384)

    def test_no_data_timeout(self):
        with patch.object(rat.select, "select", return_value=([], [], [])):
            assert _read_pty(5, timeout=0.1) is None

    def test_oserror_returns_none(self):
        with patch.object(rat.select, "select", side_effect=OSError("boom")):
            assert _read_pty(5) is None


class TestWritePty:
    def test_normal_write_encodes(self):
        with patch.object(rat.os, "write") as mock_write:
            _write_pty(7, "hi")
            mock_write.assert_called_once_with(7, b"hi")

    def test_oserror_swallowed(self):
        with patch.object(rat.os, "write", side_effect=OSError("closed")):
            _write_pty(7, "hi")  # must not raise


class TestResizePty:
    def test_calls_ioctl(self):
        with patch("fcntl.ioctl") as mock_ioctl:
            _resize_pty(9, 40, 120)
            assert mock_ioctl.called
            args = mock_ioctl.call_args[0]
            assert args[0] == 9

    def test_oserror_swallowed(self):
        with patch("fcntl.ioctl", side_effect=OSError("bad fd")):
            _resize_pty(9, 40, 120)  # must not raise


class TestKillAgent:
    def test_no_process_returns_none(self):
        rat._agent_proc = None
        assert _kill_agent() is None

    def test_terminates_cleanly(self):
        proc = MagicMock()
        proc.wait.return_value = 0
        proc.returncode = 0
        rat._agent_proc = proc
        rat._agent_pty_fd = 12

        with patch.object(rat.os, "close") as mock_close:
            code = _kill_agent()

        assert code == 0
        proc.terminate.assert_called_once()
        proc.kill.assert_not_called()
        mock_close.assert_called_once_with(12)
        assert rat._agent_proc is None
        assert rat._agent_pty_fd is None

    def test_needs_kill_after_timeout(self):
        proc = MagicMock()
        proc.wait.side_effect = [rat.subprocess.TimeoutExpired("cmd", 5), None]
        proc.returncode = -9
        rat._agent_proc = proc
        rat._agent_pty_fd = None

        code = _kill_agent()

        assert code == -9
        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()
        assert proc.wait.call_count == 2

    def test_close_oserror_swallowed(self):
        proc = MagicMock()
        proc.wait.return_value = 0
        proc.returncode = 0
        rat._agent_proc = proc
        rat._agent_pty_fd = 3

        with patch.object(rat.os, "close", side_effect=OSError("already closed")):
            code = _kill_agent()

        assert code == 0
        assert rat._agent_pty_fd is None


@pytest.fixture(scope="class")
def _server_app():
    from diffui.git_utils import resolve_repo_root, set_active_repo
    from diffui.server.app import create_app

    root = resolve_repo_root(Path(__file__).parent.parent)
    set_active_repo(root)
    app = create_app([root])

    from fastapi.testclient import TestClient

    return TestClient(app)


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

    def test_spawn_agent_creates_process(self):
        proc = MagicMock()
        proc.pid = 4242
        rat._pending_start = {"prompt": "test", "repo_root": "/repo", "agent": "claude", "cmd": ["claude"]}
        with (
            patch.object(rat.pty, "openpty", return_value=(10, 11)),
            patch.object(rat.os, "ttyname", return_value="/dev/pts/99"),
            patch.object(rat.tty, "setraw"),
            patch.object(rat.subprocess, "Popen", return_value=proc) as mock_popen,
            patch.object(rat.os, "close") as mock_close,
        ):
            result = rat._spawn_agent(30, 100)

        assert result == {"ok": True, "pid": 4242, "agent": "claude"}
        mock_close.assert_called_once_with(11)
        called_cmd = mock_popen.call_args[0][0]
        assert called_cmd[0] == "claude"
        kwargs = mock_popen.call_args[1]
        assert kwargs["stdin"] == 11
        assert kwargs["env"]["COLUMNS"] == "100"
        assert kwargs["env"]["LINES"] == "30"
        assert kwargs["preexec_fn"] is not None

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


class TestPtyIntegration:
    """Integration tests that spawn real PTY processes to verify terminal setup."""

    def test_child_has_controlling_terminal(self):
        pty_fd, child_fd = pty.openpty()
        child_tty = os.ttyname(child_fd)
        tty.setraw(child_fd)

        def child_setup():
            os.setsid()
            fd = os.open(child_tty, os.O_RDWR)
            os.close(fd)

        proc = subprocess.Popen(
            ["python3", "-c", "import os; print(os.ctermid())"],
            stdin=child_fd,
            stdout=child_fd,
            stderr=child_fd,
            preexec_fn=child_setup,
            close_fds=True,
        )
        os.close(child_fd)

        output = b""
        for _ in range(50):
            ready, _, _ = select.select([pty_fd], [], [], 0.1)
            if ready:
                output += os.read(pty_fd, 4096)
            if proc.poll() is not None:
                break

        proc.wait(timeout=5)
        os.close(pty_fd)
        assert b"/dev/" in output

    def test_arrow_key_sequences_pass_through_raw_pty(self):
        pty_fd, child_fd = pty.openpty()
        child_tty = os.ttyname(child_fd)
        tty.setraw(child_fd)

        def child_setup():
            os.setsid()
            fd = os.open(child_tty, os.O_RDWR)
            os.close(fd)

        proc = subprocess.Popen(
            ["cat"],
            stdin=child_fd,
            stdout=child_fd,
            stderr=child_fd,
            preexec_fn=child_setup,
            close_fds=True,
        )
        os.close(child_fd)

        os.write(pty_fd, b"\x1b[A")

        output = b""
        for _ in range(20):
            ready, _, _ = select.select([pty_fd], [], [], 0.1)
            if ready:
                output += os.read(pty_fd, 4096)
            if b"\x1b[A" in output:
                break

        proc.terminate()
        proc.wait(timeout=5)
        os.close(pty_fd)
        assert b"\x1b[A" in output

    def test_sigwinch_delivered_after_resize(self):
        pty_fd, child_fd = pty.openpty()
        child_tty = os.ttyname(child_fd)
        tty.setraw(child_fd)
        import fcntl

        fcntl.ioctl(pty_fd, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))

        def child_setup():
            os.setsid()
            fd = os.open(child_tty, os.O_RDWR)
            os.close(fd)

        script = (
            "import signal, sys, struct, fcntl, termios\n"
            "got = []\n"
            "def handler(sig, frame):\n"
            "    ws = fcntl.ioctl(0, termios.TIOCGWINSZ, b'\\x00' * 8)\n"
            "    rows, cols = struct.unpack('HHHH', ws)[:2]\n"
            "    got.append(f'{rows}x{cols}')\n"
            "signal.signal(signal.SIGWINCH, handler)\n"
            "import time; time.sleep(0.5)\n"
            "print(','.join(got) if got else 'NO_SIGWINCH')\n"
        )

        proc = subprocess.Popen(
            ["python3", "-c", script],
            stdin=child_fd,
            stdout=child_fd,
            stderr=child_fd,
            preexec_fn=child_setup,
            close_fds=True,
        )
        os.close(child_fd)

        import time

        time.sleep(0.1)
        fcntl.ioctl(pty_fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 100, 0, 0))

        output = b""
        for _ in range(50):
            ready, _, _ = select.select([pty_fd], [], [], 0.1)
            if ready:
                output += os.read(pty_fd, 4096)
            if proc.poll() is not None:
                break

        proc.wait(timeout=5)
        os.close(pty_fd)
        text = output.decode("utf-8", errors="replace")
        assert "40x100" in text, f"Expected SIGWINCH with 40x100, got: {text!r}"

    def test_without_setsid_no_controlling_terminal(self):
        """Verify that without setsid, the child does NOT get a controlling terminal."""
        pty_fd, child_fd = pty.openpty()
        tty.setraw(child_fd)

        proc = subprocess.Popen(
            ["python3", "-c", "import os; print(os.ttyname(0))"],
            stdin=child_fd,
            stdout=child_fd,
            stderr=child_fd,
            close_fds=True,
        )
        os.close(child_fd)

        output = b""
        for _ in range(50):
            ready, _, _ = select.select([pty_fd], [], [], 0.1)
            if ready:
                output += os.read(pty_fd, 4096)
            if proc.poll() is not None:
                break

        proc.wait(timeout=5)
        os.close(pty_fd)
        assert b"/dev/" in output


class TestAgentWebSocket:
    def test_no_process_sends_error(self, _server_app):
        with (
            patch.object(rat, "_agent_proc", None),
            patch.object(rat, "_agent_pty_fd", None),
            _server_app.websocket_connect("/api/agent/ws") as ws,
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
            _server_app.websocket_connect("/api/agent/ws") as ws,
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
            _server_app.websocket_connect("/api/agent/ws") as ws,
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
            _server_app.websocket_connect("/api/agent/ws") as ws,
        ):
            ws.receive_json()  # started
            ws.send_json({"type": "kill"})
            exit_msg = ws.receive_json()

        assert exit_msg == {"type": "exit", "code": -15}
        mock_kill.assert_called_once()
