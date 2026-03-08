"""Drift detection: compare scan results across runs."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_HISTORY_DIR = os.path.expanduser("~/.infra-auditor/history")


class DriftDetector:
    """Compare current scan results against a previous baseline."""

    def __init__(self, history_dir: str = DEFAULT_HISTORY_DIR):
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _host_dir(self, hostname: str) -> Path:
        """Get per-host history directory."""
        safe = hostname.replace("/", "_").replace("..", "_")
        d = self.history_dir / safe
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_scan(self, report: Dict[str, Any]) -> str:
        """Save a scan report to history. Returns the saved file path."""
        hostname = report.get("server_info", {}).get("hostname", "unknown")
        scan_id = report.get("metadata", {}).get("scan_id", "unknown")
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        host_dir = self._host_dir(hostname)
        filename = f"{ts}_{scan_id[:8]}.json"
        path = host_dir / filename

        with open(path, "w") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # Maintain a symlink to latest
        latest = host_dir / "latest.json"
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(path.name)

        return str(path)

    def get_previous(self, hostname: str) -> Optional[Dict[str, Any]]:
        """Load the most recent saved scan for a host."""
        host_dir = self._host_dir(hostname)
        latest = host_dir / "latest.json"

        if not latest.exists():
            return None

        with open(latest) as f:
            return json.load(f)

    def get_history(
        self, hostname: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List saved scans for a host (newest first)."""
        host_dir = self._host_dir(hostname)
        files = sorted(host_dir.glob("2*.json"), reverse=True)[:limit]
        results = []
        for fp in files:
            try:
                with open(fp) as f:
                    data = json.load(f)
                results.append({
                    "file": str(fp),
                    "scan_id": data.get("metadata", {}).get("scan_id", ""),
                    "timestamp": data.get("metadata", {}).get("timestamp", ""),
                    "compliance_score": data.get("compliance", {}).get(
                        "overall_score", 0
                    ),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def compare(
        self,
        current: Dict[str, Any],
        previous: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare two scan reports and return drift analysis.

        Returns a dict with:
        - summary: overall drift stats
        - items: list of individual drift entries
        - score_change: compliance score delta
        """
        cur_results = self._flatten_scan_results(current)
        prev_results = self._flatten_scan_results(previous)

        cur_keys = set(cur_results.keys())
        prev_keys = set(prev_results.keys())

        added = cur_keys - prev_keys
        removed = prev_keys - cur_keys
        common = cur_keys & prev_keys

        items: List[Dict[str, Any]] = []

        for key in sorted(added):
            entry = cur_results[key]
            items.append({
                "item": key,
                "drift_type": "added",
                "category": entry.get("category", ""),
                "current_value": entry.get("current_value", ""),
                "previous_value": None,
                "current_compliance": entry.get("compliance", False),
                "previous_compliance": None,
                "severity": entry.get("severity", "info"),
            })

        for key in sorted(removed):
            entry = prev_results[key]
            items.append({
                "item": key,
                "drift_type": "removed",
                "category": entry.get("category", ""),
                "current_value": None,
                "previous_value": entry.get("current_value", ""),
                "current_compliance": None,
                "previous_compliance": entry.get("compliance", False),
                "severity": entry.get("severity", "info"),
            })

        changed_items = []
        for key in sorted(common):
            cur = cur_results[key]
            prev = prev_results[key]
            cur_val = cur.get("current_value", "")
            prev_val = prev.get("current_value", "")

            if cur_val != prev_val:
                cur_comp = cur.get("compliance", False)
                prev_comp = prev.get("compliance", False)

                if prev_comp and not cur_comp:
                    direction = "degraded"
                elif not prev_comp and cur_comp:
                    direction = "improved"
                else:
                    direction = "changed"

                entry = {
                    "item": key,
                    "drift_type": direction,
                    "category": cur.get("category", ""),
                    "current_value": cur_val,
                    "previous_value": prev_val,
                    "current_compliance": cur_comp,
                    "previous_compliance": prev_comp,
                    "severity": cur.get("severity", "info"),
                }
                items.append(entry)
                changed_items.append(entry)

        cur_score = current.get("compliance", {}).get("overall_score", 0)
        prev_score = previous.get("compliance", {}).get("overall_score", 0)

        summary = {
            "total_items_checked": len(cur_keys | prev_keys),
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed_items),
            "improved": sum(
                1 for i in changed_items if i["drift_type"] == "improved"
            ),
            "degraded": sum(
                1 for i in changed_items if i["drift_type"] == "degraded"
            ),
            "unchanged": len(common) - len(changed_items),
            "has_drift": bool(added or removed or changed_items),
        }

        return {
            "summary": summary,
            "score_change": {
                "current": cur_score,
                "previous": prev_score,
                "delta": cur_score - prev_score,
            },
            "items": items,
            "current_timestamp": current.get("metadata", {}).get(
                "timestamp", ""
            ),
            "previous_timestamp": previous.get("metadata", {}).get(
                "timestamp", ""
            ),
        }

    @staticmethod
    def _flatten_scan_results(
        report: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Flatten scan_results categories into a dict keyed by item name."""
        flat: Dict[str, Dict[str, Any]] = {}
        scan_results = report.get("scan_results", {})
        for category, items in scan_results.items():
            if isinstance(items, list):
                for item in items:
                    key = item.get("item", "")
                    if key:
                        flat[key] = item
        return flat
