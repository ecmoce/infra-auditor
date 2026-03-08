"""Remediation script generation for non-compliant items."""

import textwrap
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class RemediationGenerator:
    """Generate shell scripts to fix non-compliant audit findings."""

    SCRIPT_HEADER = textwrap.dedent("""\
        #!/usr/bin/env bash
        # ============================================================
        # infra-auditor Remediation Script
        # Generated: {timestamp}
        # Host: {hostname}
        # Role: {role}
        # ============================================================
        # WARNING: Review this script before execution!
        # Run with --dry-run first: bash {script_name} --dry-run
        # ============================================================

        set -euo pipefail

        DRY_RUN=false
        if [[ "${{1:-}}" == "--dry-run" ]]; then
            DRY_RUN=true
            echo "[DRY-RUN] No changes will be made."
        fi

        BACKUP_DIR="/var/backups/infra-auditor/$(date +%Y%m%d_%H%M%S)"
        CHANGES_LOG="$BACKUP_DIR/changes.log"

        log() {{
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$CHANGES_LOG"
        }}

        backup_file() {{
            local src="$1"
            if [[ -f "$src" ]]; then
                local dest="$BACKUP_DIR/$(echo "$src" | tr '/' '_')"
                cp -a "$src" "$dest"
                log "BACKUP: $src -> $dest"
            fi
        }}

        apply_sysctl() {{
            local key="$1"
            local value="$2"
            local current
            current=$(sysctl -n "$key" 2>/dev/null || echo "UNKNOWN")
            if [[ "$current" == "$value" ]]; then
                log "SKIP: $key already set to $value"
                return
            fi
            if $DRY_RUN; then
                log "DRY-RUN: sysctl -w $key=$value (current: $current)"
            else
                sysctl -w "$key=$value"
                log "APPLIED: $key = $value (was: $current)"
            fi
        }}

        persist_sysctl() {{
            local key="$1"
            local value="$2"
            local conf_file="/etc/sysctl.d/99-infra-auditor.conf"
            if $DRY_RUN; then
                log "DRY-RUN: Would persist $key = $value in $conf_file"
                return
            fi
            backup_file "$conf_file"
            # Remove existing entry for this key, then append
            if [[ -f "$conf_file" ]]; then
                sed -i "/^$key\\s*=/d" "$conf_file"
            fi
            echo "$key = $value" >> "$conf_file"
            log "PERSISTED: $key = $value in $conf_file"
        }}

        # ── Setup ─────────────────────────────────────────
        if ! $DRY_RUN; then
            mkdir -p "$BACKUP_DIR"
            log "Remediation started"
            backup_file "/etc/sysctl.conf"
            [[ -d /etc/sysctl.d ]] && backup_file "/etc/sysctl.d/99-infra-auditor.conf"
        else
            CHANGES_LOG="/dev/null"
            log "Dry-run remediation started"
        fi

        echo ""
    """)

    SCRIPT_FOOTER = textwrap.dedent("""\

        # ── Verification ──────────────────────────────────
        echo ""
        echo "============================================================"
        if $DRY_RUN; then
            echo "DRY-RUN complete. No changes were made."
            echo "Run without --dry-run to apply changes."
        else
            log "Remediation complete. Backup: $BACKUP_DIR"
            echo "Backup directory: $BACKUP_DIR"
            echo "Changes log: $CHANGES_LOG"

            # Reload sysctl
            if [[ -f /etc/sysctl.d/99-infra-auditor.conf ]]; then
                sysctl -p /etc/sysctl.d/99-infra-auditor.conf 2>/dev/null || true
                log "Reloaded sysctl configuration"
            fi
        fi
        echo "============================================================"
    """)

    def __init__(self):
        self.sysctl_items: List[Dict[str, Any]] = []
        self.other_items: List[Dict[str, Any]] = []
        self.reboot_required = False

    def generate(
        self,
        report: Dict[str, Any],
        categories: Optional[List[str]] = None,
        severities: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generate remediation from a scan report.

        Args:
            report: Full scan report dict
            categories: Filter to specific categories (None = all)
            severities: Filter to specific severities (None = all)

        Returns:
            Dict with script content, items list, and metadata
        """
        self.sysctl_items = []
        self.other_items = []
        self.reboot_required = False

        scan_results = report.get("scan_results", {})
        server_info = report.get("server_info", {})
        hostname = server_info.get("hostname", "unknown")
        role = server_info.get("role", "unknown")
        if isinstance(role, dict):
            role = role.get("detected", "unknown")

        non_compliant = []
        for cat, items in scan_results.items():
            if categories and cat not in categories:
                continue
            for item in items:
                if item.get("compliance", True):
                    continue
                if severities and item.get("severity") not in severities:
                    continue
                non_compliant.append(item)

        if not non_compliant:
            return {
                "script": "",
                "items": [],
                "total_fixes": 0,
                "reboot_required": False,
                "hostname": hostname,
                "role": role,
            }

        self._classify_items(non_compliant)
        script = self._build_script(hostname, role)

        return {
            "script": script,
            "items": [
                {
                    "item": it["item"],
                    "category": it.get("category", ""),
                    "severity": it.get("severity", ""),
                    "current_value": it.get("current_value", ""),
                    "recommended_value": it.get("recommended_value", ""),
                    "fix_type": self._get_fix_type(it),
                }
                for it in non_compliant
            ],
            "total_fixes": len(non_compliant),
            "reboot_required": self.reboot_required,
            "hostname": hostname,
            "role": role,
        }

    def _classify_items(self, items: List[Dict[str, Any]]) -> None:
        """Classify items by remediation type."""
        for item in items:
            remediation = item.get("remediation", {})
            if remediation.get("requires_reboot", False):
                self.reboot_required = True

            cmd = remediation.get("command", "")
            # Detect sysctl items
            if "sysctl" in cmd or item.get("item", "").startswith(
                ("vm.", "net.", "kernel.", "fs.")
            ):
                self.sysctl_items.append(item)
            elif cmd:
                self.other_items.append(item)
            else:
                # Items without a command go to other (manual)
                self.other_items.append(item)

    def _get_fix_type(self, item: Dict[str, Any]) -> str:
        """Determine the fix type for an item."""
        remediation = item.get("remediation", {})
        cmd = remediation.get("command", "")
        if "sysctl" in cmd or item.get("item", "").startswith(
            ("vm.", "net.", "kernel.", "fs.")
        ):
            return "sysctl"
        if cmd:
            return "command"
        if remediation.get("requires_reboot"):
            return "reboot_required"
        return "manual"

    def _build_script(self, hostname: str, role: str) -> str:
        """Build the full remediation shell script."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        parts = [
            self.SCRIPT_HEADER.format(
                timestamp=ts,
                hostname=hostname,
                role=role,
                script_name="remediate.sh",
            )
        ]

        if self.sysctl_items:
            parts.append("# ── Sysctl Fixes ──────────────────────────────")
            for item in self.sysctl_items:
                name = item["item"]
                rec = item.get("recommended_value", "")
                desc = item.get("description", "")
                cur = item.get("current_value", "")
                sev = item.get("severity", "info")

                # Convert item name to sysctl key format
                sysctl_key = name.replace("-", ".")

                parts.append(f'echo "── [{sev.upper()}] {name}: {desc}"')
                parts.append(f'echo "   Current: {cur} → Recommended: {rec}"')
                parts.append(f'apply_sysctl "{sysctl_key}" "{rec}"')
                parts.append(f'persist_sysctl "{sysctl_key}" "{rec}"')
                parts.append("")

        if self.other_items:
            parts.append(
                "# ── Other Fixes ───────────────────────────────"
            )
            for item in self.other_items:
                name = item["item"]
                remediation = item.get("remediation", {})
                cmd = remediation.get("command", "")
                desc = item.get("description", "")
                sev = item.get("severity", "info")

                parts.append(f'echo "── [{sev.upper()}] {name}: {desc}"')
                if cmd:
                    parts.append(f"if $DRY_RUN; then")
                    parts.append(f'    log "DRY-RUN: {cmd}"')
                    parts.append(f"else")
                    parts.append(f"    {cmd}")
                    parts.append(
                        f'    log "APPLIED: {name}"'
                    )
                    parts.append(f"fi")
                else:
                    persistent = remediation.get("persistent", "")
                    if persistent:
                        parts.append(
                            f'log "MANUAL: {name} — {persistent}"'
                        )
                    else:
                        parts.append(
                            f'log "MANUAL: {name} — no auto-fix available"'
                        )
                parts.append("")

        if self.reboot_required:
            parts.append(
                'echo ""'
            )
            parts.append(
                'echo "⚠ WARNING: Some changes require a reboot to take effect."'
            )

        parts.append(self.SCRIPT_FOOTER)
        return "\n".join(parts)

    @staticmethod
    def generate_single_fix(item: Dict[str, Any]) -> Optional[str]:
        """Generate a single-item fix command (for API use)."""
        remediation = item.get("remediation", {})
        cmd = remediation.get("command", "")
        if cmd:
            return cmd
        return None
