"""Control Plane FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bootstrap import bootstrap_admin, init_database
from app.routers import admin, auth, user

logging.basicConfig(level=logging.INFO)


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
