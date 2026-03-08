"""systemd service and system configuration collector."""

import json
import os
from typing import Any, Dict, List

from infra_auditor.collectors.base import BaseCollector


class SystemdCollector(BaseCollector):
    """Collect systemd service configuration and status information."""

    # Define critical services per server role
    ROLE_SERVICES = {
        "control": [
            "etcd", "etcd.service",
            "kube-apiserver", "kube-apiserver.service", 
            "kube-scheduler", "kube-scheduler.service",
            "kube-controller-manager", "kube-controller-manager.service",
            "docker", "docker.service",
            "containerd", "containerd.service"
        ],
        "compute": [
            "libvirtd", "libvirtd.service",
            "qemu-kvm", 
            "ovs-vswitchd", "ovs-vswitchd.service",
            "ovsdb-server", "ovsdb-server.service",
            "nova-compute", "nova-compute.service"
        ],
        "network": [
            "haproxy", "haproxy.service",
            "nginx", "nginx.service", 
            "keepalived", "keepalived.service",
            "ovs-vswitchd", "ovs-vswitchd.service"
        ],
        "storage-ceph": [
            "ceph-osd@*", "ceph-mon@*", "ceph-mgr@*", "ceph-mds@*"
        ],
        "storage-s3": [
            "radosgw@*", "nginx", "nginx.service"
        ],
        "common": [
            "chronyd", "chronyd.service", "ntpd", "ntpd.service",
            "rsyslog", "rsyslog.service",
            "auditd", "auditd.service", 
            "firewalld", "firewalld.service",
            "iptables", "iptables.service",
            "irqbalance", "irqbalance.service",
            "tuned", "tuned.service"
        ]
    }

    def collect(self) -> Dict[str, Any]:
        """Collect systemd information."""
        # Check if systemd is available
        if not self._is_systemd_available():
            return {"available": False}
        
        return {
            "available": True,
            "system_config": self._get_system_config(),
            "services": self._get_services_info(),
            "targets": self._get_targets_info(),
            "failed_units": self._get_failed_units(),
            "journald_config": self._get_journald_config(),
            "logind_config": self._get_logind_config(),
            "performance_metrics": self._get_performance_metrics(),
        }

    def _is_systemd_available(self) -> bool:
        """Check if systemd is available on the system."""
        return (
            self._run_command(["systemctl", "--version"]) != ""
            and os.path.exists("/run/systemd/system")
        )

    def _get_system_config(self) -> Dict[str, Any]:
        """Get systemd system configuration."""
        system_config: Dict[str, Any] = {}
        
        # Read system.conf
        system_conf_content = self._read_file("/etc/systemd/system.conf")
        if system_conf_content:
            system_config["system_conf"] = self._parse_systemd_config(system_conf_content)
        
        # Get system-wide defaults via systemctl
        show_output = self._run_command(["systemctl", "show"])
        if show_output:
            system_config["system_properties"] = self._parse_systemctl_show(show_output)
        
        # Get systemd version
        version_output = self._run_command(["systemctl", "--version"])
        if version_output:
            lines = version_output.split("\n")
            if lines:
                version_line = lines[0]
                if "systemd" in version_line:
                    system_config["version"] = version_line.split()[-1] if version_line.split() else "unknown"
        
        return system_config

    def _parse_systemd_config(self, config_content: str) -> Dict[str, str]:
        """Parse systemd configuration file content."""
        config = {}
        current_section = "main"
        
        for line in config_content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                continue
                
            if "=" in line:
                key, value = line.split("=", 1)
                config[f"{current_section}.{key.strip()}"] = value.strip()
        
        return config

    def _parse_systemctl_show(self, show_output: str) -> Dict[str, str]:
        """Parse systemctl show output."""
        properties = {}
        
        for line in show_output.split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                properties[key] = value
        
        return properties

    def _get_services_info(self) -> Dict[str, Any]:
        """Get information about systemd services."""
        services_info: Dict[str, Any] = {
            "role_services": {},
            "all_services_summary": {},
            "service_details": {}
        }
        
        # Check services for each role
        for role, service_names in self.ROLE_SERVICES.items():
            role_services = []
            for service_name in service_names:
                if "*" in service_name:
                    # Handle wildcard services like ceph-osd@*
                    matching_services = self._find_wildcard_services(service_name)
                    for matching_service in matching_services:
                        service_info = self._get_service_status(matching_service)
                        if service_info:
                            role_services.append(service_info)
                else:
                    service_info = self._get_service_status(service_name)
                    if service_info:
                        role_services.append(service_info)
            
            services_info["role_services"][role] = role_services
        
        # Get summary of all services
        list_units_output = self._run_command([
            "systemctl", "list-units", "--type=service", "--no-pager", "--plain"
        ])
        if list_units_output:
            services_info["all_services_summary"] = self._parse_list_units(list_units_output)
        
        return services_info

    def _find_wildcard_services(self, pattern: str) -> List[str]:
        """Find services matching a wildcard pattern."""
        matching_services = []
        
        # Convert pattern to systemctl list pattern
        # e.g., ceph-osd@* becomes ceph-osd@*.service
        if not pattern.endswith(".service"):
            if "@" in pattern:
                list_pattern = pattern.replace("*", "*.service")
            else:
                list_pattern = f"{pattern}*.service"
        else:
            list_pattern = pattern
        
        # List units matching pattern
        list_output = self._run_command([
            "systemctl", "list-units", "--type=service", "--all", 
            "--no-pager", "--plain", list_pattern
        ])
        
        if list_output:
            for line in list_output.split("\n"):
                if line.strip() and not line.strip().startswith("●"):
                    parts = line.split()
                    if parts and parts[0].endswith(".service"):
                        matching_services.append(parts[0])
        
        return matching_services

    def _get_service_status(self, service_name: str) -> Dict[str, Any]:
        """Get detailed status for a specific service."""
        service_info: Dict[str, Any] = {"name": service_name}
        
        # Ensure service name has .service suffix if not already
        if not service_name.endswith(".service") and "@" not in service_name:
            service_name_full = f"{service_name}.service"
        else:
            service_name_full = service_name
        
        # Get basic status
        status_output = self._run_command([
            "systemctl", "is-active", service_name_full
        ])
        service_info["active"] = status_output.strip()
        
        enabled_output = self._run_command([
            "systemctl", "is-enabled", service_name_full
        ])
        service_info["enabled"] = enabled_output.strip()
        
        # Get detailed properties
        show_output = self._run_command([
            "systemctl", "show", service_name_full
        ])
        if show_output:
            properties = self._parse_systemctl_show(show_output)
            
            # Extract key properties
            key_properties = [
                "Type", "ExecStart", "ExecStop", "Restart", "RestartSec",
                "TimeoutStartUSec", "TimeoutStopUSec", "LimitNOFILE", 
                "LimitNPROC", "LimitMEMLOCK", "LimitCORE", "OOMScoreAdjust",
                "CPUAffinity", "MemoryLimit", "MemoryMax", "TasksMax",
                "User", "Group", "WorkingDirectory", "Environment",
                "PrivateTmp", "ProtectSystem", "ProtectHome", "WatchdogUSec",
                "After", "Requires", "Wants", "PartOf"
            ]
            
            for prop in key_properties:
                if prop in properties:
                    service_info[prop] = properties[prop]
        
        # Get unit file path and content if possible
        unit_file_output = self._run_command([
            "systemctl", "show", service_name_full, "--property=FragmentPath"
        ])
        if unit_file_output and "=" in unit_file_output:
            unit_file_path = unit_file_output.split("=", 1)[1].strip()
            if unit_file_path and os.path.exists(unit_file_path):
                service_info["unit_file_path"] = unit_file_path
                unit_file_content = self._read_file(unit_file_path)
                if unit_file_content:
                    service_info["unit_file_config"] = self._parse_unit_file(unit_file_content)
        
        return service_info

    def _parse_list_units(self, list_output: str) -> Dict[str, Any]:
        """Parse systemctl list-units output."""
        summary = {
            "total_services": 0,
            "active_services": 0,
            "failed_services": 0,
            "inactive_services": 0
        }
        
        for line in list_output.split("\n"):
            if ".service" in line:
                summary["total_services"] += 1
                if "active" in line and "running" in line:
                    summary["active_services"] += 1
                elif "failed" in line:
                    summary["failed_services"] += 1
                elif "inactive" in line:
                    summary["inactive_services"] += 1
        
        return summary

    def _parse_unit_file(self, unit_content: str) -> Dict[str, Dict[str, str]]:
        """Parse systemd unit file content."""
        config = {}
        current_section = None
        
        for line in unit_content.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
                
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                config[current_section] = {}
                continue
                
            if current_section and "=" in line:
                key, value = line.split("=", 1)
                config[current_section][key.strip()] = value.strip()
        
        return config

    def _get_targets_info(self) -> Dict[str, Any]:
        """Get systemd targets information."""
        targets_info: Dict[str, Any] = {}
        
        # Get current default target
        default_target = self._run_command(["systemctl", "get-default"])
        targets_info["default_target"] = default_target.strip()
        
        # Get active targets
        list_targets_output = self._run_command([
            "systemctl", "list-units", "--type=target", "--no-pager", "--plain"
        ])
        if list_targets_output:
            active_targets = []
            for line in list_targets_output.split("\n"):
                if ".target" in line and "active" in line:
                    parts = line.split()
                    if parts:
                        active_targets.append(parts[0])
            targets_info["active_targets"] = active_targets
        
        return targets_info

    def _get_failed_units(self) -> List[str]:
        """Get list of failed systemd units."""
        failed_output = self._run_command([
            "systemctl", "list-units", "--failed", "--no-pager", "--plain"
        ])
        
        failed_units = []
        if failed_output:
            for line in failed_output.split("\n"):
                if "failed" in line:
                    parts = line.split()
                    if parts:
                        failed_units.append(parts[0])
        
        return failed_units

    def _get_journald_config(self) -> Dict[str, Any]:
        """Get journald configuration."""
        journald_config: Dict[str, Any] = {}
        
        # Read journald.conf
        journald_conf_content = self._read_file("/etc/systemd/journald.conf")
        if journald_conf_content:
            journald_config["journald_conf"] = self._parse_systemd_config(journald_conf_content)
        
        # Get journal disk usage
        journal_usage = self._run_command(["journalctl", "--disk-usage"])
        if journal_usage:
            journald_config["disk_usage"] = journal_usage.strip()
        
        # Get journal statistics
        journal_stats = self._run_command(["systemd-analyze", "plot"])
        if journal_stats:
            journald_config["has_systemd_analyze"] = True
        
        return journald_config

    def _get_logind_config(self) -> Dict[str, Any]:
        """Get logind configuration."""
        logind_config: Dict[str, Any] = {}
        
        # Read logind.conf
        logind_conf_content = self._read_file("/etc/systemd/logind.conf")
        if logind_conf_content:
            logind_config["logind_conf"] = self._parse_systemd_config(logind_conf_content)
        
        return logind_config

    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get systemd performance metrics."""
        performance: Dict[str, Any] = {}
        
        # Boot time analysis
        boot_time = self._run_command(["systemd-analyze", "time"])
        if boot_time:
            performance["boot_time"] = boot_time.strip()
        
        # Critical chain
        critical_chain = self._run_command(["systemd-analyze", "critical-chain"])
        if critical_chain:
            performance["critical_chain"] = critical_chain
        
        # Blame (slowest services)
        blame_output = self._run_command(["systemd-analyze", "blame"])
        if blame_output:
            # Parse top 10 slowest services
            slow_services = []
            for line in blame_output.split("\n")[:10]:
                if line.strip():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        slow_services.append({
                            "time": parts[0],
                            "service": " ".join(parts[1:])
                        })
            performance["slowest_services"] = slow_services
        
        return performance