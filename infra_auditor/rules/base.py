"""Base rule definition."""

from typing import Any, Callable, Dict, Optional


class Rule:
    """A single audit rule that checks a system value against a recommendation."""

    def __init__(
        self,
        category: str,
        subcategory: str,
        item: str,
        description: str,
        recommended_value: str,
        collection_method: str,
        severity: str = "warning",
        impact_description: str = "",
        justification: str = "",
        remediation_command: str = "",
        remediation_persistent: str = "",
        requires_reboot: bool = False,
        score_impact: int = 10,
        value_extractor: Optional[Callable[[Dict[str, Any]], str]] = None,
        comparator: Optional[Callable[[str, str], bool]] = None,
        roles: Optional[list] = None,
    ):
        self.category = category
        self.subcategory = subcategory
        self.item = item
        self.description = description
        self.recommended_value = recommended_value
        self.collection_method = collection_method
        self.severity = severity
        self.impact_description = impact_description
        self.justification = justification
        self.remediation_command = remediation_command
        self.remediation_persistent = remediation_persistent
        self.requires_reboot = requires_reboot
        self.score_impact = score_impact
        self.value_extractor = value_extractor
        self.comparator = comparator
        # Which roles this rule applies to. None = all roles (common rule).
        self.roles = roles

    def extract_value(self, collected_data: Dict[str, Any]) -> str:
        """Extract the current value from collected data."""
        if self.value_extractor:
            return self.value_extractor(collected_data)
        return "unknown"

    def check_compliance(self, current_value: str) -> bool:
        """Check if current value matches recommendation."""
        if self.comparator:
            return self.comparator(current_value, self.recommended_value)
        # Default: exact match (case-insensitive, whitespace-stripped)
        return current_value.strip().lower() == self.recommended_value.strip().lower()

    def evaluate(self, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate this rule against collected data."""
        current_value = self.extract_value(collected_data)
        compliant = self.check_compliance(current_value)

        return {
            "category": self.category,
            "subcategory": self.subcategory,
            "item": self.item,
            "description": self.description,
            "current_value": str(current_value),
            "recommended_value": self.recommended_value,
            "collection_method": self.collection_method,
            "severity": self.severity,
            "impact_description": self.impact_description,
            "justification": self.justification,
            "remediation": {
                "command": self.remediation_command,
                "persistent": self.remediation_persistent,
                "requires_reboot": self.requires_reboot,
            },
            "compliance": compliant,
            "score_impact": self.score_impact,
        }
