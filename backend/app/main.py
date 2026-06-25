"""Control Plane FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import FileResponse

from app.bootstrap import bootstrap_admin, init_database
from app.routers import admin, auth, user

logging.basicConfig(level=logging.INFO)

# Built React SPA, baked into the image at /app/frontend_dist (see Dockerfile).
# Absent in local dev, where Vite serves the SPA on :5173 — the guard keeps the
# API working unchanged when there is nothing to serve.
_SPA_DIST = Path(__file__).resolve().parent.parent / "frontend_dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialise the database and bootstrap admin on startup."""
    init_database()
    bootstrap_admin()
    yield


app = FastAPI(
    title="Freqtrade Control Plane",
    version="0.1.0",
    summary="Multi-user orchestration layer for per-user Freqtrade instances",
    lifespan=lifespan,
)

app.include_router(auth.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(user.router, prefix="/api")


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe for the control plane itself."""
    return {"status": "ok"}


# --- Static SPA (production single-origin serving) -------------------------
# Mounted last so it never shadows the API routers above. In dev the dist dir
# does not exist and this whole block is skipped.
if _SPA_DIST.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=_SPA_DIST / "assets"),
        name="assets",
    )

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str = "") -> FileResponse:
        """Serve hashed static files when they exist, else the SPA shell.

        The fallback to ``index.html`` lets client-side routes (``/admin/*``,
        ``/app/*``) survive a hard refresh / deep link. This catch-all is
        registered after the API routers, so a real API path is matched there
        first; only an *unknown* ``/api/*`` path reaches here, and we return a
        genuine 404 for it rather than the SPA shell.
        """
        if full_path.startswith("api/") or full_path.startswith("assets/"):
            raise StarletteHTTPException(status_code=404)
        candidate = (_SPA_DIST / full_path).resolve()
        if (
            full_path
            and _SPA_DIST in candidate.parents
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(_SPA_DIST / "index.html")
