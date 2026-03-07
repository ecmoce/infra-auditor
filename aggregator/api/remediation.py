"""Remediation API endpoints."""

import json
from typing import List, Optional

from fastapi import APIRouter, Query, Request

from aggregator.responses import success_response, error_response

router = APIRouter(prefix="/api/v1", tags=["remediation"])


@router.post("/remediation/generate")
async def generate_remediation(request: Request):
    """Generate a remediation script from a report.

    Body:
        {
            "report": { ... full scan report ... },
            "categories": ["cpu", "memory"],   // optional filter
            "severities": ["critical", "warning"]  // optional filter
        }

    Or generate from the latest report for a server:
        {
            "server_id": "web-01",
            "categories": ["cpu"],
            "severities": ["critical"]
        }
    """
    from infra_auditor.remediation import RemediationGenerator

    body = await request.json()
    db = request.app.state.db

    report = body.get("report")
    server_id = body.get("server_id")
    categories = body.get("categories")
    severities = body.get("severities")

    if not report and server_id:
        row = db.conn.execute(
            """SELECT report_data FROM reports
               WHERE server_id = ?
               ORDER BY received_at DESC LIMIT 1""",
            (server_id,),
        ).fetchone()

        if not row:
            return error_response(
                404,
                "NOT_FOUND",
                f"No reports found for server '{server_id}'",
            )
        report = json.loads(row["report_data"])

    if not report:
        return error_response(
            400,
            "VALIDATION_ERROR",
            "Provide either 'report' object or 'server_id'",
        )

    gen = RemediationGenerator()
    result = gen.generate(
        report,
        categories=categories,
        severities=severities,
    )

    return success_response(result)


@router.get("/remediation/{server_id}")
async def get_remediation(
    request: Request,
    server_id: str,
    severity: Optional[str] = Query(None),
):
    """Get remediation info for a server's latest scan.

    Returns non-compliant items with fix commands.
    """
    db = request.app.state.db

    row = db.conn.execute(
        """SELECT report_data FROM reports
           WHERE server_id = ?
           ORDER BY received_at DESC LIMIT 1""",
        (server_id,),
    ).fetchone()

    if not row:
        return error_response(
            404, "NOT_FOUND", f"No reports found for server '{server_id}'"
        )

    report = json.loads(row["report_data"])
    scan_results = report.get("scan_results", {})

    non_compliant = []
    for cat, items in scan_results.items():
        for item in items:
            if item.get("compliance", True):
                continue
            if severity and item.get("severity") != severity:
                continue
            non_compliant.append({
                "item": item.get("item", ""),
                "category": item.get("category", ""),
                "severity": item.get("severity", ""),
                "current_value": item.get("current_value", ""),
                "recommended_value": item.get("recommended_value", ""),
                "description": item.get("description", ""),
                "remediation": item.get("remediation", {}),
            })

    # Sort by severity (critical first)
    sev_order = {"critical": 0, "warning": 1, "info": 2}
    non_compliant.sort(key=lambda x: sev_order.get(x["severity"], 3))

    return success_response({
        "server_id": server_id,
        "total_non_compliant": len(non_compliant),
        "items": non_compliant,
    })
