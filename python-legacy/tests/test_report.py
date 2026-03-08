"""Tests for report generation."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from infra_auditor.report import Report


class TestReport:
    @patch("infra_auditor.report.CPUCollector")
    @patch("infra_auditor.report.MemoryCollector")
    @patch("infra_auditor.report.NetworkCollector")
    @patch("infra_auditor.report.StorageCollector")
    @patch("infra_auditor.report.KernelCollector")
    @patch("infra_auditor.report.ServiceCollector")
    @patch("infra_auditor.report.detect_role")
    def test_generate_full_report(
        self,
        mock_detect,
        mock_svc,
        mock_kernel,
        mock_storage,
        mock_net,
        mock_mem,
        mock_cpu,
        mock_collected_data,
    ):
        """Test full report generation with mocked collectors."""
        # Setup mocks
        mock_cpu.return_value.collect.return_value = mock_collected_data["cpu"]
        mock_cpu.return_value.errors = []
        mock_mem.return_value.collect.return_value = mock_collected_data["memory"]
        mock_mem.return_value.errors = []
        mock_net.return_value.collect.return_value = mock_collected_data["network"]
        mock_net.return_value.errors = []
        mock_storage.return_value.collect.return_value = mock_collected_data["storage"]
        mock_storage.return_value.errors = []
        mock_kernel.return_value.collect.return_value = mock_collected_data["kernel"]
        mock_kernel.return_value.errors = []
        mock_svc.return_value.collect.return_value = mock_collected_data["service"]
        mock_svc.return_value.errors = []
        mock_detect.return_value = {
            "role": "compute",
            "confidence": 0.95,
            "method": "auto",
        }

        report = Report()
        data = report.generate()

        # Verify schema structure
        assert "metadata" in data
        assert "server_info" in data
        assert "hardware_info" in data
        assert "scan_results" in data
        assert "compliance" in data
        assert "errors" in data

        # Metadata
        meta = data["metadata"]
        assert meta["version"] == "1.0.0"
        assert "scan_id" in meta
        assert "timestamp" in meta
        assert meta["scan_type"] == "full"

        # Server info
        assert data["server_info"]["role"] == "compute"

        # Compliance
        compliance = data["compliance"]
        assert 0 <= compliance["overall_score"] <= 100

    @patch("infra_auditor.report.CPUCollector")
    @patch("infra_auditor.report.MemoryCollector")
    @patch("infra_auditor.report.NetworkCollector")
    @patch("infra_auditor.report.StorageCollector")
    @patch("infra_auditor.report.KernelCollector")
    @patch("infra_auditor.report.ServiceCollector")
    def test_manual_role(
        self,
        mock_svc,
        mock_kernel,
        mock_storage,
        mock_net,
        mock_mem,
        mock_cpu,
        mock_collected_data,
    ):
        """Test report with manual role specification."""
        for cls in [mock_cpu, mock_mem, mock_net, mock_storage, mock_kernel, mock_svc]:
            cls.return_value.collect.return_value = {}
            cls.return_value.errors = []

        report = Report(role="control")
        data = report.generate()
        assert data["server_info"]["role"] == "control"
        assert data["server_info"]["role_detection"]["method"] == "manual"

    @patch("infra_auditor.report.CPUCollector")
    @patch("infra_auditor.report.MemoryCollector")
    @patch("infra_auditor.report.NetworkCollector")
    @patch("infra_auditor.report.StorageCollector")
    @patch("infra_auditor.report.KernelCollector")
    @patch("infra_auditor.report.ServiceCollector")
    def test_to_json(
        self,
        mock_svc,
        mock_kernel,
        mock_storage,
        mock_net,
        mock_mem,
        mock_cpu,
    ):
        """Test JSON output is valid."""
        for cls in [mock_cpu, mock_mem, mock_net, mock_storage, mock_kernel, mock_svc]:
            cls.return_value.collect.return_value = {}
            cls.return_value.errors = []

        report = Report(role="control")
        json_str = report.to_json()
        data = json.loads(json_str)
        assert isinstance(data, dict)

    @patch("infra_auditor.report.CPUCollector")
    @patch("infra_auditor.report.MemoryCollector")
    @patch("infra_auditor.report.NetworkCollector")
    @patch("infra_auditor.report.StorageCollector")
    @patch("infra_auditor.report.KernelCollector")
    @patch("infra_auditor.report.ServiceCollector")
    def test_save_to_file(
        self,
        mock_svc,
        mock_kernel,
        mock_storage,
        mock_net,
        mock_mem,
        mock_cpu,
        tmp_path,
    ):
        """Test saving report to file."""
        for cls in [mock_cpu, mock_mem, mock_net, mock_storage, mock_kernel, mock_svc]:
            cls.return_value.collect.return_value = {}
            cls.return_value.errors = []

        report = Report(role="network")
        out_path = str(tmp_path / "report.json")
        report.save(out_path)
        assert os.path.exists(out_path)
        with open(out_path) as f:
            data = json.load(f)
        assert data["server_info"]["role"] == "network"

    @patch("infra_auditor.report.CPUCollector")
    @patch("infra_auditor.report.MemoryCollector")
    @patch("infra_auditor.report.NetworkCollector")
    @patch("infra_auditor.report.StorageCollector")
    @patch("infra_auditor.report.KernelCollector")
    @patch("infra_auditor.report.ServiceCollector")
    def test_collector_failure_handled(
        self,
        mock_svc,
        mock_kernel,
        mock_storage,
        mock_net,
        mock_mem,
        mock_cpu,
    ):
        """Test that a failing collector doesn't crash the report."""
        mock_cpu.return_value.collect.side_effect = RuntimeError("boom")
        mock_cpu.return_value.errors = []
        for cls in [mock_mem, mock_net, mock_storage, mock_kernel, mock_svc]:
            cls.return_value.collect.return_value = {}
            cls.return_value.errors = []

        report = Report(role="control")
        data = report.generate()
        # Should still produce a report
        assert "errors" in data
        assert any("boom" in e.get("message", "") for e in data["errors"])
