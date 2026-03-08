"""Open vSwitch (OVS) information collector."""

import glob
import json
import os
from typing import Any, Dict, List

from infra_auditor.collectors.base import BaseCollector


class OVSCollector(BaseCollector):
    """Collect Open vSwitch configuration and performance information."""

    def collect(self) -> Dict[str, Any]:
        """Collect OVS information."""
        # Check if OVS is available
        if not self._is_ovs_available():
            return {"available": False}
        
        return {
            "available": True,
            "version": self._get_ovs_version(),
            "bridges": self._get_bridges(),
            "dpdk_config": self._get_dpdk_config(),
            "global_config": self._get_global_config(),
            "bonding": self._get_ovs_bonding(),
            "datapath": self._get_datapath_info(),
            "flow_tables": self._get_flow_table_stats(),
            "performance": self._get_performance_info(),
        }

    def _is_ovs_available(self) -> bool:
        """Check if OVS is available on the system."""
        return (
            self._run_command(["ovs-vsctl", "--version"]) != ""
            and os.path.exists("/var/run/openvswitch")
        )

    def _get_ovs_version(self) -> Dict[str, Any]:
        """Get OVS version information."""
        version_output = self._run_command(["ovs-vsctl", "--version"])
        version_info: Dict[str, Any] = {"raw_output": version_output}
        
        if version_output:
            lines = version_output.split("\n")
            for line in lines:
                if "ovs-vsctl" in line and ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        version_info["version"] = parts[1].strip()
                elif "DB Schema" in line and ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        version_info["db_schema"] = parts[1].strip()

        return version_info

    def _get_bridges(self) -> List[Dict[str, Any]]:
        """Get OVS bridge information."""
        bridges = []
        
        # Get bridge list
        bridge_list = self._run_command(["ovs-vsctl", "list-br"])
        if not bridge_list:
            return bridges

        for bridge_name in bridge_list.split("\n"):
            bridge_name = bridge_name.strip()
            if not bridge_name:
                continue

            bridge_info: Dict[str, Any] = {"name": bridge_name}
            
            # Get bridge details using ovs-vsctl show
            show_output = self._run_command(["ovs-vsctl", "show"])
            bridge_info["show_output"] = show_output

            # Get bridge specific configuration
            bridge_info["datapath_type"] = self._run_command([
                "ovs-vsctl", "get", "bridge", bridge_name, "datapath_type"
            ]).strip('"')

            # Get ports
            ports_output = self._run_command([
                "ovs-vsctl", "list-ports", bridge_name
            ])
            bridge_info["ports"] = [
                p.strip() for p in ports_output.split("\n") if p.strip()
            ]

            # Get flow eviction threshold
            flow_threshold = self._run_command([
                "ovs-vsctl", "get", "bridge", bridge_name,
                "other_config:flow-eviction-threshold"
            ])
            if flow_threshold and flow_threshold != "{}":
                bridge_info["flow_eviction_threshold"] = flow_threshold.strip('"')

            bridges.append(bridge_info)

        return bridges

    def _get_dpdk_config(self) -> Dict[str, Any]:
        """Get DPDK configuration."""
        dpdk_config: Dict[str, Any] = {}

        # Check DPDK initialization
        dpdk_init = self._run_command([
            "ovs-vsctl", "get", "Open_vSwitch", ".", "other_config:dpdk-init"
        ])
        dpdk_config["dpdk_init"] = dpdk_init.strip('"') if dpdk_init else ""

        # DPDK socket memory
        socket_mem = self._run_command([
            "ovs-vsctl", "get", "Open_vSwitch", ".", "other_config:dpdk-socket-mem"
        ])
        dpdk_config["socket_mem"] = socket_mem.strip('"') if socket_mem else ""

        # DPDK lcore mask
        lcore_mask = self._run_command([
            "ovs-vsctl", "get", "Open_vSwitch", ".", "other_config:dpdk-lcore-mask"
        ])
        dpdk_config["lcore_mask"] = lcore_mask.strip('"') if lcore_mask else ""

        # PMD CPU mask
        pmd_cpu_mask = self._run_command([
            "ovs-vsctl", "get", "Open_vSwitch", ".", "other_config:pmd-cpu-mask"
        ])
        dpdk_config["pmd_cpu_mask"] = pmd_cpu_mask.strip('"') if pmd_cpu_mask else ""

        # Hugepage info
        dpdk_config["hugepage_info"] = self._get_hugepage_info()

        return dpdk_config

    def _get_hugepage_info(self) -> Dict[str, Any]:
        """Get hugepage configuration."""
        hugepage_info: Dict[str, Any] = {}
        
        # Check /proc/meminfo for hugepage info
        meminfo = self._read_file("/proc/meminfo")
        if meminfo:
            for line in meminfo.split("\n"):
                if "HugePages_" in line or "Hugepagesize" in line:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().split()[0] if parts[1].strip() else ""
                        hugepage_info[key] = value

        # Check hugepage mounts
        mounts = self._read_file("/proc/mounts")
        hugepage_mounts = []
        if mounts:
            for line in mounts.split("\n"):
                if "hugetlbfs" in line:
                    hugepage_mounts.append(line.strip())
        hugepage_info["mounts"] = hugepage_mounts

        return hugepage_info

    def _get_global_config(self) -> Dict[str, Any]:
        """Get global OVS configuration."""
        global_config: Dict[str, Any] = {}

        # Handler threads
        handler_threads = self._run_command([
            "ovs-vsctl", "get", "Open_vSwitch", ".", "other_config:n-handler-threads"
        ])
        global_config["n_handler_threads"] = handler_threads.strip('"') if handler_threads else ""

        # Revalidator threads
        revalidator_threads = self._run_command([
            "ovs-vsctl", "get", "Open_vSwitch", ".", "other_config:n-revalidator-threads"
        ])
        global_config["n_revalidator_threads"] = revalidator_threads.strip('"') if revalidator_threads else ""

        # EMC settings
        emc_size = self._run_command([
            "ovs-vsctl", "get", "Open_vSwitch", ".", "other_config:emc-insert-inv-prob"
        ])
        global_config["emc_insert_inv_prob"] = emc_size.strip('"') if emc_size else ""

        # Connection tracking
        ct_zone_limit = self._run_command([
            "ovs-vsctl", "get", "Open_vSwitch", ".", "other_config:ct-zone-limit"
        ])
        global_config["ct_zone_limit"] = ct_zone_limit.strip('"') if ct_zone_limit else ""

        # Log level
        log_level = self._run_command([
            "ovs-appctl", "vlog/list"
        ])
        global_config["log_level"] = log_level

        return global_config

    def _get_ovs_bonding(self) -> List[Dict[str, Any]]:
        """Get OVS bonding information."""
        bonds = []
        
        # Get all ports and check which ones are bonds
        all_ports_output = self._run_command(["ovs-vsctl", "list", "port"])
        if not all_ports_output:
            return bonds

        # Parse port information to find bonds
        current_port = {}
        for line in all_ports_output.split("\n"):
            line = line.strip()
            if line.startswith("_uuid"):
                if current_port.get("bond_mode"):
                    bonds.append(current_port)
                current_port = {}
            elif ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                
                if key == "name":
                    current_port["name"] = value.strip('"')
                elif key == "bond_mode":
                    current_port["bond_mode"] = value.strip('"')
                elif key == "interfaces":
                    current_port["interfaces"] = value
                elif key == "lacp":
                    current_port["lacp"] = value.strip('"')
                elif key == "other_config":
                    current_port["other_config"] = value

        # Add the last port if it's a bond
        if current_port.get("bond_mode"):
            bonds.append(current_port)

        return bonds

    def _get_datapath_info(self) -> Dict[str, Any]:
        """Get OVS datapath information."""
        datapath_info: Dict[str, Any] = {}

        # Datapath list
        dp_list = self._run_command(["ovs-dpctl", "dump-dps"])
        datapath_info["datapaths"] = [
            dp.strip() for dp in dp_list.split("\n") if dp.strip()
        ]

        # For each datapath, get more details
        dp_details = {}
        for dp in datapath_info["datapaths"]:
            dp_info = {}
            
            # Flow dump stats
            flow_stats = self._run_command(["ovs-dpctl", "show", dp])
            dp_info["stats"] = flow_stats
            
            dp_details[dp] = dp_info

        datapath_info["details"] = dp_details

        return datapath_info

    def _get_flow_table_stats(self) -> Dict[str, Any]:
        """Get flow table statistics."""
        flow_stats: Dict[str, Any] = {}

        # Coverage stats
        coverage_output = self._run_command(["ovs-appctl", "coverage/show"])
        flow_stats["coverage"] = coverage_output

        # Memory usage
        memory_output = self._run_command(["ovs-appctl", "memory/show"])
        flow_stats["memory"] = memory_output

        # DPDK stats if available
        dpdk_stats = self._run_command(["ovs-appctl", "dpif-netdev/pmd-stats-show"])
        flow_stats["pmd_stats"] = dpdk_stats

        return flow_stats

    def _get_performance_info(self) -> Dict[str, Any]:
        """Get OVS performance metrics."""
        performance: Dict[str, Any] = {}

        # Upcall stats
        upcall_stats = self._run_command(["ovs-appctl", "upcall/show"])
        performance["upcall"] = upcall_stats

        # dpctl stats
        dpctl_stats = self._run_command(["ovs-appctl", "dpctl/show"])
        performance["dpctl"] = dpctl_stats

        # LACP status
        lacp_status = self._run_command(["ovs-appctl", "lacp/show"])
        performance["lacp"] = lacp_status

        # Bond status
        bond_status = self._run_command(["ovs-appctl", "bond/show"])
        performance["bond"] = bond_status

        return performance