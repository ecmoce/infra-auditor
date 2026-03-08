"""Tests for rules engine."""

import pytest

from infra_auditor.rules.base import Rule
from infra_auditor.rules.common import COMMON_RULES, _gte_comparator, _lte_comparator
from infra_auditor.rules.engine import RulesEngine
from infra_auditor.rules.role_rules import ROLE_RULES


class TestComparators:
    def test_gte_pass(self):
        assert _gte_comparator("65535", "65535") is True
        assert _gte_comparator("100000", "65535") is True

    def test_gte_fail(self):
        assert _gte_comparator("128", "65535") is False

    def test_gte_invalid(self):
        assert _gte_comparator("unknown", "65535") is False

    def test_lte_pass(self):
        assert _lte_comparator("1", "1") is True
        assert _lte_comparator("0", "1") is True

    def test_lte_fail(self):
        assert _lte_comparator("60", "1") is False


class TestRule:
    def test_basic_rule_evaluate(self):
        rule = Rule(
            category="test",
            subcategory="sub",
            item="test_item",
            description="A test rule",
            recommended_value="42",
            collection_method="echo 42",
            value_extractor=lambda d: d.get("value", ""),
        )
        result = rule.evaluate({"value": "42"})
        assert result["compliance"] is True
        assert result["current_value"] == "42"

    def test_rule_non_compliant(self):
        rule = Rule(
            category="test",
            subcategory="sub",
            item="test_item",
            description="A test rule",
            recommended_value="42",
            collection_method="echo 42",
            value_extractor=lambda d: d.get("value", ""),
        )
        result = rule.evaluate({"value": "99"})
        assert result["compliance"] is False

    def test_rule_custom_comparator(self):
        rule = Rule(
            category="test",
            subcategory="sub",
            item="test_item",
            description="A test rule",
            recommended_value="100",
            collection_method="echo",
            value_extractor=lambda d: d.get("value", ""),
            comparator=_gte_comparator,
        )
        assert rule.evaluate({"value": "200"})["compliance"] is True
        assert rule.evaluate({"value": "50"})["compliance"] is False

    def test_rule_case_insensitive(self):
        rule = Rule(
            category="test",
            subcategory="sub",
            item="test_item",
            description="test",
            recommended_value="Performance",
            collection_method="echo",
            value_extractor=lambda d: "performance",
        )
        assert rule.evaluate({})["compliance"] is True


class TestRulesEngine:
    def test_common_rules_loaded(self):
        engine = RulesEngine("unknown")
        assert len(engine.rules) == len(COMMON_RULES)

    def test_role_rules_loaded(self):
        engine = RulesEngine("control")
        # Should have common + control-specific (minus overridden)
        assert len(engine.rules) > 0

    def test_evaluate_non_compliant_system(self, mock_collected_data):
        engine = RulesEngine("compute")
        result = engine.evaluate(mock_collected_data)

        assert "scan_results" in result
        assert "compliance" in result

        compliance = result["compliance"]
        assert "overall_score" in compliance
        assert 0 <= compliance["overall_score"] <= 100
        assert compliance["severity_summary"]["critical"] > 0

    def test_evaluate_compliant_system(self, mock_compliant_data):
        engine = RulesEngine("control")
        result = engine.evaluate(mock_compliant_data)

        compliance = result["compliance"]
        # Should have reasonable score (adjusted for 62 total rules)
        assert compliance["overall_score"] >= 60

    def test_category_scores_present(self, mock_collected_data):
        engine = RulesEngine("control")
        result = engine.evaluate(mock_collected_data)
        cat_scores = result["compliance"]["category_scores"]
        assert len(cat_scores) > 0
        for cat, stats in cat_scores.items():
            assert "score" in stats
            assert "compliant_items" in stats
            assert "total_items" in stats
            assert stats["compliant_items"] <= stats["total_items"]

    def test_recommendations_sorted_by_severity(self, mock_collected_data):
        engine = RulesEngine("control")
        result = engine.evaluate(mock_collected_data)
        recs = result["compliance"]["recommendations"]
        assert "high_priority" in recs
        assert "medium_priority" in recs
        assert "low_priority" in recs

    def test_all_roles_have_valid_rules(self):
        """All defined roles should load without error."""
        for role in ["control", "compute", "network", "storage-ceph", "storage-s3"]:
            engine = RulesEngine(role)
            assert len(engine.rules) > 0

    def test_role_override_common_rule(self):
        """Role rules for same item should override common rules."""
        # storage-ceph has its own vm.dirty_ratio (recommended=5 vs common=15)
        engine = RulesEngine("storage-ceph")
        dirty_rules = [r for r in engine.rules if r.item == "vm.dirty_ratio"]
        assert len(dirty_rules) == 1
        assert dirty_rules[0].recommended_value == "5"

    def test_storage_s3_swappiness_override(self):
        """storage-s3 has its own swappiness rule (10 vs common 1)."""
        engine = RulesEngine("storage-s3")
        swap_rules = [r for r in engine.rules if r.item == "vm.swappiness"]
        assert len(swap_rules) == 1
        assert swap_rules[0].recommended_value == "10"


class TestAdvancedNetworkRules:
    """Test advanced network tuning rules."""

    def test_rps_sock_flow_entries_rule(self):
        """Test RPS/RFS global flow table rule."""
        engine = RulesEngine("network")
        rps_rules = [r for r in engine.rules if r.item == "rps_sock_flow_entries"]
        assert len(rps_rules) == 1
        rule = rps_rules[0]
        assert rule.recommended_value == "32768"
        assert rule.severity == "info"

    def test_nf_conntrack_max_rule(self):
        """Test connection tracking limits rule."""
        engine = RulesEngine("network")
        conntrack_rules = [r for r in engine.rules if r.item == "nf_conntrack_max"]
        assert len(conntrack_rules) == 1
        rule = conntrack_rules[0]
        assert rule.recommended_value == "1048576"
        assert rule.severity == "warning"

    def test_irq_affinity_network_rule(self):
        """Test network IRQ affinity rule for ELB role."""
        engine = RulesEngine("network")
        irq_rules = [r for r in engine.rules if r.item == "irq_affinity"]
        assert len(irq_rules) == 1
        rule = irq_rules[0]
        assert rule.recommended_value == "configured"


class TestKVMVirtualizationRules:
    """Test KVM/QEMU virtualization rules."""

    def test_kvm_nested_rule(self):
        """Test KVM nested virtualization rule."""
        engine = RulesEngine("compute")
        nested_rules = [r for r in engine.rules if r.item == "kvm_nested"]
        assert len(nested_rules) == 1
        rule = nested_rules[0]
        assert rule.recommended_value == "Y"
        assert rule.category == "virtualization"

    def test_compute_hugepages_rule(self):
        """Test compute hugepages rule."""
        engine = RulesEngine("compute")
        hp_rules = [r for r in engine.rules if r.item == "hugepages_2mb"]
        assert len(hp_rules) == 1
        rule = hp_rules[0]
        assert rule.recommended_value == "1024"
        assert rule.severity == "warning"

    def test_memory_overcommit_compute(self):
        """Test memory overcommit rule for VM hosts."""
        engine = RulesEngine("compute")
        overcommit_rules = [r for r in engine.rules if r.item == "memory_overcommit"]
        assert len(overcommit_rules) == 1
        rule = overcommit_rules[0]
        assert rule.recommended_value == "1"


class TestCephStorageRules:
    """Test Ceph storage optimization rules."""

    def test_osd_memory_target_rule(self):
        """Test Ceph OSD memory target rule."""
        engine = RulesEngine("storage-ceph")
        memory_rules = [r for r in engine.rules if r.item == "osd_memory_target"]
        assert len(memory_rules) == 1
        rule = memory_rules[0]
        assert rule.recommended_value == "8589934592"  # 8GB
        assert rule.severity == "critical"

    def test_io_scheduler_nvme_rule(self):
        """Test NVMe I/O scheduler rule for Ceph."""
        engine = RulesEngine("storage-ceph")
        sched_rules = [r for r in engine.rules if r.item == "io_scheduler_nvme"]
        assert len(sched_rules) == 1
        rule = sched_rules[0]
        assert rule.recommended_value == "none"

    def test_xfs_noatime_rule(self):
        """Test XFS noatime mount option rule."""
        engine = RulesEngine("storage-ceph")
        xfs_rules = [r for r in engine.rules if r.item == "xfs_noatime"]
        assert len(xfs_rules) == 1
        rule = xfs_rules[0]
        assert rule.recommended_value == "noatime"


class TestAdvancedKernelRules:
    """Test advanced kernel tuning rules."""

    def test_sched_migration_cost_rule(self):
        """Test scheduler migration cost rule."""
        # Should be present in all roles via common rules
        engine = RulesEngine("control")
        sched_rules = [r for r in engine.rules if r.item == "sched_migration_cost_ns"]
        assert len(sched_rules) == 1
        rule = sched_rules[0]
        assert rule.recommended_value == "5000000"

    def test_panic_on_oops_rule(self):
        """Test kernel panic on OOPS rule."""
        engine = RulesEngine("compute")
        panic_rules = [r for r in engine.rules if r.item == "panic_on_oops"]
        assert len(panic_rules) == 1
        rule = panic_rules[0]
        assert rule.recommended_value == "1"
        assert rule.severity == "warning"

    def test_aio_max_nr_rule(self):
        """Test AIO maximum requests rule."""
        engine = RulesEngine("storage-ceph")
        aio_rules = [r for r in engine.rules if r.item == "fs_aio_max_nr"]
        assert len(aio_rules) == 1
        rule = aio_rules[0]
        assert rule.recommended_value == "1048576"


class TestMemoryTuningRules:
    """Test advanced memory management rules."""

    def test_min_free_kbytes_rule(self):
        """Test min_free_kbytes rule for large memory systems."""
        engine = RulesEngine("compute")
        mem_rules = [r for r in engine.rules if r.item == "min_free_kbytes"]
        assert len(mem_rules) == 1
        rule = mem_rules[0]
        assert rule.recommended_value == "1048576"  # 1GB
        assert rule.severity == "info"

    def test_zone_reclaim_rule(self):
        """Test NUMA zone reclaim rule."""
        engine = RulesEngine("network")
        zone_rules = [r for r in engine.rules if r.item == "zone_reclaim_mode"]
        assert len(zone_rules) == 1
        rule = zone_rules[0]
        assert rule.recommended_value == "0"

    def test_transparent_hugepage_rule(self):
        """Test THP rule in common rules."""
        engine = RulesEngine("network")
        thp_rules = [r for r in engine.rules if r.item == "transparent_hugepage"]
        assert len(thp_rules) == 1
        rule = thp_rules[0]
        assert rule.recommended_value == "madvise"


class TestRuleCount:
    """Test that we have the expected number of rules."""

    def test_total_rule_count(self):
        """Verify we have 62 total rules."""
        total_common = len(COMMON_RULES)
        total_role = sum(len(rules) for rules in ROLE_RULES.values())
        total = total_common + total_role
        assert total == 62, f"Expected 62 total rules, got {total}"

    def test_common_rule_count(self):
        """Verify we have 24 common rules."""
        assert len(COMMON_RULES) == 24

    def test_role_rule_counts(self):
        """Verify role-specific rule counts."""
        assert len(ROLE_RULES["control"]) >= 5  # At least 5 control rules
        assert len(ROLE_RULES["compute"]) >= 6  # At least 6 compute rules  
        assert len(ROLE_RULES["network"]) >= 7  # At least 7 network rules
        assert len(ROLE_RULES["storage-ceph"]) >= 8  # At least 8 ceph rules
        assert len(ROLE_RULES["storage-s3"]) >= 6  # At least 6 S3 rules
