"""Memory information collector."""

import re
from typing import Any, Dict

from infra_auditor.collectors.base import BaseCollector


class MemoryCollector(BaseCollector):
    """Collect memory hardware and tuning information."""

    def collect(self) -> Dict[str, Any]:
        """Collect memory information."""
        meminfo = self._parse_meminfo()
        return {
            "total_kb": meminfo.get("MemTotal", 0),
            "total_gb": round(meminfo.get("MemTotal", 0) / (1024 * 1024), 1),
            "available_kb": meminfo.get("MemAvailable", 0),
            "swap_total_kb": meminfo.get("SwapTotal", 0),
            "hugepages_total": meminfo.get("HugePages_Total", 0),
            "hugepages_free": meminfo.get("HugePages_Free", 0),
            "hugepage_size_kb": meminfo.get("Hugepagesize", 0),
            "swappiness": self._read_sysctl("vm.swappiness", "unknown"),
            "dirty_ratio": self._read_sysctl("vm.dirty_ratio", "unknown"),
            "dirty_background_ratio": self._read_sysctl(
                "vm.dirty_background_ratio", "unknown"
            ),
            "overcommit_memory": self._read_sysctl(
                "vm.overcommit_memory", "unknown"
            ),
            "transparent_hugepage": self._get_thp_status(),
            "numa_balancing": self._read_sysctl(
                "kernel.numa_balancing", "unknown"
            ),
            "zone_reclaim_mode": self._read_sysctl(
                "vm.zone_reclaim_mode", "unknown"
            ),
        }

    def _parse_meminfo(self) -> Dict[str, int]:
        """Parse /proc/meminfo into a dict."""
        result = {}
        content = self._read_file("/proc/meminfo")
        for line in content.splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                key = parts[0].strip()
                val_str = parts[1].strip().split()[0]  # strip "kB"
                try:
                    result[key] = int(val_str)
                except ValueError:
                    pass
        return result

    def _get_thp_status(self) -> str:
        """Get transparent hugepage status."""
        content = self._read_file(
            "/sys/kernel/mm/transparent_hugepage/enabled", "unknown"
        )
        # Format: "always [madvise] never" — bracketed value is active
        match = re.search(r"\[(\w+)\]", content)
        if match:
            return match.group(1)
        return content
