"""CPU information collector."""

import glob
import os
import platform
import re
from typing import Any, Dict, List, Optional

from infra_auditor.collectors.base import BaseCollector


class CPUCollector(BaseCollector):
    """Collect CPU hardware and tuning information."""

    def collect(self) -> Dict[str, Any]:
        """Collect CPU information."""
        return {
            "model": self._get_cpu_model(),
            "architecture": platform.machine(),
            "sockets": self._get_sockets(),
            "cores_per_socket": self._get_cores_per_socket(),
            "threads_per_core": self._get_threads_per_core(),
            "total_cores": self._get_total_cores(),
            "total_threads": self._get_total_threads(),
            "numa_nodes": self._get_numa_nodes(),
            "governor": self._get_governor(),
            "max_cstate": self._get_max_cstate(),
        }

    def _get_cpu_model(self) -> str:
        cpuinfo = self._read_file("/proc/cpuinfo")
        for line in cpuinfo.splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
        return platform.processor() or "unknown"

    def _get_sockets(self) -> int:
        cpuinfo = self._read_file("/proc/cpuinfo")
        physical_ids = set()
        for line in cpuinfo.splitlines():
            if line.startswith("physical id"):
                physical_ids.add(line.split(":", 1)[1].strip())
        return len(physical_ids) or 1

    def _get_cores_per_socket(self) -> int:
        cpuinfo = self._read_file("/proc/cpuinfo")
        for line in cpuinfo.splitlines():
            if line.startswith("cpu cores"):
                try:
                    return int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
        return self._get_total_cores()

    def _get_threads_per_core(self) -> int:
        total = self._get_total_threads()
        cores = self._get_total_cores()
        if cores > 0:
            return total // cores
        return 1

    def _get_total_cores(self) -> int:
        """Get total physical cores."""
        try:
            dirs = glob.glob("/sys/devices/system/cpu/cpu[0-9]*")
            if dirs:
                # Count unique core_ids across all physical packages
                core_set = set()
                for d in dirs:
                    core_id = self._read_file(
                        os.path.join(d, "topology/core_id"), ""
                    )
                    phys_id = self._read_file(
                        os.path.join(d, "topology/physical_package_id"), ""
                    )
                    if core_id and phys_id:
                        core_set.add((phys_id, core_id))
                if core_set:
                    return len(core_set)
        except OSError:
            pass
        # Fallback: count processors in /proc/cpuinfo
        cpuinfo = self._read_file("/proc/cpuinfo")
        count = sum(1 for l in cpuinfo.splitlines() if l.startswith("processor"))
        return count or 1

    def _get_total_threads(self) -> int:
        """Get total logical CPUs (threads)."""
        try:
            dirs = glob.glob("/sys/devices/system/cpu/cpu[0-9]*")
            if dirs:
                return len(dirs)
        except OSError:
            pass
        # Fallback
        try:
            import os as _os
            cpus = _os.cpu_count()
            if cpus:
                return cpus
        except Exception:
            pass
        return 1

    def _get_numa_nodes(self) -> int:
        try:
            dirs = glob.glob("/sys/devices/system/node/node[0-9]*")
            if dirs:
                return len(dirs)
        except OSError:
            pass
        return 1

    def _get_governor(self) -> str:
        return self._read_file(
            "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor",
            "unknown",
        )

    def _get_max_cstate(self) -> str:
        return self._read_file(
            "/sys/module/intel_idle/parameters/max_cstate",
            "unknown",
        )
