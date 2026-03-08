"""Tests for RemediationGenerator."""

import pytest

from infra_auditor.remediation import RemediationGenerator


def _make_report(items=None, hostname="test-host", role="compute"):
    """Build a minimal report for remediation testing."""
    if items is None:
        items = {
            "memory": [
                {
                    "item": "vm.swappiness",
                    "category": "memory",
                    "description": "스왑 사용 적극성 설정",
                    "current_value": "60",
                    "recommended_value": "1",
                    "compliance": False,
                    "severity": "critical",
                    "score_impact": 25,
                    "remediation": {
                        "command": "sysctl -w vm.swappiness=1",
                        "persistent": "echo 'vm.swappiness = 1' >> /etc/sysctl.conf",
                        "requires_reboot": False,
                    },
                },
                {
                    "item": "vm.dirty_ratio",
                    "category": "memory",
                    "description": "더티 페이지 비율 상한",
                    "current_value": "15",
                    "recommended_value": "15",
                    "compliance": True,
                    "severity": "warning",
                    "score_impact": 8,
                    "remediation": {
                        "command": "sysctl -w vm.dirty_ratio=15",
                        "persistent": "",
                        "requires_reboot": False,
                    },
                },
            ],
            "cpu": [
                {
                    "item": "scaling_governor",
                    "category": "cpu",
                    "description": "CPU 주파수 조절 정책",
                    "current_value": "ondemand",
                    "recommended_value": "performance",
                    "compliance": False,
                    "severity": "warning",
                    "score_impact": 10,
                    "remediation": {
                        "command": "echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor",
                        "persistent": "",
                        "requires_reboot": False,
                    },
                },
                {
                    "item": "max_cstate",
                    "category": "cpu",
                    "description": "CPU C-state 최대 깊이",
                    "current_value": "9",
                    "recommended_value": "1",
                    "compliance": False,
                    "severity": "warning",
                    "score_impact": 8,
                    "remediation": {
                        "command": "",
                        "persistent": "GRUB_CMDLINE에 intel_idle.max_cstate=1 추가",
                        "requires_reboot": True,
                    },
                },
            ],
        }

    return {
        "server_info": {"hostname": hostname, "role": role},
        "scan_results": items,
        "compliance": {"overall_score": 50},
    }


class TestRemediationGenerator:
    """Test remediation script generation."""

    def test_generate_basic(self):
        gen = RemediationGenerator()
        result = gen.generate(_make_report())

        assert result["total_fixes"] == 3  # 3 non-compliant
        assert result["hostname"] == "test-host"
        assert result["role"] == "compute"
        assert result["reboot_required"] is True
        assert len(result["items"]) == 3
        assert result["script"]  # Non-empty script

    def test_generate_script_content(self):
        gen = RemediationGenerator()
        result = gen.generate(_make_report())
        script = result["script"]

        assert "#!/usr/bin/env bash" in script
        assert "DRY_RUN" in script
        assert "BACKUP_DIR" in script
        assert "apply_sysctl" in script
        assert "vm.swappiness" in script

    def test_generate_all_compliant(self):
        items = {
            "memory": [
                {
                    "item": "vm.swappiness",
                    "category": "memory",
                    "current_value": "1",
                    "recommended_value": "1",
                    "compliance": True,
                    "severity": "critical",
                    "remediation": {"command": "", "persistent": "", "requires_reboot": False},
                },
            ],
        }
        gen = RemediationGenerator()
        result = gen.generate(_make_report(items=items))

        assert result["total_fixes"] == 0
        assert result["script"] == ""
        assert result["items"] == []

    def test_filter_by_severity(self):
        gen = RemediationGenerator()
        result = gen.generate(
            _make_report(),
            severities=["critical"],
        )

        assert result["total_fixes"] == 1
        assert result["items"][0]["item"] == "vm.swappiness"

    def test_filter_by_category(self):
        gen = RemediationGenerator()
        result = gen.generate(
            _make_report(),
            categories=["cpu"],
        )

        assert result["total_fixes"] == 2
        items = {i["item"] for i in result["items"]}
        assert "scaling_governor" in items
        assert "max_cstate" in items

    def test_fix_type_classification(self):
        gen = RemediationGenerator()
        result = gen.generate(_make_report())

        fix_types = {i["item"]: i["fix_type"] for i in result["items"]}
        assert fix_types["vm.swappiness"] == "sysctl"
        assert fix_types["scaling_governor"] == "command"

    def test_generate_single_fix(self):
        item = {
            "remediation": {
                "command": "sysctl -w vm.swappiness=1",
            },
        }
        cmd = RemediationGenerator.generate_single_fix(item)
        assert cmd == "sysctl -w vm.swappiness=1"

    def test_generate_single_fix_no_command(self):
        item = {"remediation": {"command": ""}}
        cmd = RemediationGenerator.generate_single_fix(item)
        assert cmd is None

    def test_role_dict_handling(self):
        """Handle role as dict (from server_info)."""
        report = _make_report()
        report["server_info"]["role"] = {"detected": "control"}

        gen = RemediationGenerator()
        result = gen.generate(report)
        assert result["role"] == "control"

    def test_script_has_dry_run(self):
        gen = RemediationGenerator()
        result = gen.generate(_make_report())
        script = result["script"]

        assert "--dry-run" in script
        assert "DRY_RUN=false" in script

    def test_script_has_backup(self):
        gen = RemediationGenerator()
        result = gen.generate(_make_report())
        script = result["script"]

        assert "BACKUP_DIR" in script
        assert "backup_file" in script
