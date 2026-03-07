"""Tests for the Aggregator server: database, API endpoints, middleware."""

import json
import time

import pytest
from httpx import AsyncClient, ASGITransport

from aggregator.app import create_app
from aggregator.config import Settings
from aggregator.database import Database


# ── Fixtures ─────────────────────────────────────────────────────

def _settings(**overrides):
    defaults = dict(
        host="127.0.0.1",
        port=8443,
        debug=False,
        db_path=":memory:",
        api_keys=[],
        cors_origins=["*"],
        rate_limit_per_minute=1000,
        retention_days=30,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _sample_report(role="compute", score=85, critical=1, warning=3, info=5):
    return {
        "metadata": {
            "version": "1.0.0",
            "agent_version": "0.1.0",
            "scan_id": "test-scan-001",
            "timestamp": "2024-03-07T07:48:00Z",
            "scan_duration_seconds": 2.5,
            "scan_type": "full",
        },
        "server_info": {
            "hostname": "test-host",
            "role": {"detected": role},
            "region": "seoul",
        },
        "compliance": {
            "overall_score": score,
            "severity_summary": {
                "critical": critical,
                "warning": warning,
                "info": info,
            },
        },
        "scan_results": {},
        "errors": [],
    }


@pytest.fixture
def db():
    d = Database(":memory:")
    d.connect()
    yield d
    d.close()


@pytest.fixture
def app():
    settings = _settings()
    application = create_app(settings)
    # Manually connect db for testing since lifespan won't run with httpx
    application.state.db = Database(":memory:")
    application.state.db.connect()
    yield application
    application.state.db.close()


@pytest.fixture
def client(app):
    """Provide a test client that works with sync tests via anyio."""
    return app


# ── Database Unit Tests ──────────────────────────────────────────

class TestDatabase:
    def test_insert_and_retrieve(self, db):
        report = _sample_report()
        result = db.insert_report("server-01", report)

        assert result["report_id"]
        assert result["processing_status"] == "accepted"

        fetched = db.get_report_by_host("server-01")
        assert fetched is not None
        assert fetched["current_report"]["compliance"]["overall_score"] == 85

    def test_get_nonexistent_host(self, db):
        assert db.get_report_by_host("nope") is None

    def test_history(self, db):
        for i in range(3):
            r = _sample_report(score=70 + i * 10)
            db.insert_report("server-01", r)

        data = db.get_report_by_host("server-01", include_history=True, limit=5)
        assert len(data["history"]) == 3
        # Most recent first
        assert data["history"][0]["compliance_score"] >= data["history"][-1]["compliance_score"]

    def test_list_reports_pagination(self, db):
        for i in range(5):
            db.insert_report(f"server-{i:02d}", _sample_report())

        page1 = db.list_reports(page=1, size=2)
        assert len(page1["servers"]) == 2
        assert page1["pagination"]["total"] == 5
        assert page1["pagination"]["total_pages"] == 3

        page3 = db.list_reports(page=3, size=2)
        assert len(page3["servers"]) == 1

    def test_list_reports_filter_region(self, db):
        db.insert_report("s1", _sample_report())
        r2 = _sample_report()
        r2["server_info"]["region"] = "tokyo"
        db.insert_report("s2", r2)

        result = db.list_reports(region="seoul")
        assert len(result["servers"]) == 1
        assert result["servers"][0]["region"] == "seoul"

    def test_dashboard_summary(self, db):
        db.insert_report("s1", _sample_report(score=90))
        r2 = _sample_report(score=70, role="control")
        r2["server_info"]["region"] = "tokyo"
        db.insert_report("s2", r2)

        summary = db.get_dashboard_summary()
        assert summary["overall"]["total_servers"] == 2
        assert summary["overall"]["average_compliance"] == 80.0
        assert len(summary["regions"]) == 2
        assert len(summary["roles"]) == 2

    def test_dashboard_summary_empty(self, db):
        summary = db.get_dashboard_summary()
        assert summary["overall"]["total_servers"] == 0

    def test_dashboard_region(self, db):
        db.insert_report("s1", _sample_report(score=90))
        db.insert_report("s2", _sample_report(score=80))

        data = db.get_dashboard_region("seoul")
        assert data is not None
        assert data["total_servers"] == 2
        assert data["average_compliance"] == 85.0

    def test_dashboard_region_not_found(self, db):
        assert db.get_dashboard_region("nonexistent") is None

    def test_compliance_summary(self, db):
        db.insert_report("s1", _sample_report(score=90))  # pass
        db.insert_report("s2", _sample_report(score=70))  # warn
        db.insert_report("s3", _sample_report(score=50))  # fail

        data = db.get_compliance_summary()
        assert data["total_servers"] == 3
        assert data["distribution"]["pass"] == 1
        assert data["distribution"]["warn"] == 1
        assert data["distribution"]["fail"] == 1

    def test_compliance_summary_empty(self, db):
        data = db.get_compliance_summary()
        assert data["total_servers"] == 0

    def test_cleanup_old_reports(self, db):
        db.insert_report("s1", _sample_report())
        # Manually backdate
        db.conn.execute(
            "UPDATE reports SET received_at = '2020-01-01T00:00:00Z'"
        )
        db.conn.commit()

        deleted = db.cleanup_old_reports(retention_days=30)
        assert deleted == 1
        assert db.get_report_by_host("s1") is None

    def test_get_stats(self, db):
        db.insert_report("s1", _sample_report())
        db.insert_report("s1", _sample_report())
        db.insert_report("s2", _sample_report())

        stats = db.get_stats()
        assert stats["total_reports"] == 3
        assert stats["unique_servers"] == 2
        assert stats["last_report_received"] is not None


# ── API Integration Tests ────────────────────────────────────────

@pytest.mark.anyio
class TestAPIHealth:
    async def test_health(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["data"]["service"] == "healthy"


@pytest.mark.anyio
class TestAPIReports:
    async def test_submit_report(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/v1/reports",
                json={"server_id": "s1", "report": _sample_report()},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["processing_status"] == "accepted"

    async def test_submit_report_validation(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/v1/reports", json={})
        assert resp.status_code == 400

    async def test_list_reports(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v1/reports",
                json={"server_id": "s1", "report": _sample_report()},
            )
            resp = await ac.get("/api/v1/reports")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["pagination"]["total"] == 1

    async def test_get_host_report(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v1/reports",
                json={"server_id": "host1", "report": _sample_report()},
            )
            resp = await ac.get("/api/v1/reports/host1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["current_report"]["compliance"]["overall_score"] == 85

    async def test_get_host_report_not_found(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/reports/nonexistent")
        assert resp.status_code == 404

    async def test_get_host_report_with_history(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            for _ in range(3):
                await ac.post(
                    "/api/v1/reports",
                    json={"server_id": "h1", "report": _sample_report()},
                )
            resp = await ac.get("/api/v1/reports/h1?include_history=true")
        assert resp.status_code == 200
        assert len(resp.json()["data"]["history"]) == 3


@pytest.mark.anyio
class TestAPIDashboard:
    async def test_dashboard_empty(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/dashboard")
        assert resp.status_code == 200
        assert resp.json()["data"]["overall"]["total_servers"] == 0

    async def test_dashboard_with_data(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v1/reports",
                json={"server_id": "s1", "report": _sample_report(score=90)},
            )
            resp = await ac.get("/api/v1/dashboard")
        assert resp.status_code == 200
        assert resp.json()["data"]["overall"]["total_servers"] == 1

    async def test_dashboard_region(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v1/reports",
                json={"server_id": "s1", "report": _sample_report()},
            )
            resp = await ac.get("/api/v1/dashboard/seoul")
        assert resp.status_code == 200
        assert resp.json()["data"]["region"] == "seoul"

    async def test_dashboard_region_not_found(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/dashboard/nowhere")
        assert resp.status_code == 404


@pytest.mark.anyio
class TestAPICompliance:
    async def test_compliance_empty(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/compliance")
        assert resp.status_code == 200
        assert resp.json()["data"]["total_servers"] == 0

    async def test_compliance_with_data(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post(
                "/api/v1/reports",
                json={"server_id": "s1", "report": _sample_report(score=90)},
            )
            await ac.post(
                "/api/v1/reports",
                json={"server_id": "s2", "report": _sample_report(score=50)},
            )
            resp = await ac.get("/api/v1/compliance")
        body = resp.json()
        assert body["data"]["total_servers"] == 2
        assert body["data"]["distribution"]["pass"] == 1
        assert body["data"]["distribution"]["fail"] == 1


# ── Middleware Tests ─────────────────────────────────────────────

@pytest.mark.anyio
class TestMiddleware:
    async def test_api_key_auth_required(self):
        settings = _settings(api_keys=["secret-key-123"])
        app = create_app(settings)
        app.state.db = Database(":memory:")
        app.state.db.connect()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # No key → 401
            resp = await ac.get("/api/v1/dashboard")
            assert resp.status_code == 401

            # Wrong key → 401
            resp = await ac.get(
                "/api/v1/dashboard",
                headers={"Authorization": "Bearer wrong"},
            )
            assert resp.status_code == 401

            # Correct key → 200
            resp = await ac.get(
                "/api/v1/dashboard",
                headers={"Authorization": "Bearer secret-key-123"},
            )
            assert resp.status_code == 200

        app.state.db.close()

    async def test_health_bypasses_auth(self):
        settings = _settings(api_keys=["secret"])
        app = create_app(settings)
        app.state.db = Database(":memory:")
        app.state.db.connect()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/health")
        assert resp.status_code == 200
        app.state.db.close()

    async def test_no_auth_when_no_keys_configured(self):
        """Dev mode: no keys = open access."""
        settings = _settings(api_keys=[])
        app = create_app(settings)
        app.state.db = Database(":memory:")
        app.state.db.connect()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/dashboard")
        assert resp.status_code == 200
        app.state.db.close()


# ── Response Format Tests ────────────────────────────────────────

@pytest.mark.anyio
class TestResponseFormat:
    async def test_success_format(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/health")
        body = resp.json()
        assert "status" in body
        assert "data" in body
        assert "meta" in body
        assert body["status"] == "success"
        assert "timestamp" in body["meta"]
        assert "version" in body["meta"]
        assert "request_id" in body["meta"]

    async def test_error_format(self, client):
        transport = ASGITransport(app=client)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/v1/reports/nonexistent")
        body = resp.json()
        assert body["status"] == "error"
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert "meta" in body
