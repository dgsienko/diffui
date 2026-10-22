from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.datastructures import Headers
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketClose

from diffui.git_utils import PathOutsideRepo
from diffui.server.events import router as events_router
from diffui.server.events import start_poller
from diffui.server.herdr import clear_status, report_status
from diffui.server.routes_comments import router as comments_router
from diffui.server.routes_diff import router as diff_router
from diffui.server.routes_repo import router as repo_router
from diffui.server.routes_review import router as review_router
from diffui.server.routes_review import shutdown as review_shutdown
from diffui.server.routes_settings import router as settings_router
from diffui.server.state import app_state
from diffui.themes import ALL_THEMES


class _NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if path.endswith((".js", ".css")):
            response.headers["Cache-Control"] = "no-store"
        return response


_STATIC_DIR = Path(__file__).parent.parent / "static"
_LOCAL_HOSTS = {"localhost", "127.0.0.1"}


class _LocalOriginOnly:
    # Any page open in the browser can send requests to a localhost port. Checking Host stops DNS
    # rebinding, and checking Origin stops cross-site form posts and WebSocket connections.
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = Headers(scope=scope)
            host = headers.get("host", "")
            origin = headers.get("origin", "")
            if host.rsplit(":", 1)[0] not in _LOCAL_HOSTS or (origin and origin.split("://", 1)[-1] != host):
                reject = WebSocketClose(1008) if scope["type"] == "websocket" else PlainTextResponse("Forbidden", 403)
                await reject(scope, receive, send)
                return
        await self.app(scope, receive, send)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    start_poller()
    report_status()
    yield
    review_shutdown()
    clear_status()


def create_app(repos: list[Path], active_index: int = 0) -> FastAPI:
    app_state.repos = repos
    app_state.active_repo_index = active_index
    app_state.reload_repo_state()

    app = FastAPI(title="diffui", lifespan=_lifespan)
    app.add_middleware(_LocalOriginOnly)
    app.include_router(repo_router)
    app.include_router(diff_router)
    app.include_router(comments_router)
    app.include_router(review_router)
    app.include_router(settings_router)
    app.include_router(events_router)

    from diffui.server.routes_agent_terminal import router as agent_terminal_router

    app.include_router(agent_terminal_router)

    @app.exception_handler(PathOutsideRepo)
    def path_outside_repo(_request: Request, _exc: PathOutsideRepo):
        return JSONResponse({"detail": "Path outside repository"}, status_code=400)

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

    app.mount("/static", _NoCacheStaticFiles(directory=str(_STATIC_DIR)), name="static")
    return app
