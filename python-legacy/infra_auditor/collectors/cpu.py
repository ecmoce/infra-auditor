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
            "isolation": self._get_cpu_isolation_info(),
            "virtualization": self._get_virtualization_info(),
            "frequency": self._get_frequency_info(),
            "p_states": self._get_p_states_info(),
            "microcode": self._get_microcode_info(),
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

    def _get_cpu_isolation_info(self) -> Dict[str, Any]:
        """Get CPU isolation information."""
        result = {}
        
        # Check kernel command line for isolcpus
        cmdline = self._read_file("/proc/cmdline", "")
        if cmdline:
            # Parse isolcpus parameter
            isolcpus_match = re.search(r'isolcpus=([^\s]+)', cmdline)
            if isolcpus_match:
                result["isolcpus"] = isolcpus_match.group(1)
                
            # Parse nohz_full parameter
            nohz_match = re.search(r'nohz_full=([^\s]+)', cmdline)
            if nohz_match:
                result["nohz_full"] = nohz_match.group(1)
                
            # Parse rcu_nocbs parameter
            rcu_match = re.search(r'rcu_nocbs=([^\s]+)', cmdline)
            if rcu_match:
                result["rcu_nocbs"] = rcu_match.group(1)

        # Check cgroup cpuset
        cpuset_cpus = self._read_file("/sys/fs/cgroup/cpuset/cpuset.cpus", "")
        if cpuset_cpus:
            result["cpuset_cpus"] = cpuset_cpus
            
        return result

    def _get_virtualization_info(self) -> Dict[str, Any]:
        """Get virtualization-related information."""
        result = {}
        
        # Check for KVM nested virtualization
        kvm_intel_nested = self._read_file("/sys/module/kvm_intel/parameters/nested", "")
        if kvm_intel_nested:
            result["kvm_intel_nested"] = kvm_intel_nested
            
        kvm_amd_nested = self._read_file("/sys/module/kvm_amd/parameters/nested", "")
        if kvm_amd_nested:
            result["kvm_amd_nested"] = kvm_amd_nested
            
        # Check for VFIO/IOMMU settings
        cmdline = self._read_file("/proc/cmdline", "")
        if cmdline:
            if "intel_iommu=on" in cmdline:
                result["intel_iommu"] = "on"
            if "iommu=pt" in cmdline:
                result["iommu"] = "pt"
            if "vfio-pci" in cmdline:
                result["vfio_pci"] = "enabled"
                
        # Check if running under hypervisor
        virt_type = self._run_command(["systemd-detect-virt"], "")
        if virt_type and virt_type != "none":
            result["detected_virtualization"] = virt_type
            
        # Check for hypervisor CPUID leaf
        cpu_flags = self._read_file("/proc/cpuinfo", "")
        if cpu_flags and "hypervisor" in cpu_flags:
            result["hypervisor_flag"] = True
            
        return result

    def _get_frequency_info(self) -> Dict[str, Any]:
        """Get CPU frequency scaling information."""
        result = {}
        
        # Check scaling driver
        driver = self._read_file("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver", "")
        if driver:
            result["scaling_driver"] = driver
            
        # Check available governors
        governors = self._read_file("/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors", "")
        if governors:
            result["available_governors"] = governors.split()
            
        # Check current frequencies for each CPU
        cpu_dirs = glob.glob("/sys/devices/system/cpu/cpu[0-9]*")
        frequencies = {}
        for cpu_dir in cpu_dirs:
            cpu_num = os.path.basename(cpu_dir)
            freq_path = os.path.join(cpu_dir, "cpufreq/scaling_cur_freq")
            freq = self._read_file(freq_path, "")
            if freq:
                frequencies[cpu_num] = freq
                
        if frequencies:
            result["current_frequencies"] = frequencies
            
        # Check for turbo boost status
        turbo_pct = self._read_file("/sys/devices/system/cpu/intel_pstate/turbo_pct", "")
        if turbo_pct:
            result["turbo_pct"] = turbo_pct
            
        no_turbo = self._read_file("/sys/devices/system/cpu/intel_pstate/no_turbo", "")
        if no_turbo:
            result["no_turbo"] = no_turbo
            
        return result

    def _get_p_states_info(self) -> Dict[str, Any]:
        """Get P-states information."""
        result = {}
        
        # Check Intel P-state driver status
        status = self._read_file("/sys/devices/system/cpu/intel_pstate/status", "")
        if status:
            result["status"] = status
            
        # Check min/max performance
        min_perf = self._read_file("/sys/devices/system/cpu/intel_pstate/min_perf_pct", "")
        if min_perf:
            result["min_perf_pct"] = min_perf
            
        max_perf = self._read_file("/sys/devices/system/cpu/intel_pstate/max_perf_pct", "")
        if max_perf:
            result["max_perf_pct"] = max_perf
            
        return result

    def _get_microcode_info(self) -> Dict[str, Any]:
        """Get microcode information."""
        result = {}
        
        # Get current microcode version from /proc/cpuinfo
        cpuinfo = self._read_file("/proc/cpuinfo", "")
        if cpuinfo:
            microcode_match = re.search(r'microcode\s+:\s+(.+)', cpuinfo)
            if microcode_match:
                result["current_version"] = microcode_match.group(1).strip()
                
        # Check microcode update time from dmesg (if available)
        dmesg_output = self._run_command(["dmesg"], "")
        if dmesg_output:
            microcode_lines = [line for line in dmesg_output.split('\n') 
                             if 'microcode' in line.lower()]
            if microcode_lines:
                result["dmesg_info"] = microcode_lines[-3:]  # Last 3 lines
                
        return result
