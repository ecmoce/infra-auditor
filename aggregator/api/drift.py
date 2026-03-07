"""Drift detection API endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, Query, Request

from aggregator.responses import success_response, error_response

router = APIRouter(prefix="/api/v1", tags=["drift"])


@router.post("/drift/compare")
async def compare_reports(request: Request):
    """Compare two reports for drift.

    Body:
        {
            "current_report": { ... },
            "previous_report": { ... }
        }

    Or compare by server_id (uses latest two reports):
        {
            "server_id": "web-01"
        }
    """
    from infra_auditor.drift import DriftDetector

    body = await request.json()

    current = body.get("current_report")
    previous = body.get("previous_report")
    server_id = body.get("server_id")

    if current and previous:
        detector = DriftDetector.__new__(DriftDetector)
        drift = detector.compare(current, previous)
        return success_response(drift)

    if server_id:
        db = request.app.state.db
        # Get the two most recent reports for this server
        rows = db.conn.execute(
            """SELECT report_data FROM reports
               WHERE server_id = ?
               ORDER BY received_at DESC LIMIT 2""",
            (server_id,),
        ).fetchall()

        if len(rows) < 2:
            return error_response(
                404,
                "INSUFFICIENT_DATA",
                f"Need at least 2 reports for server '{server_id}' to compare. "
                f"Found {len(rows)}.",
            )

        current = json.loads(rows[0]["report_data"])
        previous = json.loads(rows[1]["report_data"])
        detector = DriftDetector.__new__(DriftDetector)
        drift = detector.compare(current, previous)
        return success_response(drift)

    return error_response(
        400,
        "VALIDATION_ERROR",
        "Provide either (current_report + previous_report) or server_id",
    )


@router.get("/drift/{server_id}")
async def get_drift(
    request: Request,
    server_id: str,
):
    """Get drift analysis for the latest two scans of a server."""
    db = request.app.state.db

    rows = db.conn.execute(
        """SELECT report_data, received_at FROM reports
           WHERE server_id = ?
           ORDER BY received_at DESC LIMIT 2""",
        (server_id,),
    ).fetchall()

    if len(rows) == 0:
        return error_response(
            404, "NOT_FOUND", f"No reports found for server '{server_id}'"
        )

    if len(rows) < 2:
        return success_response({
            "has_drift": False,
            "message": "Only one report available, no comparison possible",
            "latest_scan": rows[0]["received_at"],
        })

    from infra_auditor.drift import DriftDetector

    current = json.loads(rows[0]["report_data"])
    previous = json.loads(rows[1]["report_data"])
    detector = DriftDetector.__new__(DriftDetector)
    drift = detector.compare(current, previous)
    return success_response(drift)


@router.get("/drift/{server_id}/history")
async def get_drift_history(
    request: Request,
    server_id: str,
    limit: int = Query(10, ge=1, le=50),
):
    """Get compliance score history for a server (for trend visualization)."""
    db = request.app.state.db

    rows = db.conn.execute(
        """SELECT id, received_at, compliance_score
           FROM reports
           WHERE server_id = ?
           ORDER BY received_at DESC LIMIT ?""",
        (server_id, limit),
    ).fetchall()

    if not rows:
        return error_response(
            404, "NOT_FOUND", f"No reports found for server '{server_id}'"
        )

    history = [
        {
            "report_id": r["id"],
            "timestamp": r["received_at"],
            "compliance_score": r["compliance_score"],
        }
        for r in rows
    ]

    # Calculate trend
    scores = [r["compliance_score"] for r in rows]
    if len(scores) >= 2:
        trend = "improving" if scores[0] > scores[-1] else (
            "declining" if scores[0] < scores[-1] else "stable"
        )
    else:
        trend = "insufficient_data"

    return success_response({
        "server_id": server_id,
        "history": history,
        "trend": trend,
        "latest_score": scores[0] if scores else 0,
    })
