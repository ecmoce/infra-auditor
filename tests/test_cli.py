"""Tests for CLI interface."""

import json
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from infra_auditor.cli import main


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_report_data():
    return {
        "metadata": {
            "version": "1.0.0",
            "agent_version": "0.1.0",
            "scan_id": "test-uuid-1234",
            "timestamp": "2026-03-07T12:00:00Z",
            "scan_duration_seconds": 1.5,
            "scan_type": "full",
        },
        "server_info": {
            "hostname": "test-host",
            "role": "compute",
            "os": {"distribution": {"name": "Ubuntu"}},
            "role_detection": {"method": "manual"},
        },
        "hardware_info": {},
        "scan_results": {},
        "compliance": {
            "overall_score": 75,
            "max_possible_score": 100,
            "category_scores": {
                "cpu": {"score": 80, "max_score": 100, "compliant_items": 2, "total_items": 3},
            },
            "severity_summary": {"critical": 1, "warning": 3, "info": 2},
            "recommendations": {
                "high_priority": [{"item": "vm.swappiness", "impact": 25, "effort": "low"}],
                "medium_priority": [],
                "low_priority": [],
            },
        },
        "errors": [],
    }


class TestCLI:
    def test_version(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "infra-auditor" in result.output

    def test_scan_help(self, runner):
        result = runner.invoke(main, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--role" in result.output
        assert "--output" in result.output
        assert "--format" in result.output

    @patch("infra_auditor.cli.Report")
    def test_scan_json_stdout(self, mock_report_cls, runner, mock_report_data):
        mock_report = MagicMock()
        mock_report.to_json.return_value = json.dumps(mock_report_data)
        mock_report_cls.return_value = mock_report

        result = runner.invoke(main, ["scan", "--role", "compute"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["server_info"]["role"] == "compute"

    @patch("infra_auditor.cli.Report")
    def test_scan_json_file(self, mock_report_cls, runner, mock_report_data, tmp_path):
        mock_report = MagicMock()
        mock_report.to_json.return_value = json.dumps(mock_report_data)
        mock_report_cls.return_value = mock_report

        outpath = str(tmp_path / "out.json")
        result = runner.invoke(main, ["scan", "--role", "control", "-o", outpath])
        assert result.exit_code == 0
        assert "리포트 저장" in result.output

    @patch("infra_auditor.cli.Report")
    def test_scan_summary(self, mock_report_cls, runner, mock_report_data):
        mock_report = MagicMock()
        mock_report.generate.return_value = mock_report_data
        mock_report_cls.return_value = mock_report

        result = runner.invoke(main, ["scan", "--role", "compute", "--format", "summary"])
        assert result.exit_code == 0
        assert "스캔 결과 요약" in result.output
        assert "75" in result.output  # overall score

    def test_scan_invalid_role(self, runner):
        result = runner.invoke(main, ["scan", "--role", "invalid"])
        assert result.exit_code != 0
