"""SQLite database layer for the aggregator."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    server_id TEXT NOT NULL,
    hostname TEXT,
    role TEXT,
    region TEXT,
    compliance_score REAL DEFAULT 0,
    severity_critical INTEGER DEFAULT 0,
    severity_warning INTEGER DEFAULT 0,
    severity_info INTEGER DEFAULT 0,
    report_data TEXT NOT NULL,
    received_at TEXT NOT NULL,
    scan_timestamp TEXT
);

CREATE INDEX IF NOT EXISTS idx_reports_server_id ON reports(server_id);
CREATE INDEX IF NOT EXISTS idx_reports_received_at ON reports(received_at);
CREATE INDEX IF NOT EXISTS idx_reports_region ON reports(region);
CREATE INDEX IF NOT EXISTS idx_reports_role ON reports(role);
"""


class Database:
    """Synchronous SQLite database wrapper."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Open connection and ensure schema exists."""
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    # ── Reports ──────────────────────────────────────────────────

    def insert_report(
        self,
        server_id: str,
        report_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Insert a report and return receipt info."""
        report_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Extract metadata from report
        server_info = report_data.get("server_info", {})
        compliance = report_data.get("compliance", {})
        severity = compliance.get("severity_summary", {})
        metadata = report_data.get("metadata", {})

        hostname = server_info.get("hostname", server_id)
        role = server_info.get("role", {})
        if isinstance(role, dict):
            role = role.get("detected", "unknown")
        region = server_info.get("region", "unknown")
        score = compliance.get("overall_score", 0)

        self.conn.execute(
            """INSERT INTO reports
               (id, server_id, hostname, role, region,
                compliance_score, severity_critical, severity_warning,
                severity_info, report_data, received_at, scan_timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report_id,
                server_id,
                hostname,
                role,
                region,
                score,
                severity.get("critical", 0),
                severity.get("warning", 0),
                severity.get("info", 0),
                json.dumps(report_data, ensure_ascii=False),
                now,
                metadata.get("timestamp", now),
            ),
        )
        self.conn.commit()

        return {
            "report_id": report_id,
            "received_at": now,
            "processing_status": "accepted",
        }

    def get_report_by_host(
        self,
        server_id: str,
        include_history: bool = False,
        limit: int = 10,
    ) -> Optional[Dict[str, Any]]:
        """Get latest report for a host, optionally with history."""
        row = self.conn.execute(
            """SELECT * FROM reports
               WHERE server_id = ?
               ORDER BY received_at DESC LIMIT 1""",
            (server_id,),
        ).fetchone()

        if not row:
            return None

        result: Dict[str, Any] = {
            "current_report": json.loads(row["report_data"]),
            "report_id": row["id"],
            "received_at": row["received_at"],
        }

        if include_history:
            rows = self.conn.execute(
                """SELECT id, received_at, compliance_score
                   FROM reports
                   WHERE server_id = ?
                   ORDER BY received_at DESC LIMIT ?""",
                (server_id, limit),
            ).fetchall()
            result["history"] = [
                {
                    "report_id": r["id"],
                    "timestamp": r["received_at"],
                    "compliance_score": r["compliance_score"],
                }
                for r in rows
            ]

        return result

    def list_reports(
        self,
        region: Optional[str] = None,
        role: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> Dict[str, Any]:
        """List reports with filtering and pagination.

        Returns the latest report per server_id.
        """
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

        # Get latest report per server using a subquery
        count_sql = (
            f"SELECT COUNT(DISTINCT server_id) FROM reports {where}"
        )
        total = self.conn.execute(count_sql, params).fetchone()[0]

        offset = (page - 1) * size
        # The subquery and outer join both need the where-clause params
        # but the outer SELECT doesn't repeat the WHERE, so params once.
        data_sql = f"""
            SELECT r.* FROM reports r
            INNER JOIN (
                SELECT server_id, MAX(received_at) as max_received
                FROM reports {where}
                GROUP BY server_id
            ) latest ON r.server_id = latest.server_id
                    AND r.received_at = latest.max_received
            ORDER BY r.received_at DESC
            LIMIT ? OFFSET ?
        """
        rows = self.conn.execute(
            data_sql, params + [size, offset]
        ).fetchall()

        servers = []
        for row in rows:
            servers.append({
                "server_id": row["server_id"],
                "hostname": row["hostname"],
                "role": row["role"],
                "region": row["region"],
                "last_scan": row["received_at"],
                "compliance_score": row["compliance_score"],
                "critical_issues": row["severity_critical"],
                "warning_issues": row["severity_warning"],
                "info_issues": row["severity_info"],
            })

        total_pages = max(1, (total + size - 1) // size)

        return {
            "servers": servers,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "total_pages": total_pages,
            },
        }

    # ── Dashboard / Aggregation ────────────────────────────────

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get overall dashboard summary."""
        # Use latest report per server
        latest_sql = """
            SELECT r.* FROM reports r
            INNER JOIN (
                SELECT server_id, MAX(received_at) as max_received
                FROM reports GROUP BY server_id
            ) latest ON r.server_id = latest.server_id
                    AND r.received_at = latest.max_received
        """
        rows = self.conn.execute(latest_sql).fetchall()

        if not rows:
            return {
                "overall": {
                    "total_servers": 0,
                    "average_compliance": 0,
                    "critical_issues": 0,
                    "warning_issues": 0,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                },
                "regions": [],
                "roles": [],
            }

        total_servers = len(rows)
        total_compliance = sum(r["compliance_score"] for r in rows)
        total_critical = sum(r["severity_critical"] for r in rows)
        total_warning = sum(r["severity_warning"] for r in rows)
        avg_compliance = round(total_compliance / total_servers, 1)

        last_updated = max(r["received_at"] for r in rows)

        # Region aggregation
        region_map: Dict[str, List] = {}
        for r in rows:
            region_map.setdefault(r["region"], []).append(r)

        regions = []
        for name, region_rows in sorted(region_map.items()):
            count = len(region_rows)
            avg = round(
                sum(r["compliance_score"] for r in region_rows) / count, 1
            )
            status = (
                "healthy" if avg >= 80
                else "warning" if avg >= 60
                else "critical"
            )
            regions.append({
                "name": name,
                "servers": count,
                "compliance": avg,
                "status": status,
            })

        # Role aggregation
        role_map: Dict[str, List] = {}
        for r in rows:
            role_map.setdefault(r["role"], []).append(r)

        roles = []
        for name, role_rows in sorted(role_map.items()):
            count = len(role_rows)
            avg = round(
                sum(r["compliance_score"] for r in role_rows) / count, 1
            )
            status = (
                "healthy" if avg >= 80
                else "warning" if avg >= 60
                else "critical"
            )
            roles.append({
                "name": name,
                "servers": count,
                "compliance": avg,
                "status": status,
            })

        return {
            "overall": {
                "total_servers": total_servers,
                "average_compliance": avg_compliance,
                "critical_issues": total_critical,
                "warning_issues": total_warning,
                "last_updated": last_updated,
            },
            "regions": regions,
            "roles": roles,
        }

    def get_dashboard_region(self, region: str) -> Optional[Dict[str, Any]]:
        """Get dashboard data for a specific region."""
        latest_sql = """
            SELECT r.* FROM reports r
            INNER JOIN (
                SELECT server_id, MAX(received_at) as max_received
                FROM reports WHERE region = ?
                GROUP BY server_id
            ) latest ON r.server_id = latest.server_id
                    AND r.received_at = latest.max_received
        """
        rows = self.conn.execute(latest_sql, (region,)).fetchall()

        if not rows:
            return None

        total = len(rows)
        avg_compliance = round(
            sum(r["compliance_score"] for r in rows) / total, 1
        )
        total_critical = sum(r["severity_critical"] for r in rows)
        total_warning = sum(r["severity_warning"] for r in rows)

        # Per-role breakdown
        role_map: Dict[str, List] = {}
        for r in rows:
            role_map.setdefault(r["role"], []).append(r)

        roles = []
        for name, role_rows in sorted(role_map.items()):
            count = len(role_rows)
            avg = round(
                sum(r["compliance_score"] for r in role_rows) / count, 1
            )
            roles.append({
                "name": name,
                "servers": count,
                "compliance": avg,
            })

        servers = []
        for r in rows:
            servers.append({
                "server_id": r["server_id"],
                "hostname": r["hostname"],
                "role": r["role"],
                "compliance_score": r["compliance_score"],
                "critical_issues": r["severity_critical"],
                "warning_issues": r["severity_warning"],
            })

        return {
            "region": region,
            "total_servers": total,
            "average_compliance": avg_compliance,
            "critical_issues": total_critical,
            "warning_issues": total_warning,
            "roles": roles,
            "servers": servers,
        }

    def get_compliance_summary(self) -> Dict[str, Any]:
        """Get compliance status across all servers."""
        latest_sql = """
            SELECT r.* FROM reports r
            INNER JOIN (
                SELECT server_id, MAX(received_at) as max_received
                FROM reports GROUP BY server_id
            ) latest ON r.server_id = latest.server_id
                    AND r.received_at = latest.max_received
        """
        rows = self.conn.execute(latest_sql).fetchall()

        if not rows:
            return {
                "total_servers": 0,
                "average_score": 0,
                "distribution": {"pass": 0, "warn": 0, "fail": 0},
                "by_region": [],
                "by_role": [],
            }

        total = len(rows)
        avg_score = round(
            sum(r["compliance_score"] for r in rows) / total, 1
        )

        # Distribution: pass >= 80, warn >= 60, fail < 60
        dist = {"pass": 0, "warn": 0, "fail": 0}
        for r in rows:
            s = r["compliance_score"]
            if s >= 80:
                dist["pass"] += 1
            elif s >= 60:
                dist["warn"] += 1
            else:
                dist["fail"] += 1

        # By region
        region_map: Dict[str, List] = {}
        for r in rows:
            region_map.setdefault(r["region"], []).append(r)

        by_region = []
        for name, rrows in sorted(region_map.items()):
            avg = round(
                sum(r["compliance_score"] for r in rrows) / len(rrows), 1
            )
            by_region.append({
                "region": name,
                "servers": len(rrows),
                "average_score": avg,
            })

        # By role
        role_map: Dict[str, List] = {}
        for r in rows:
            role_map.setdefault(r["role"], []).append(r)

        by_role = []
        for name, rrows in sorted(role_map.items()):
            avg = round(
                sum(r["compliance_score"] for r in rrows) / len(rrows), 1
            )
            by_role.append({
                "role": name,
                "servers": len(rrows),
                "average_score": avg,
            })

        return {
            "total_servers": total,
            "average_score": avg_score,
            "distribution": dist,
            "by_region": by_region,
            "by_role": by_role,
        }

    # ── Maintenance ────────────────────────────────────────────

    def cleanup_old_reports(self, retention_days: int = 30) -> int:
        """Delete reports older than retention_days. Returns deleted count."""
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=retention_days)
        ).isoformat()
        cursor = self.conn.execute(
            "DELETE FROM reports WHERE received_at < ?", (cutoff,)
        )
        self.conn.commit()
        return cursor.rowcount

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics for health checks."""
        total_reports = self.conn.execute(
            "SELECT COUNT(*) FROM reports"
        ).fetchone()[0]
        unique_servers = self.conn.execute(
            "SELECT COUNT(DISTINCT server_id) FROM reports"
        ).fetchone()[0]

        latest_row = self.conn.execute(
            "SELECT MAX(received_at) FROM reports"
        ).fetchone()
        last_report = latest_row[0] if latest_row[0] else None

        return {
            "total_reports": total_reports,
            "unique_servers": unique_servers,
            "last_report_received": last_report,
        }
