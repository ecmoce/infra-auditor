"""Kernel parameter collector."""

from typing import Any, Dict

from infra_auditor.collectors.base import BaseCollector


class KernelCollector(BaseCollector):
    """Collect kernel parameters and limits."""

    def collect(self) -> Dict[str, Any]:
        """Collect kernel information."""
        return {
            "file_max": self._read_sysctl("fs.file-max", "unknown"),
            "pid_max": self._read_sysctl("kernel.pid_max", "unknown"),
            "threads_max": self._read_sysctl("kernel.threads-max", "unknown"),
            "cmdline": self._get_cmdline_params(),
        }

    def _get_cmdline_params(self) -> Dict[str, str]:
        """Parse kernel command line parameters of interest."""
        cmdline = self._read_file("/proc/cmdline")
        params: Dict[str, str] = {}
        interesting = [
            "isolcpus",
            "nohz_full",
            "rcu_nocbs",
            "intel_pstate",
            "hugepagesz",
            "hugepages",
            "default_hugepagesz",
        ]
        for token in cmdline.split():
            for key in interesting:
                if token.startswith(key + "="):
                    params[key] = token.split("=", 1)[1]
                elif token == key:
                    params[key] = "enabled"
        return params
