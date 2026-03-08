"""Tests for drift and remediation API endpoints."""

import json

import pytest
from httpx import AsyncClient, ASGITransport

from aggregator.app import create_app
from aggregator.config import Settings
from aggregator.database import Database


def _settings():
    return Settings(
        host="127.0.0.1",
        port=8443,
        debug=False,
        db_path=":memory:",
        api_keys=[],
        cors_origins=["*"],
        rate_limit_per_minute=1000,
        retention_days=30,
    )


def _sample_report(score=85, swappiness="60"):
    return {
        "metadata": {
            "version": "1.0.0",
            "agent_version": "0.1.0",
            "scan_id": "test-scan-001",
            "timestamp": "2024-03-07T07:48:00Z",
        },
        "server_info": {
            "hostname": "test-host",
            "role": {"detected": "compute"},
            "region": "seoul",
        },
        "scan_results": {
            "memory": [
                {
                    "item": "vm.swappiness",
                    "category": "memory",
                    "description": "스왑 사용 적극성 설정",
                    "current_value": swappiness,
                    "recommended_value": "1",
                    "compliance": swappiness == "1",
                    "severity": "critical",
                    "score_impact": 25,
                    "remediation": {
                        "command": "sysctl -w vm.swappiness=1",
                        "persistent": "echo 'vm.swappiness = 1' >> /etc/sysctl.conf",
                        "requires_reboot": False,
                    },
                },
            ],
        },
        "compliance": {
            "overall_score": score,
            "severity_summary": {"critical": 1, "warning": 0, "info": 0},
        },
    }


@pytest.fixture
def app():
    application = create_app(_settings())
    application.state.db = Database(":memory:")
    application.state.db.connect()
    yield application
    application.state.db.close()


@pytest.mark.anyio
class TestDriftAPI:
    """Test drift API endpoints."""

    async def test_compare_reports(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            prev = _sample_report(score=50, swappiness="60")
            cur = _sample_report(score=85, swappiness="1")

            resp = await client.post(
                "/api/v1/drift/compare",
                json={
                    "current_report": cur,
                    "previous_report": prev,
                },
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["summary"]["has_drift"] is True
            assert data["summary"]["improved"] == 1
            assert data["score_change"]["delta"] == 35

    async def test_compare_by_server_id(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Submit two reports
            await client.post(
                "/api/v1/reports",
                json={
                    "server_id": "web-01",
                    "report": _sample_report(score=50, swappiness="60"),
                },
            )
            await client.post(
                "/api/v1/reports",
                json={
                    "server_id": "web-01",
                    "report": _sample_report(score=85, swappiness="1"),
                },
            )

            resp = await client.post(
                "/api/v1/drift/compare",
                json={"server_id": "web-01"},
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["summary"]["has_drift"] is True

    async def test_compare_insufficient_data(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/v1/reports",
                json={
                    "server_id": "lonely-01",
                    "report": _sample_report(),
                },
            )

            resp = await client.post(
                "/api/v1/drift/compare",
                json={"server_id": "lonely-01"},
            )
            assert resp.status_code == 404

    async def test_get_drift(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/v1/reports",
                json={
                    "server_id": "web-02",
                    "report": _sample_report(score=50, swappiness="60"),
                },
            )
            await client.post(
                "/api/v1/reports",
                json={
                    "server_id": "web-02",
                    "report": _sample_report(score=85, swappiness="1"),
                },
            )

            resp = await client.get("/api/v1/drift/web-02")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["summary"]["has_drift"] is True

    async def test_get_drift_single_report(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/v1/reports",
                json={
                    "server_id": "single-01",
                    "report": _sample_report(),
                },
            )

            resp = await client.get("/api/v1/drift/single-01")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["has_drift"] is False

    async def test_get_drift_not_found(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/drift/nonexistent")
            assert resp.status_code == 404

    async def test_drift_history(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            for score in [50, 60, 70, 80]:
                await client.post(
                    "/api/v1/reports",
                    json={
                        "server_id": "trend-01",
                        "report": _sample_report(score=score),
                    },
                )

            resp = await client.get("/api/v1/drift/trend-01/history")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert len(data["history"]) == 4
            assert data["trend"] == "improving"


@pytest.mark.anyio
class TestRemediationAPI:
    """Test remediation API endpoints."""

    async def test_generate_from_report(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/remediation/generate",
                json={"report": _sample_report(swappiness="60")},
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["total_fixes"] == 1
            assert "script" in data
            assert "vm.swappiness" in data["script"]

    async def test_generate_from_server_id(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/v1/reports",
                json={
                    "server_id": "fix-01",
                    "report": _sample_report(swappiness="60"),
                },
            )

            resp = await client.post(
                "/api/v1/remediation/generate",
                json={"server_id": "fix-01"},
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["total_fixes"] == 1

    async def test_generate_with_filter(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Compliant report — no fixes needed
            resp = await client.post(
                "/api/v1/remediation/generate",
                json={
                    "report": _sample_report(swappiness="1"),
                    "severities": ["critical"],
                },
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["total_fixes"] == 0

    async def test_generate_no_data(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/remediation/generate",
                json={},
            )
            assert resp.status_code == 400

    async def test_get_remediation(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/v1/reports",
                json={
                    "server_id": "rem-01",
                    "report": _sample_report(swappiness="60"),
                },
            )

            resp = await client.get("/api/v1/remediation/rem-01")
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["total_non_compliant"] == 1
            assert data["items"][0]["item"] == "vm.swappiness"

    async def test_get_remediation_not_found(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/remediation/nonexistent")
            assert resp.status_code == 404

    async def test_get_remediation_severity_filter(self, app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/v1/reports",
                json={
                    "server_id": "sev-01",
                    "report": _sample_report(swappiness="60"),
                },
            )

            # Filter by warning — should find nothing (only critical)
            resp = await client.get(
                "/api/v1/remediation/sev-01?severity=warning"
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["total_non_compliant"] == 0
