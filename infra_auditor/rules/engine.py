"""Rules engine: loads and evaluates rules against collected data."""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from infra_auditor.rules.base import Rule
from infra_auditor.rules.common import COMMON_RULES
from infra_auditor.rules.role_rules import ROLE_RULES

logger = logging.getLogger(__name__)


class RulesEngine:
    """Loads common + role-specific rules and evaluates them."""

    def __init__(self, role: str):
        self.role = role
        self.rules: List[Rule] = []
        self._load_rules()

    def _load_rules(self) -> None:
        """Load common rules plus role-specific rules."""
        self.rules = list(COMMON_RULES)
        role_specific = ROLE_RULES.get(self.role, [])
        # For role-specific rules, check for overlap with common rules
        # Role rules override common rules for same item
        role_items = {r.item for r in role_specific}
        self.rules = [r for r in self.rules if r.item not in role_items]
        self.rules.extend(role_specific)
        logger.info(
            "Loaded %d rules for role '%s' (%d common, %d role-specific)",
            len(self.rules),
            self.role,
            len(COMMON_RULES),
            len(role_specific),
        )

    def evaluate(self, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate all rules against collected data.

        Returns scan_results grouped by category, plus compliance summary.
        """
        scan_results: Dict[str, List[Dict]] = defaultdict(list)
        total_score = 0
        max_score = 0
        severity_summary = {"critical": 0, "warning": 0, "info": 0}
        category_stats: Dict[str, Dict] = {}

        for rule in self.rules:
            result = rule.evaluate(collected_data)
            category = result["category"]
            scan_results[category].append(result)

            max_score += result["score_impact"]
            if result["compliance"]:
                total_score += result["score_impact"]
            else:
                severity_summary[result["severity"]] += 1

            # Track per-category stats
            if category not in category_stats:
                category_stats[category] = {
                    "score": 0,
                    "max_score": 0,
                    "compliant_items": 0,
                    "total_items": 0,
                }
            stats = category_stats[category]
            stats["max_score"] += result["score_impact"]
            stats["total_items"] += 1
            if result["compliance"]:
                stats["score"] += result["score_impact"]
                stats["compliant_items"] += 1

        # Calculate overall percentage
        overall_score = round(
            (total_score / max_score * 100) if max_score > 0 else 0
        )

        # Calculate category percentages
        category_scores = {}
        for cat, stats in category_stats.items():
            cat_pct = round(
                (stats["score"] / stats["max_score"] * 100)
                if stats["max_score"] > 0
                else 0
            )
            category_scores[cat] = {
                "score": cat_pct,
                "max_score": 100,
                "compliant_items": stats["compliant_items"],
                "total_items": stats["total_items"],
            }

        # Build prioritized recommendations
        non_compliant = []
        for cat_results in scan_results.values():
            for r in cat_results:
                if not r["compliance"]:
                    non_compliant.append(r)

        non_compliant.sort(key=lambda x: x["score_impact"], reverse=True)

        high = [
            {"item": r["item"], "impact": r["score_impact"], "effort": "low"}
            for r in non_compliant
            if r["severity"] == "critical"
        ]
        medium = [
            {"item": r["item"], "impact": r["score_impact"], "effort": "low"}
            for r in non_compliant
            if r["severity"] == "warning"
        ]
        low = [
            {"item": r["item"], "impact": r["score_impact"], "effort": "low"}
            for r in non_compliant
            if r["severity"] == "info"
        ]

        compliance = {
            "overall_score": overall_score,
            "max_possible_score": 100,
            "category_scores": category_scores,
            "severity_summary": severity_summary,
            "recommendations": {
                "high_priority": high,
                "medium_priority": medium,
                "low_priority": low,
            },
        }

        return {
            "scan_results": dict(scan_results),
            "compliance": compliance,
        }
