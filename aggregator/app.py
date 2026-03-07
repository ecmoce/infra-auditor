"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aggregator import __version__
from aggregator.config import Settings
from aggregator.database import Database
from aggregator.middleware import APIKeyMiddleware, RateLimitMiddleware
from aggregator.api import reports, dashboard, compliance, health


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

    return app
