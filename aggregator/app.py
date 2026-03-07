"""FastAPI application factory."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from aggregator import __version__
from aggregator.config import Settings
from aggregator.database import Database
from aggregator.middleware import APIKeyMiddleware, RateLimitMiddleware
from aggregator.api import reports, dashboard, compliance, health, drift, remediation, anomaly


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        from aggregator.config import get_settings
        settings = get_settings()

    db = Database(settings.db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.connect()
        app.state.db = db
        yield
        db.close()

    app = FastAPI(
        title="Infra-Auditor Aggregator",
        version=__version__,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # ── Middleware (applied bottom-up) ──────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(APIKeyMiddleware, api_keys=settings.api_keys)
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=settings.rate_limit_per_minute,
        window_seconds=60,
    )

    # Store settings
    app.state.settings = settings

    # ── Routes ─────────────────────────────────────────────
    app.include_router(reports.router)
    app.include_router(dashboard.router)
    app.include_router(compliance.router)
    app.include_router(health.router)
    app.include_router(drift.router)
    app.include_router(remediation.router)
    app.include_router(anomaly.router)

    # ── Static frontend serving ────────────────────────────
    frontend_dir = os.getenv(
        "INFRA_AUDITOR_FRONTEND_DIR",
        str(Path(__file__).resolve().parent.parent / "frontend" / "dist"),
    )
    if os.path.isdir(frontend_dir):
        app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dir, "assets")), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            """Serve the SPA index.html for all non-API routes."""
            file_path = os.path.join(frontend_dir, full_path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(os.path.join(frontend_dir, "index.html"))

    return app
