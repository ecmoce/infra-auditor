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
            "ksm": self._get_ksm_info(),
            "overcommit_ratio": self._read_sysctl(
                "vm.overcommit_ratio", "unknown"
            ),
            "min_free_kbytes": self._read_sysctl(
                "vm.min_free_kbytes", "unknown"
            ),
            "vfs_cache_pressure": self._read_sysctl(
                "vm.vfs_cache_pressure", "unknown"
            ),
            "hugepages_1gb": self._get_hugepages_1gb_info(),
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

    def _get_ksm_info(self) -> Dict[str, str]:
        """Get KSM (Kernel Same-page Merging) information."""
        result = {}
        
        # Check if KSM is enabled
        run = self._read_file("/sys/kernel/mm/ksm/run", "")
        if run:
            result["run"] = run
            
        # Get shared pages count
        pages_shared = self._read_file("/sys/kernel/mm/ksm/pages_shared", "")
        if pages_shared:
            result["pages_shared"] = pages_shared
            
        # Get sharing violations count
        pages_sharing = self._read_file("/sys/kernel/mm/ksm/pages_sharing", "")
        if pages_sharing:
            result["pages_sharing"] = pages_sharing
            
        # Get unshared pages count
        pages_unshared = self._read_file("/sys/kernel/mm/ksm/pages_unshared", "")
        if pages_unshared:
            result["pages_unshared"] = pages_unshared
            
        # Get volatile pages count
        pages_volatile = self._read_file("/sys/kernel/mm/ksm/pages_volatile", "")
        if pages_volatile:
            result["pages_volatile"] = pages_volatile
            
        return result

    def _get_hugepages_1gb_info(self) -> Dict[str, str]:
        """Get 1GB hugepages information."""
        result = {}
        
        # Check for 1GB hugepages support
        hugepages_1gb_path = "/sys/kernel/mm/hugepages/hugepages-1048576kB"
        if self._read_file(f"{hugepages_1gb_path}/nr_hugepages", "") != "":
            nr_hugepages = self._read_file(f"{hugepages_1gb_path}/nr_hugepages", "")
            if nr_hugepages:
                result["nr_hugepages"] = nr_hugepages
                
            free_hugepages = self._read_file(f"{hugepages_1gb_path}/free_hugepages", "")
            if free_hugepages:
                result["free_hugepages"] = free_hugepages
                
            surplus_hugepages = self._read_file(f"{hugepages_1gb_path}/surplus_hugepages", "")
            if surplus_hugepages:
                result["surplus_hugepages"] = surplus_hugepages
                
        return result
