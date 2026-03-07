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
        # Should have high score
        assert compliance["overall_score"] >= 80

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
