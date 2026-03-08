"""Compliance status endpoint."""

from fastapi import APIRouter, Request

from aggregator.responses import success_response

router = APIRouter(prefix="/api/v1", tags=["compliance"])


@router.get("/compliance")
async def compliance_status(request: Request):
    """GET /api/v1/compliance — Compliance overview."""
    db = request.app.state.db
    data = db.get_compliance_summary()
    return success_response(data)
