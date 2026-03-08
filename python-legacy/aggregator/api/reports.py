"""Report submission and retrieval endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request

from aggregator.responses import success_response, error_response

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.post("/reports")
async def submit_report(request: Request):
    """POST /api/v1/reports — Agent report submission."""
    body = await request.json()
    db = request.app.state.db

    server_id = body.get("server_id")
    report_data = body.get("report")

    if not server_id or not report_data:
        return error_response(
            400,
            "VALIDATION_ERROR",
            "server_id and report are required",
        )

    result = db.insert_report(server_id, report_data)
    return success_response(result)


@router.get("/reports")
async def list_reports(
    request: Request,
    region: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
):
    """GET /api/v1/reports — List reports with filtering/pagination."""
    db = request.app.state.db
    data = db.list_reports(region=region, role=role, page=page, size=size)
    return success_response(data)


@router.get("/reports/{server_id}")
async def get_host_report(
    request: Request,
    server_id: str,
    include_history: bool = Query(False),
    limit: int = Query(10, ge=1, le=100),
):
    """GET /api/v1/reports/{host} — Host-specific report."""
    db = request.app.state.db
    data = db.get_report_by_host(
        server_id, include_history=include_history, limit=limit
    )

    if data is None:
        return error_response(
            404, "NOT_FOUND", f"No reports found for server '{server_id}'"
        )

    return success_response(data)
