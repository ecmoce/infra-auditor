"""Health check endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from aggregator import __version__
from aggregator.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health_check(request: Request):
    """GET /api/v1/health — Service health check."""
    db = request.app.state.db
    db_stats = db.get_stats()

    data = {
        "service": "healthy",
        "version": __version__,
        "database": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_reports": db_stats["total_reports"],
        "unique_servers": db_stats["unique_servers"],
        "last_report_received": db_stats["last_report_received"],
    }
    return success_response(data)
