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

    @patch("infra_auditor.cli.DriftDetector")
    @patch("infra_auditor.cli.Report")
    def test_scan_json_stdout(self, mock_report_cls, mock_drift_cls, runner, mock_report_data):
        mock_report = MagicMock()
        mock_report.generate.return_value = mock_report_data
        mock_report_cls.return_value = mock_report

        mock_detector = MagicMock()
        mock_detector.get_previous.return_value = None
        mock_drift_cls.return_value = mock_detector

        result = runner.invoke(main, ["scan", "--role", "compute"])
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["server_info"]["role"] == "compute"

    @patch("infra_auditor.cli.DriftDetector")
    @patch("infra_auditor.cli.Report")
    def test_scan_json_file(self, mock_report_cls, mock_drift_cls, runner, mock_report_data, tmp_path):
        mock_report = MagicMock()
        mock_report.generate.return_value = mock_report_data
        mock_report_cls.return_value = mock_report

        mock_detector = MagicMock()
        mock_detector.get_previous.return_value = None
        mock_drift_cls.return_value = mock_detector

        outpath = str(tmp_path / "out.json")
        result = runner.invoke(main, ["scan", "--role", "control", "-o", outpath])
        assert result.exit_code == 0
        assert "리포트 저장" in result.output

    @patch("infra_auditor.cli.DriftDetector")
    @patch("infra_auditor.cli.Report")
    def test_scan_summary(self, mock_report_cls, mock_drift_cls, runner, mock_report_data):
        mock_report = MagicMock()
        mock_report.generate.return_value = mock_report_data
        mock_report_cls.return_value = mock_report

        mock_detector = MagicMock()
        mock_detector.get_previous.return_value = None
        mock_drift_cls.return_value = mock_detector

        result = runner.invoke(main, ["scan", "--role", "compute", "--format", "summary"])
        assert result.exit_code == 0
        assert "스캔 결과 요약" in result.output
        assert "75" in result.output  # overall score

    def test_scan_invalid_role(self, runner):
        result = runner.invoke(main, ["scan", "--role", "invalid"])
        assert result.exit_code != 0

    @patch("infra_auditor.cli.DriftDetector")
    @patch("infra_auditor.cli.Report")
    def test_scan_no_save(self, mock_report_cls, mock_drift_cls, runner, mock_report_data):
        mock_report = MagicMock()
        mock_report.generate.return_value = mock_report_data
        mock_report_cls.return_value = mock_report

        result = runner.invoke(main, ["scan", "--role", "compute", "--no-save"])
        assert result.exit_code == 0
        # DriftDetector should not be instantiated when --no-save
        mock_drift_cls.assert_not_called()

    @patch("infra_auditor.cli.DriftDetector")
    @patch("infra_auditor.cli.Report")
    def test_scan_with_drift(self, mock_report_cls, mock_drift_cls, runner, mock_report_data):
        mock_report = MagicMock()
        mock_report.generate.return_value = mock_report_data
        mock_report_cls.return_value = mock_report

        # Simulate a previous scan exists
        prev_data = dict(mock_report_data)
        mock_detector = MagicMock()
        mock_detector.get_previous.return_value = prev_data
        mock_detector.compare.return_value = {
            "summary": {"has_drift": False, "changed": 0},
            "score_change": {"current": 75, "previous": 75, "delta": 0},
            "items": [],
        }
        mock_drift_cls.return_value = mock_detector

        result = runner.invoke(
            main, ["scan", "--role", "compute", "--format", "summary"]
        )
        assert result.exit_code == 0
        mock_detector.compare.assert_called_once()

    def test_drift_help(self, runner):
        result = runner.invoke(main, ["drift", "--help"])
        assert result.exit_code == 0
        assert "drift" in result.output.lower()

    def test_remediate_help(self, runner):
        result = runner.invoke(main, ["remediate", "--help"])
        assert result.exit_code == 0
        assert "--severity" in result.output

    @patch("infra_auditor.cli.RemediationGenerator")
    @patch("infra_auditor.cli.Report")
    def test_remediate_all_compliant(self, mock_report_cls, mock_gen_cls, runner, mock_report_data):
        mock_report = MagicMock()
        mock_report.generate.return_value = mock_report_data
        mock_report_cls.return_value = mock_report

        mock_gen = MagicMock()
        mock_gen.generate.return_value = {
            "script": "",
            "items": [],
            "total_fixes": 0,
            "reboot_required": False,
            "hostname": "test-host",
            "role": "compute",
        }
        mock_gen_cls.return_value = mock_gen

        result = runner.invoke(main, ["remediate", "--role", "compute"])
        assert result.exit_code == 0
        assert "모든 항목이 준수" in result.output

    @patch("infra_auditor.cli.RemediationGenerator")
    @patch("infra_auditor.cli.Report")
    def test_remediate_with_fixes(self, mock_report_cls, mock_gen_cls, runner, mock_report_data):
        mock_report = MagicMock()
        mock_report.generate.return_value = mock_report_data
        mock_report_cls.return_value = mock_report

        mock_gen = MagicMock()
        mock_gen.generate.return_value = {
            "script": "#!/bin/bash\necho test",
            "items": [
                {
                    "item": "vm.swappiness",
                    "category": "memory",
                    "severity": "critical",
                    "current_value": "60",
                    "recommended_value": "1",
                    "fix_type": "sysctl",
                },
            ],
            "total_fixes": 1,
            "reboot_required": False,
            "hostname": "test-host",
            "role": "compute",
        }
        mock_gen_cls.return_value = mock_gen

        result = runner.invoke(main, ["remediate", "--role", "compute"])
        assert result.exit_code == 0
        assert "1개 비준수 항목" in result.output
        assert "vm.swappiness" in result.output
