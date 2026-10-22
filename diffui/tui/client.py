from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import quote

import httpx
import uvicorn

from diffui.cli import _find_free_port
from diffui.server.app import create_app


class LocalServer:
    """The FastAPI app on a free port, served from a background thread so the lifespan (watcher, herdr status) runs."""

    def __init__(self, repos: list[Path], active_index: int = 0) -> None:
        self.port = _find_free_port()
        config = uvicorn.Config(
            create_app(repos, active_index=active_index),
            host="127.0.0.1",
            port=self.port,
            log_config=None,
            timeout_graceful_shutdown=2,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name="diffui-server", daemon=True)

    @property
    def url(self) -> str:
        return f"http://localhost:{self.port}"

    def start(self) -> None:
        self._thread.start()
        deadline = time.monotonic() + 15
        while not self._server.started:
            if not self._thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("diffui server failed to start")
            time.sleep(0.02)

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10)


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self._http = httpx.AsyncClient(base_url=base_url, timeout=30)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, url: str, **params) -> httpx.Response:
        r = await self._http.get(url, params=params)
        r.raise_for_status()
        return r

    async def _post(self, url: str, **kwargs) -> httpx.Response:
        r = await self._http.post(url, **kwargs)
        r.raise_for_status()
        return r

    async def settings(self) -> dict:
        return (await self._get("/api/settings")).json()

    async def branch(self) -> dict:
        return (await self._get("/api/branch")).json()

    async def files(self, order: str) -> list[dict]:
        return (await self._get("/api/files", order=order, hide_ignored="true")).json()

    async def next_unreviewed(self, order: str) -> str | None:
        return (await self._get("/api/files/next-unreviewed", order=order)).json()["path"]

    async def diff(self, path: str) -> dict:
        return (await self._get(f"/api/diff/{quote(path)}")).json()

    async def comments(self) -> dict[str, list[dict]]:
        return (await self._get("/api/comments")).json()

    async def toggle_reviewed(self, path: str) -> bool:
        return (await self._post(f"/api/reviewed/{quote(path)}")).json()["reviewed"]

    async def add_comment(self, path: str, line: dict, text: str) -> None:
        await self._post(
            "/api/comments",
            json={
                "file_path": path,
                "line_index": line["index"],
                "line_text": line["text"],
                "file_line_num": int(line["new_num"] or line["old_num"] or 0) or None,
                "comment": text,
            },
        )

    async def reply(self, path: str, comment_id: str, text: str) -> None:
        await self._post(f"/api/comments/{quote(path)}/{comment_id}/reply", json={"text": text})

    async def toggle_resolved(self, path: str, comment_id: str) -> None:
        await self._post(f"/api/comments/{quote(path)}/{comment_id}/resolve")

    async def agent_prompt(self) -> dict:
        return (await self._post("/api/agent/prompt")).json()

    async def agent_paste(self) -> dict:
        return (await self._post("/api/agent/paste")).json()

    async def set_active_file(self, path: str) -> None:
        await self._http.put("/api/session", json={"activeFile": path})

    async def events(self) -> AsyncIterator[list[str]]:
        """Event names from the server's SSE stream, reconnecting if it drops."""
        while True:
            try:
                async with self._http.stream("GET", "/api/events", timeout=None) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            yield json.loads(line[5:])["events"]
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
