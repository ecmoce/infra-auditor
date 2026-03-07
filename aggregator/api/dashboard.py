"""Dashboard endpoints."""

from fastapi import APIRouter, Request

from aggregator.responses import success_response, error_response

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard")
async def dashboard_summary(request: Request):
    """GET /api/v1/dashboard — Overall dashboard data."""
    db = request.app.state.db
    data = db.get_dashboard_summary()
    return success_response(data)


@router.get("/dashboard/{region}")
async def dashboard_region(request: Request, region: str):
    """GET /api/v1/dashboard/{region} — Region-specific dashboard."""
    db = request.app.state.db
    data = db.get_dashboard_region(region)

    if data is None:
        return error_response(
            404, "NOT_FOUND", f"No data found for region '{region}'"
        )

    return success_response(data)
