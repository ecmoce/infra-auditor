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
            "scheduler": self._get_scheduler_info(),
            "panic": self._get_panic_settings(),
            "core_pattern": self._read_sysctl("kernel.core_pattern", "unknown"),
            "watchdog": self._get_watchdog_info(),
            "numa_balancing": self._read_sysctl("kernel.numa_balancing", "unknown"),
            "version": self._get_kernel_version(),
            "cgroup_version": self._get_cgroup_version(),
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
            "intel_iommu",
            "iommu",
            "vfio-pci",
            "intel_idle.max_cstate",
            "processor.max_cstate",
            "transparent_hugepage",
            "systemd.unified_cgroup_hierarchy",
            "cgroup_enable",
        ]
        for token in cmdline.split():
            for key in interesting:
                if token.startswith(key + "="):
                    params[key] = token.split("=", 1)[1]
                elif token == key:
                    params[key] = "enabled"
        return params

    def _get_scheduler_info(self) -> Dict[str, str]:
        """Get kernel scheduler tuning parameters."""
        result = {}
        
        scheduler_params = [
            "kernel.sched_migration_cost_ns",
            "kernel.sched_autogroup_enabled",
            "kernel.sched_latency_ns",
            "kernel.sched_min_granularity_ns",
            "kernel.sched_wakeup_granularity_ns",
            "kernel.sched_rt_period_us",
            "kernel.sched_rt_runtime_us",
        ]
        
        for param in scheduler_params:
            value = self._read_sysctl(param, "")
            if value:
                result[param] = value
                
        return result

    def _get_panic_settings(self) -> Dict[str, str]:
        """Get kernel panic and crash handling settings."""
        result = {}
        
        panic_params = [
            "kernel.panic",
            "kernel.panic_on_oops",
            "kernel.panic_on_io_nmi",
            "kernel.panic_on_unrecovered_nmi",
            "kernel.panic_on_warn",
            "kernel.unknown_nmi_panic",
        ]
        
        for param in panic_params:
            value = self._read_sysctl(param, "")
            if value:
                result[param] = value
                
        return result

    def _get_watchdog_info(self) -> Dict[str, str]:
        """Get kernel watchdog settings."""
        result = {}
        
        watchdog_params = [
            "kernel.watchdog",
            "kernel.watchdog_thresh",
            "kernel.nmi_watchdog",
            "kernel.soft_watchdog",
            "kernel.hardlockup_panic",
            "kernel.softlockup_panic",
        ]
        
        for param in watchdog_params:
            value = self._read_sysctl(param, "")
            if value:
                result[param] = value
                
        return result

    def _get_kernel_version(self) -> Dict[str, str]:
        """Get detailed kernel version information."""
        result = {}
        
        # Get version from uname
        version = self._run_command(["uname", "-r"], "")
        if version:
            result["release"] = version
            
        # Get full version string
        full_version = self._read_file("/proc/version", "")
        if full_version:
            result["full_version"] = full_version
            
        return result

    def _get_cgroup_version(self) -> str:
        """Determine if cgroup v1 or v2 is in use."""
        # Check if cgroup v2 is mounted
        cgroup2_mount = self._run_command(["mount", "-t", "cgroup2"], "")
        if cgroup2_mount:
            return "v2"
            
        # Check cgroup v1 mounts
        cgroup1_mount = self._run_command(["mount", "-t", "cgroup"], "")
        if cgroup1_mount:
            return "v1"
            
        # Check /sys/fs/cgroup to see what type of filesystem it is
        cgroup_fstype = self._run_command(["stat", "-f", "-c", "%T", "/sys/fs/cgroup"], "")
        if cgroup_fstype:
            if "cgroup2fs" in cgroup_fstype:
                return "v2"
            elif "tmpfs" in cgroup_fstype:
                return "v1"
                
        return "unknown"
