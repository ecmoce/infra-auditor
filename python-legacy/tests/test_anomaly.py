"""Tests for anomaly detection API endpoints."""

import json
import pytest
from fastapi.testclient import TestClient

from aggregator.app import create_app
from aggregator.config import Settings


@pytest.fixture
def app():
    settings = Settings(db_path=":memory:", debug=True)
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


def _make_report(
    server_id: str,
    hostname: str,
    role: str,
    region: str,
    score: float,
    results: list | None = None,
    critical: int = 0,
    warning: int = 0,
):
    """Helper to create a report payload."""
    if results is None:
        results = [
            {"rule": "vm.swappiness", "status": "pass", "actual": 10, "expected": 10, "severity": "warning"},
            {"rule": "net.core.somaxconn", "status": "pass", "actual": 4096, "expected": 4096, "severity": "warning"},
        ]

    return {
        "server_info": {
            "hostname": hostname,
            "role": {"detected": role},
            "region": region,
        },
        "compliance": {
            "overall_score": score,
            "severity_summary": {
                "critical": critical,
                "warning": warning,
                "info": 0,
            },
        },
        "results": results,
        "metadata": {"timestamp": "2026-03-08T00:00:00Z"},
    }


def _seed_multi_region(client):
    """Seed database with multi-region, multi-role data."""
    reports = [
        # ap-northeast-1
        ("web-01", "web-01.apne1", "web", "ap-northeast-1", 85.0, None, 0, 2),
        ("web-02", "web-02.apne1", "web", "ap-northeast-1", 80.0, None, 0, 3),
        ("db-01", "db-01.apne1", "database", "ap-northeast-1", 70.0, None, 1, 4),
        # us-east-1
        ("web-03", "web-03.use1", "web", "us-east-1", 60.0, None, 2, 5),
        ("web-04", "web-04.use1", "web", "us-east-1", 55.0, None, 3, 6),
        ("db-02", "db-02.use1", "database", "us-east-1", 50.0, None, 4, 7),
        # eu-west-1
        ("web-05", "web-05.euw1", "web", "eu-west-1", 90.0, None, 0, 1),
        ("db-03", "db-03.euw1", "database", "eu-west-1", 88.0, None, 0, 1),
    ]

    for args in reports:
        report = _make_report(*args)
        resp = client.post("/api/v1/reports", json={"server_id": args[0], "report": report})
        assert resp.status_code == 200


def _seed_config_drift(client):
    """Seed data with config drift between same-role servers."""
    results_pass = [
        {"rule": "vm.swappiness", "status": "pass", "actual": 10, "expected": 10, "severity": "warning"},
        {"rule": "net.core.somaxconn", "status": "pass", "actual": 4096, "expected": 4096, "severity": "warning"},
        {"rule": "fs.file-max", "status": "pass", "actual": 2097152, "expected": 2097152, "severity": "critical"},
    ]
    results_drift = [
        {"rule": "vm.swappiness", "status": "fail", "actual": 60, "expected": 10, "severity": "warning"},
        {"rule": "net.core.somaxconn", "status": "pass", "actual": 4096, "expected": 4096, "severity": "warning"},
        {"rule": "fs.file-max", "status": "fail", "actual": 65536, "expected": 2097152, "severity": "critical"},
    ]

    reports = [
        ("web-a", "web-a", "web", "ap-northeast-1", 90.0, results_pass),
        ("web-b", "web-b", "web", "ap-northeast-1", 85.0, results_pass),
        ("web-c", "web-c", "web", "us-east-1", 50.0, results_drift),
    ]

    for sid, hostname, role, region, score, results in reports:
        report = _make_report(sid, hostname, role, region, score, results)
        resp = client.post("/api/v1/reports", json={"server_id": sid, "report": report})
        assert resp.status_code == 200


# ── Config Drift Tests ──────────────────────────────────────────


class TestConfigDrift:
    def test_no_data(self, client):
        resp = client.get("/api/v1/anomaly/config-drift")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["groups"] == []
        assert data["total_mismatches"] == 0

    def test_detect_mismatches(self, client):
        _seed_config_drift(client)
        resp = client.get("/api/v1/anomaly/config-drift")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_mismatches"] > 0
        assert len(data["groups"]) > 0

        web_group = data["groups"][0]
        assert web_group["role"] == "web"
        assert web_group["server_count"] == 3
        assert web_group["mismatch_count"] > 0

    def test_filter_by_role(self, client):
        _seed_config_drift(client)
        resp = client.get("/api/v1/anomaly/config-drift?role=web")
        assert resp.status_code == 200
        data = resp.json()["data"]
        for g in data["groups"]:
            assert g["role"] == "web"

    def test_filter_by_region(self, client):
        _seed_config_drift(client)
        resp = client.get("/api/v1/anomaly/config-drift?region=ap-northeast-1")
        assert resp.status_code == 200
        assert resp.json()["data"]["total_mismatches"] == 0  # both pass in same region

    def test_drift_by_role_detail(self, client):
        _seed_config_drift(client)
        resp = client.get("/api/v1/anomaly/config-drift/web")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["role"] == "web"
        assert len(data["mismatches"]) > 0
        assert len(data["recommendations"]) > 0

        # Check recommendations have correct structure
        rec = data["recommendations"][0]
        assert "rule" in rec
        assert "priority" in rec
        assert "recommendation" in rec
        assert "affected_servers" in rec

    def test_drift_by_role_insufficient(self, client):
        # Only one server with role 'lonely'
        report = _make_report("lonely-01", "lonely", "lonely_role", "ap-northeast-1", 80.0)
        client.post("/api/v1/reports", json={"server_id": "lonely-01", "report": report})

        resp = client.get("/api/v1/anomaly/config-drift/lonely_role")
        assert resp.status_code == 404


# ── Region Comparison Tests ─────────────────────────────────────


class TestRegionComparison:
    def test_no_data(self, client):
        resp = client.get("/api/v1/anomaly/region-comparison")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["regions"] == []
        assert data["best_region"] is None

    def test_multi_region(self, client):
        _seed_multi_region(client)
        resp = client.get("/api/v1/anomaly/region-comparison")
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert len(data["regions"]) == 3

        # Check best/worst
        assert data["best_region"] is not None
        assert data["worst_region"] is not None
        assert data["best_region"]["score"] >= data["worst_region"]["score"]

        # eu-west-1 should be best (90, 88)
        assert data["best_region"]["name"] == "eu-west-1"

    def test_cross_region_drift(self, client):
        _seed_multi_region(client)
        resp = client.get("/api/v1/anomaly/region-comparison")
        data = resp.json()["data"]

        # web role has big drift: eu-west-1 (90) vs us-east-1 (57.5)
        assert len(data["cross_region_drift"]) > 0
        web_drift = [d for d in data["cross_region_drift"] if d["role"] == "web"]
        assert len(web_drift) > 0
        assert web_drift[0]["drift_percentage"] > 5

    def test_region_detail_fields(self, client):
        _seed_multi_region(client)
        resp = client.get("/api/v1/anomaly/region-comparison")
        data = resp.json()["data"]

        for region in data["regions"]:
            assert "region" in region
            assert "server_count" in region
            assert "average_compliance" in region
            assert "min_compliance" in region
            assert "max_compliance" in region
            assert "score_variance" in region
            assert "critical_issues" in region
            assert "warning_issues" in region
            assert "roles" in region


# ── Alerts Tests ────────────────────────────────────────────────


class TestAlerts:
    def test_no_data(self, client):
        resp = client.get("/api/v1/anomaly/alerts")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["alerts"] == []
        assert data["summary"]["total"] == 0

    def test_generates_alerts(self, client):
        _seed_multi_region(client)
        resp = client.get("/api/v1/anomaly/alerts")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["summary"]["total"] > 0

        # Should have at least critical alerts for low-scoring servers
        assert data["summary"]["critical"] > 0

    def test_filter_by_severity(self, client):
        _seed_multi_region(client)
        resp = client.get("/api/v1/anomaly/alerts?severity=critical")
        assert resp.status_code == 200
        data = resp.json()["data"]
        for alert in data["alerts"]:
            assert alert["severity"] == "critical"

    def test_filter_by_region(self, client):
        _seed_multi_region(client)
        resp = client.get("/api/v1/anomaly/alerts?region=eu-west-1")
        assert resp.status_code == 200
        data = resp.json()["data"]
        # eu-west-1 has high scores, should have few/no alerts
        assert data["summary"]["critical"] == 0

    def test_alert_structure(self, client):
        _seed_multi_region(client)
        resp = client.get("/api/v1/anomaly/alerts")
        data = resp.json()["data"]
        if data["alerts"]:
            alert = data["alerts"][0]
            assert "severity" in alert
            assert "type" in alert
            assert "message" in alert
            assert "value" in alert
            assert "threshold" in alert

    def test_sorted_critical_first(self, client):
        _seed_multi_region(client)
        resp = client.get("/api/v1/anomaly/alerts")
        data = resp.json()["data"]
        alerts = data["alerts"]
        if len(alerts) >= 2:
            # Check critical comes before warning
            critical_indices = [i for i, a in enumerate(alerts) if a["severity"] == "critical"]
            warning_indices = [i for i, a in enumerate(alerts) if a["severity"] == "warning"]
            if critical_indices and warning_indices:
                assert max(critical_indices) < min(warning_indices)

    def test_region_drift_alert(self, client):
        _seed_multi_region(client)
        resp = client.get("/api/v1/anomaly/alerts")
        data = resp.json()["data"]

        drift_alerts = [a for a in data["alerts"] if a["type"] == "region_drift"]
        assert len(drift_alerts) > 0

    def test_update_thresholds(self, client):
        resp = client.put(
            "/api/v1/anomaly/thresholds",
            json={"critical_score": 50, "warning_score": 80},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["thresholds"]["critical_score"] == 50
        assert data["thresholds"]["warning_score"] == 80

    def test_update_thresholds_validation(self, client):
        resp = client.put(
            "/api/v1/anomaly/thresholds",
            json={"invalid_key": 50},
        )
        assert resp.status_code == 400

    def test_update_thresholds_negative(self, client):
        resp = client.put(
            "/api/v1/anomaly/thresholds",
            json={"critical_score": -10},
        )
        assert resp.status_code == 400

    def test_thresholds_affect_alerts(self, client):
        _seed_multi_region(client)

        # With default thresholds
        resp1 = client.get("/api/v1/anomaly/alerts")
        count1 = resp1.json()["data"]["summary"]["total"]

        # Lower thresholds — fewer alerts
        client.put(
            "/api/v1/anomaly/thresholds",
            json={"critical_score": 10, "warning_score": 20, "critical_issues_threshold": 100, "drift_threshold": 100},
        )
        resp2 = client.get("/api/v1/anomaly/alerts")
        count2 = resp2.json()["data"]["summary"]["total"]

        assert count2 < count1
