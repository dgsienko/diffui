from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from diffui.server.events import router as events_router
from diffui.server.events import start_poller
from diffui.server.routes_comments import router as comments_router
from diffui.server.routes_diff import router as diff_router
from diffui.server.routes_repo import router as repo_router
from diffui.server.routes_review import router as review_router
from diffui.server.routes_settings import router as settings_router
from diffui.server.state import app_state
from diffui.themes import ALL_THEMES

_STATIC_DIR = Path(__file__).parent.parent / "static"


def create_app(repos: list[Path], active_index: int = 0) -> FastAPI:
    app_state.repos = repos
    app_state.active_repo_index = active_index
    app_state.reload_repo_state()

    app = FastAPI(title="diffui")
    app.include_router(repo_router)
    app.include_router(diff_router)
    app.include_router(comments_router)
    app.include_router(review_router)
    app.include_router(settings_router)
    app.include_router(events_router)

    @app.on_event("startup")
    async def startup():
        start_poller(asyncio.get_event_loop())

    @app.get("/api/themes")
    def list_themes():
        return [{"index": i, "name": t.name, "active": i == app_state.theme_index} for i, t in enumerate(ALL_THEMES)]

    @app.get("/api/theme/css")
    def get_theme_css():
        from diffui.server.theme_css import generate_css_vars

        return {"css": generate_css_vars(app_state.theme)}

    _index_html = (_STATIC_DIR / "index.html").read_text()

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(_index_html)

    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    return app
