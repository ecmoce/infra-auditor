"""Anomaly detection & multi-region comparison API endpoints."""

import json
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request

from aggregator.responses import success_response, error_response

router = APIRouter(prefix="/api/v1", tags=["anomaly"])


# ── Config drift detection (same-role servers) ──────────────────

@router.get("/anomaly/config-drift")
async def detect_config_drift(
    request: Request,
    role: Optional[str] = Query(None, description="Filter by role"),
    region: Optional[str] = Query(None, description="Filter by region"),
):
    """Detect configuration inconsistencies among servers with the same role.

    Compares tuning parameters across servers sharing a role and flags
    values that differ from the majority (mode).
    """
    db = request.app.state.db
    rows = _latest_reports(db, region=region, role=role)

    if not rows:
        return success_response({"groups": [], "total_mismatches": 0})

    # Group by role
    role_groups: Dict[str, List[Dict]] = defaultdict(list)
    for r in rows:
        role_groups[r["role"]].append(r)

    groups = []
    total_mismatches = 0

    for role_name, servers in sorted(role_groups.items()):
        if len(servers) < 2:
            continue

        mismatches = _find_config_mismatches(servers)
        total_mismatches += len(mismatches)

        groups.append({
            "role": role_name,
            "server_count": len(servers),
            "servers": [
                {"server_id": s["server_id"], "hostname": s["hostname"], "region": s["region"]}
                for s in servers
            ],
            "mismatches": mismatches,
            "mismatch_count": len(mismatches),
        })

    return success_response({
        "groups": groups,
        "total_mismatches": total_mismatches,
    })


@router.get("/anomaly/config-drift/{role}")
async def detect_config_drift_by_role(request: Request, role: str):
    """Get detailed config drift for a specific role."""
    db = request.app.state.db
    rows = _latest_reports(db, role=role)

    if len(rows) < 2:
        return error_response(
            404,
            "INSUFFICIENT_DATA",
            f"Need at least 2 servers with role '{role}'. Found {len(rows)}.",
        )

    mismatches = _find_config_mismatches(rows)
    recommendations = _generate_standardization_recommendations(mismatches)

    return success_response({
        "role": role,
        "server_count": len(rows),
        "servers": [
            {
                "server_id": s["server_id"],
                "hostname": s["hostname"],
                "region": s["region"],
                "compliance_score": s["compliance_score"],
            }
            for s in rows
        ],
        "mismatches": mismatches,
        "recommendations": recommendations,
    })


# ── Multi-region comparison ─────────────────────────────────────

@router.get("/anomaly/region-comparison")
async def compare_regions(request: Request):
    """Compare compliance and performance across all regions."""
    db = request.app.state.db
    rows = _latest_reports(db)

    if not rows:
        return success_response({
            "regions": [],
            "best_region": None,
            "worst_region": None,
            "cross_region_drift": [],
        })

    region_map: Dict[str, List[Dict]] = defaultdict(list)
    for r in rows:
        region_map[r["region"]].append(r)

    regions = []
    for name, region_rows in sorted(region_map.items()):
        scores = [r["compliance_score"] for r in region_rows]
        critical = sum(r["severity_critical"] for r in region_rows)
        warning = sum(r["severity_warning"] for r in region_rows)

        avg_score = round(sum(scores) / len(scores), 1)
        min_score = min(scores)
        max_score = max(scores)

        # Role breakdown
        role_map: Dict[str, List[float]] = defaultdict(list)
        for r in region_rows:
            role_map[r["role"]].append(r["compliance_score"])

        role_breakdown = [
            {
                "role": role,
                "servers": len(ss),
                "average_score": round(sum(ss) / len(ss), 1),
            }
            for role, ss in sorted(role_map.items())
        ]

        regions.append({
            "region": name,
            "server_count": len(region_rows),
            "average_compliance": avg_score,
            "min_compliance": min_score,
            "max_compliance": max_score,
            "score_variance": round(max_score - min_score, 1),
            "critical_issues": critical,
            "warning_issues": warning,
            "roles": role_breakdown,
        })

    # Identify best/worst
    best = max(regions, key=lambda r: r["average_compliance"])
    worst = min(regions, key=lambda r: r["average_compliance"])

    # Cross-region drift: same role, different scores across regions
    cross_drift = _cross_region_drift(region_map)

    return success_response({
        "regions": regions,
        "best_region": {
            "name": best["region"],
            "score": best["average_compliance"],
        },
        "worst_region": {
            "name": worst["region"],
            "score": worst["average_compliance"],
        },
        "cross_region_drift": cross_drift,
    })


# ── Alerts ──────────────────────────────────────────────────────

@router.get("/anomaly/alerts")
async def get_alerts(
    request: Request,
    severity: Optional[str] = Query(None, description="Filter: critical, warning"),
    region: Optional[str] = Query(None, description="Filter by region"),
):
    """Generate alerts based on anomaly detection."""
    db = request.app.state.db
    rows = _latest_reports(db, region=region)

    alerts: List[Dict[str, Any]] = []

    # Get alert thresholds from settings (or defaults)
    settings = request.app.state.settings
    thresholds = getattr(settings, "alert_thresholds", None) or {
        "critical_score": 40,
        "warning_score": 70,
        "critical_issues_threshold": 3,
        "drift_threshold": 20,
    }

    for r in rows:
        # Critical: score below threshold
        if r["compliance_score"] < thresholds["critical_score"]:
            alerts.append({
                "severity": "critical",
                "type": "low_compliance",
                "server_id": r["server_id"],
                "hostname": r["hostname"],
                "region": r["region"],
                "role": r["role"],
                "message": f"Compliance score {r['compliance_score']}% is critically low (threshold: {thresholds['critical_score']}%)",
                "value": r["compliance_score"],
                "threshold": thresholds["critical_score"],
            })
        elif r["compliance_score"] < thresholds["warning_score"]:
            alerts.append({
                "severity": "warning",
                "type": "low_compliance",
                "server_id": r["server_id"],
                "hostname": r["hostname"],
                "region": r["region"],
                "role": r["role"],
                "message": f"Compliance score {r['compliance_score']}% is below warning threshold (threshold: {thresholds['warning_score']}%)",
                "value": r["compliance_score"],
                "threshold": thresholds["warning_score"],
            })

        # Critical issues count
        if r["severity_critical"] >= thresholds["critical_issues_threshold"]:
            alerts.append({
                "severity": "critical",
                "type": "excessive_critical_issues",
                "server_id": r["server_id"],
                "hostname": r["hostname"],
                "region": r["region"],
                "role": r["role"],
                "message": f"Server has {r['severity_critical']} critical issues (threshold: {thresholds['critical_issues_threshold']})",
                "value": r["severity_critical"],
                "threshold": thresholds["critical_issues_threshold"],
            })

    # Cross-region drift alerts
    region_map: Dict[str, List[Dict]] = defaultdict(list)
    for r in rows:
        region_map[r["region"]].append(r)

    if len(region_map) >= 2:
        region_scores = {}
        for name, rrows in region_map.items():
            avg = round(sum(r["compliance_score"] for r in rrows) / len(rrows), 1)
            region_scores[name] = avg

        scores_list = list(region_scores.values())
        max_drift = max(scores_list) - min(scores_list)

        if max_drift >= thresholds["drift_threshold"]:
            best_name = max(region_scores, key=region_scores.get)
            worst_name = min(region_scores, key=region_scores.get)
            alerts.append({
                "severity": "warning",
                "type": "region_drift",
                "server_id": None,
                "hostname": None,
                "region": f"{worst_name} vs {best_name}",
                "role": None,
                "message": f"Region compliance drift of {max_drift}% detected between {worst_name} ({region_scores[worst_name]}%) and {best_name} ({region_scores[best_name]}%)",
                "value": max_drift,
                "threshold": thresholds["drift_threshold"],
            })

    # Filter by severity if requested
    if severity:
        alerts = [a for a in alerts if a["severity"] == severity]

    # Sort: critical first, then warning
    severity_order = {"critical": 0, "warning": 1}
    alerts.sort(key=lambda a: severity_order.get(a["severity"], 99))

    return success_response({
        "alerts": alerts,
        "summary": {
            "total": len(alerts),
            "critical": sum(1 for a in alerts if a["severity"] == "critical"),
            "warning": sum(1 for a in alerts if a["severity"] == "warning"),
        },
    })


@router.put("/anomaly/thresholds")
async def update_thresholds(request: Request):
    """Update alert thresholds.

    Body:
        {
            "critical_score": 40,
            "warning_score": 70,
            "critical_issues_threshold": 3,
            "drift_threshold": 20
        }
    """
    body = await request.json()

    valid_keys = {"critical_score", "warning_score", "critical_issues_threshold", "drift_threshold"}
    thresholds = {k: v for k, v in body.items() if k in valid_keys}

    if not thresholds:
        return error_response(400, "VALIDATION_ERROR", f"Provide at least one of: {valid_keys}")

    # Validate values
    for k, v in thresholds.items():
        if not isinstance(v, (int, float)) or v < 0:
            return error_response(400, "VALIDATION_ERROR", f"'{k}' must be a non-negative number")

    # Store in settings
    current = getattr(request.app.state.settings, "alert_thresholds", None) or {
        "critical_score": 40,
        "warning_score": 70,
        "critical_issues_threshold": 3,
        "drift_threshold": 20,
    }
    current.update(thresholds)
    request.app.state.settings.alert_thresholds = current

    return success_response({"thresholds": current})


# ── Helpers ─────────────────────────────────────────────────────

def _latest_reports(
    db,
    region: Optional[str] = None,
    role: Optional[str] = None,
) -> List[Dict]:
    """Get latest report per server, with optional filters."""
    conditions: List[str] = []
    params: List[Any] = []

    if region:
        conditions.append("region = ?")
        params.append(region)
    if role:
        conditions.append("role = ?")
        params.append(role)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT r.* FROM reports r
        INNER JOIN (
            SELECT server_id, MAX(received_at) as max_received
            FROM reports {where}
            GROUP BY server_id
        ) latest ON r.server_id = latest.server_id
                AND r.received_at = latest.max_received
    """
    rows = db.conn.execute(sql, params).fetchall()

    return [
        {
            "server_id": r["server_id"],
            "hostname": r["hostname"],
            "role": r["role"],
            "region": r["region"],
            "compliance_score": r["compliance_score"],
            "severity_critical": r["severity_critical"],
            "severity_warning": r["severity_warning"],
            "severity_info": r["severity_info"],
            "report_data": r["report_data"],
            "received_at": r["received_at"],
        }
        for r in rows
    ]


def _find_config_mismatches(servers: List[Dict]) -> List[Dict[str, Any]]:
    """Compare tuning results across servers and find mismatches."""
    mismatches = []

    # Extract tuning results from each server's report
    server_configs: Dict[str, Dict[str, Any]] = {}
    for s in servers:
        data = json.loads(s["report_data"]) if isinstance(s["report_data"], str) else s["report_data"]
        results = data.get("results", [])

        configs = {}
        for result in results:
            key = result.get("rule", result.get("name", "unknown"))
            configs[key] = {
                "status": result.get("status", "unknown"),
                "actual": result.get("actual"),
                "expected": result.get("expected"),
                "severity": result.get("severity", "info"),
            }
        server_configs[s["server_id"]] = configs

    # Find all unique config keys
    all_keys = set()
    for configs in server_configs.values():
        all_keys.update(configs.keys())

    # Check each key for inconsistencies
    for key in sorted(all_keys):
        values_by_server = {}
        for sid, configs in server_configs.items():
            if key in configs:
                values_by_server[sid] = configs[key]

        if len(values_by_server) < 2:
            continue

        # Check if statuses differ
        statuses = [v["status"] for v in values_by_server.values()]
        if len(set(statuses)) > 1:
            # Find the mode (most common status)
            from collections import Counter
            status_counts = Counter(statuses)
            mode_status = status_counts.most_common(1)[0][0]

            deviating = []
            conforming = []
            for sid, val in values_by_server.items():
                entry = {"server_id": sid, **val}
                if val["status"] != mode_status:
                    deviating.append(entry)
                else:
                    conforming.append(entry)

            severity = max(
                (v.get("severity", "info") for v in values_by_server.values()),
                key=lambda s: {"critical": 3, "warning": 2, "info": 1}.get(s, 0),
            )

            mismatches.append({
                "rule": key,
                "expected_status": mode_status,
                "severity": severity,
                "deviating_servers": deviating,
                "conforming_servers": conforming,
                "total_checked": len(values_by_server),
            })

    return mismatches


def _generate_standardization_recommendations(mismatches: List[Dict]) -> List[Dict]:
    """Generate recommendations to standardize configurations."""
    recommendations = []

    for m in mismatches:
        rec = {
            "rule": m["rule"],
            "priority": m["severity"],
            "recommendation": f"Standardize '{m['rule']}' across all servers. "
                            f"The majority ({len(m['conforming_servers'])}/{m['total_checked']}) "
                            f"have status '{m['expected_status']}'.",
            "affected_servers": [s["server_id"] for s in m["deviating_servers"]],
            "target_status": m["expected_status"],
        }
        recommendations.append(rec)

    # Sort by priority
    priority_order = {"critical": 0, "warning": 1, "info": 2}
    recommendations.sort(key=lambda r: priority_order.get(r["priority"], 99))

    return recommendations


def _cross_region_drift(region_map: Dict[str, List[Dict]]) -> List[Dict]:
    """Detect drift in the same role across different regions."""
    # Collect role scores per region
    role_region_scores: Dict[str, Dict[str, float]] = defaultdict(dict)

    for region, servers in region_map.items():
        role_scores: Dict[str, List[float]] = defaultdict(list)
        for s in servers:
            role_scores[s["role"]].append(s["compliance_score"])

        for role, scores in role_scores.items():
            role_region_scores[role][region] = round(sum(scores) / len(scores), 1)

    drift_items = []
    for role, region_scores in sorted(role_region_scores.items()):
        if len(region_scores) < 2:
            continue

        scores = list(region_scores.values())
        drift = max(scores) - min(scores)

        if drift > 5:  # Only report meaningful drift
            best_region = max(region_scores, key=region_scores.get)
            worst_region = min(region_scores, key=region_scores.get)

            drift_items.append({
                "role": role,
                "drift_percentage": drift,
                "best_region": best_region,
                "best_score": region_scores[best_region],
                "worst_region": worst_region,
                "worst_score": region_scores[worst_region],
                "all_regions": region_scores,
            })

    drift_items.sort(key=lambda d: d["drift_percentage"], reverse=True)
    return drift_items
