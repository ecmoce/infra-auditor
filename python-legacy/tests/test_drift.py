"""Tests for DriftDetector."""

import json
import os
import tempfile

import pytest

from infra_auditor.drift import DriftDetector


def _make_report(
    hostname="test-host",
    scan_id="scan-001",
    timestamp="2024-03-07T12:00:00Z",
    overall_score=75,
    items=None,
):
    """Build a minimal report for drift testing."""
    if items is None:
        items = {
            "cpu": [
                {
                    "item": "scaling_governor",
                    "category": "cpu",
                    "current_value": "ondemand",
                    "recommended_value": "performance",
                    "compliance": False,
                    "severity": "warning",
                    "score_impact": 10,
                },
            ],
            "memory": [
                {
                    "item": "vm.swappiness",
                    "category": "memory",
                    "current_value": "60",
                    "recommended_value": "1",
                    "compliance": False,
                    "severity": "critical",
                    "score_impact": 25,
                },
                {
                    "item": "vm.dirty_ratio",
                    "category": "memory",
                    "current_value": "15",
                    "recommended_value": "15",
                    "compliance": True,
                    "severity": "warning",
                    "score_impact": 8,
                },
            ],
        }
    return {
        "metadata": {
            "scan_id": scan_id,
            "timestamp": timestamp,
        },
        "server_info": {
            "hostname": hostname,
        },
        "scan_results": items,
        "compliance": {
            "overall_score": overall_score,
        },
    }


@pytest.fixture
def detector(tmp_path):
    """Create a DriftDetector with temporary history dir."""
    return DriftDetector(history_dir=str(tmp_path / "history"))


class TestDriftDetector:
    """Test DriftDetector save/load/compare functionality."""

    def test_save_and_load(self, detector):
        report = _make_report()
        path = detector.save_scan(report)

        assert os.path.exists(path)

        loaded = detector.get_previous("test-host")
        assert loaded is not None
        assert loaded["metadata"]["scan_id"] == "scan-001"

    def test_no_previous(self, detector):
        assert detector.get_previous("nonexistent") is None

    def test_history(self, detector):
        r1 = _make_report(scan_id="s1", timestamp="2024-03-07T10:00:00Z")
        r2 = _make_report(scan_id="s2", timestamp="2024-03-07T11:00:00Z")

        detector.save_scan(r1)
        detector.save_scan(r2)

        history = detector.get_history("test-host")
        assert len(history) == 2
        # Most recent first
        assert history[0]["scan_id"] == "s2"

    def test_compare_no_drift(self, detector):
        report = _make_report()
        drift = detector.compare(report, report)

        assert drift["summary"]["has_drift"] is False
        assert drift["summary"]["changed"] == 0
        assert drift["score_change"]["delta"] == 0

    def test_compare_value_changed(self, detector):
        prev_items = {
            "memory": [
                {
                    "item": "vm.swappiness",
                    "category": "memory",
                    "current_value": "60",
                    "recommended_value": "1",
                    "compliance": False,
                    "severity": "critical",
                    "score_impact": 25,
                },
            ],
        }
        cur_items = {
            "memory": [
                {
                    "item": "vm.swappiness",
                    "category": "memory",
                    "current_value": "1",
                    "recommended_value": "1",
                    "compliance": True,
                    "severity": "critical",
                    "score_impact": 25,
                },
            ],
        }
        prev = _make_report(items=prev_items, overall_score=50)
        cur = _make_report(items=cur_items, overall_score=75)

        drift = detector.compare(cur, prev)

        assert drift["summary"]["has_drift"] is True
        assert drift["summary"]["changed"] == 1
        assert drift["summary"]["improved"] == 1
        assert drift["score_change"]["delta"] == 25

        item = drift["items"][0]
        assert item["item"] == "vm.swappiness"
        assert item["drift_type"] == "improved"
        assert item["previous_value"] == "60"
        assert item["current_value"] == "1"

    def test_compare_degraded(self, detector):
        prev_items = {
            "cpu": [
                {
                    "item": "scaling_governor",
                    "category": "cpu",
                    "current_value": "performance",
                    "recommended_value": "performance",
                    "compliance": True,
                    "severity": "warning",
                    "score_impact": 10,
                },
            ],
        }
        cur_items = {
            "cpu": [
                {
                    "item": "scaling_governor",
                    "category": "cpu",
                    "current_value": "powersave",
                    "recommended_value": "performance",
                    "compliance": False,
                    "severity": "warning",
                    "score_impact": 10,
                },
            ],
        }
        prev = _make_report(items=prev_items, overall_score=90)
        cur = _make_report(items=cur_items, overall_score=80)

        drift = detector.compare(cur, prev)

        assert drift["summary"]["degraded"] == 1
        assert drift["items"][0]["drift_type"] == "degraded"
        assert drift["score_change"]["delta"] == -10

    def test_compare_added_removed(self, detector):
        prev_items = {
            "cpu": [
                {
                    "item": "scaling_governor",
                    "category": "cpu",
                    "current_value": "performance",
                    "recommended_value": "performance",
                    "compliance": True,
                    "severity": "warning",
                    "score_impact": 10,
                },
            ],
        }
        cur_items = {
            "memory": [
                {
                    "item": "vm.swappiness",
                    "category": "memory",
                    "current_value": "1",
                    "recommended_value": "1",
                    "compliance": True,
                    "severity": "critical",
                    "score_impact": 25,
                },
            ],
        }
        prev = _make_report(items=prev_items)
        cur = _make_report(items=cur_items)

        drift = detector.compare(cur, prev)

        assert drift["summary"]["added"] == 1
        assert drift["summary"]["removed"] == 1

        types = {i["drift_type"] for i in drift["items"]}
        assert "added" in types
        assert "removed" in types

    def test_save_creates_latest_symlink(self, detector):
        report = _make_report()
        detector.save_scan(report)

        host_dir = detector._host_dir("test-host")
        latest = host_dir / "latest.json"
        assert latest.is_symlink()

        with open(latest) as f:
            data = json.load(f)
        assert data["metadata"]["scan_id"] == "scan-001"

    def test_multiple_saves_update_latest(self, detector):
        r1 = _make_report(scan_id="s1")
        r2 = _make_report(scan_id="s2")

        detector.save_scan(r1)
        detector.save_scan(r2)

        loaded = detector.get_previous("test-host")
        assert loaded["metadata"]["scan_id"] == "s2"

    def test_history_limit(self, detector):
        for i in range(15):
            r = _make_report(scan_id=f"s{i:03d}")
            detector.save_scan(r)

        history = detector.get_history("test-host", limit=5)
        assert len(history) == 5
