"""Network information collector."""

import glob
import os
import re
from typing import Any, Dict, List

from infra_auditor.collectors.base import BaseCollector


class NetworkCollector(BaseCollector):
    """Collect network hardware and tuning information."""

    def collect(self) -> Dict[str, Any]:
        """Collect network information."""
        return {
            "interfaces": self._get_interfaces(),
            "sysctl": self._get_network_sysctl(),
            "advanced_tuning": self._get_advanced_network_tuning(),
            "interrupts": self._get_interrupt_info(),
            "conntrack": self._get_conntrack_info(),
        }

    def _get_interfaces(self) -> List[Dict[str, Any]]:
        """Get network interface information."""
        interfaces = []
        try:
            iface_dirs = glob.glob("/sys/class/net/*")
        except OSError:
            return interfaces

        for iface_path in iface_dirs:
            name = os.path.basename(iface_path)
            if name == "lo":
                continue

            iface_info: Dict[str, Any] = {"name": name}

            # Speed
            speed = self._read_file(
                os.path.join(iface_path, "speed"), ""
            )
            if speed and speed != "-1":
                try:
                    iface_info["speed_mbps"] = int(speed)
                except ValueError:
                    pass

            # MTU
            mtu = self._read_file(os.path.join(iface_path, "mtu"), "")
            if mtu:
                try:
                    iface_info["mtu"] = int(mtu)
                except ValueError:
                    pass

            # Driver
            driver_link = os.path.join(iface_path, "device/driver")
            if os.path.islink(driver_link):
                try:
                    iface_info["driver"] = os.path.basename(
                        os.readlink(driver_link)
                    )
                except OSError:
                    pass

            # Operstate
            iface_info["operstate"] = self._read_file(
                os.path.join(iface_path, "operstate"), "unknown"
            )

            # Bonding info
            bonding_slave = os.path.join(iface_path, "master")
            if os.path.exists(bonding_slave):
                try:
                    master = os.path.basename(os.readlink(bonding_slave))
                    iface_info["bond_master"] = master
                except OSError:
                    pass

            interfaces.append(iface_info)

        return interfaces

    def _get_network_sysctl(self) -> Dict[str, str]:
        """Get network-related sysctl values."""
        keys = [
            "net.core.somaxconn",
            "net.core.netdev_max_backlog",
            "net.core.rmem_max",
            "net.core.wmem_max",
            "net.ipv4.tcp_congestion_control",
            "net.ipv4.ip_local_port_range",
            "net.ipv4.tcp_tw_reuse",
            "net.ipv4.tcp_max_syn_backlog",
            "net.ipv4.tcp_rmem",
            "net.ipv4.tcp_wmem",
            # Advanced network tuning parameters
            "net.core.rps_sock_flow_entries",
            "net.core.busy_poll",
            "net.core.busy_read",
            "net.core.netdev_budget",
            "net.core.netdev_budget_usecs",
            "net.core.optmem_max",
            "net.ipv4.neigh.default.gc_thresh1",
            "net.ipv4.neigh.default.gc_thresh2",
            "net.ipv4.neigh.default.gc_thresh3",
            "net.ipv4.tcp_window_scaling",
            "net.ipv4.tcp_timestamps",
            "net.ipv4.tcp_sack",
            "net.netfilter.nf_conntrack_max",
            "net.netfilter.nf_conntrack_buckets",
        ]
        result = {}
        for key in keys:
            val = self._read_sysctl(key, "")
            if val:
                result[key] = val
        return result

    def _get_advanced_network_tuning(self) -> Dict[str, Any]:
        """Get advanced network tuning parameters like RPS, XPS, RFS, etc."""
        result = {}
        
        try:
            iface_dirs = glob.glob("/sys/class/net/*")
        except OSError:
            return result

        for iface_path in iface_dirs:
            name = os.path.basename(iface_path)
            if name == "lo":
                continue

            iface_tuning = {"name": name}

            # RPS (Receive Packet Steering) configuration
            rps_cpus = self._get_rps_config(iface_path)
            if rps_cpus:
                iface_tuning["rps"] = rps_cpus

            # XPS (Transmit Packet Steering) configuration
            xps_cpus = self._get_xps_config(iface_path)
            if xps_cpus:
                iface_tuning["xps"] = xps_cpus

            # RFS (Receive Flow Steering) configuration
            rfs_config = self._get_rfs_config(iface_path)
            if rfs_config:
                iface_tuning["rfs"] = rfs_config

            # RSS (Receive Side Scaling) information via ethtool
            rss_info = self._get_rss_info(name)
            if rss_info:
                iface_tuning["rss"] = rss_info

            # Ring buffer settings
            ring_buffer = self._get_ring_buffer_info(name)
            if ring_buffer:
                iface_tuning["ring_buffer"] = ring_buffer

            # Interrupt coalescing settings
            coalescing = self._get_coalescing_info(name)
            if coalescing:
                iface_tuning["coalescing"] = coalescing

            # Offload settings
            offload = self._get_offload_info(name)
            if offload:
                iface_tuning["offload"] = offload

            # Bonding information
            bonding_info = self._get_bonding_info(iface_path)
            if bonding_info:
                iface_tuning["bonding"] = bonding_info

            if len(iface_tuning) > 1:  # More than just the name
                result[name] = iface_tuning

        return result

    def _get_rps_config(self, iface_path: str) -> Dict[str, str]:
        """Get RPS configuration for an interface."""
        result = {}
        try:
            rx_dirs = glob.glob(os.path.join(iface_path, "queues/rx-*"))
            for rx_dir in rx_dirs:
                queue_name = os.path.basename(rx_dir)
                rps_cpus = self._read_file(os.path.join(rx_dir, "rps_cpus"), "")
                rps_flow_cnt = self._read_file(os.path.join(rx_dir, "rps_flow_cnt"), "")
                
                if rps_cpus or rps_flow_cnt:
                    result[queue_name] = {
                        "rps_cpus": rps_cpus,
                        "rps_flow_cnt": rps_flow_cnt,
                    }
        except OSError:
            pass
        return result

    def _get_xps_config(self, iface_path: str) -> Dict[str, str]:
        """Get XPS configuration for an interface."""
        result = {}
        try:
            tx_dirs = glob.glob(os.path.join(iface_path, "queues/tx-*"))
            for tx_dir in tx_dirs:
                queue_name = os.path.basename(tx_dir)
                xps_cpus = self._read_file(os.path.join(tx_dir, "xps_cpus"), "")
                xps_rxqs = self._read_file(os.path.join(tx_dir, "xps_rxqs"), "")
                
                if xps_cpus or xps_rxqs:
                    result[queue_name] = {
                        "xps_cpus": xps_cpus,
                        "xps_rxqs": xps_rxqs,
                    }
        except OSError:
            pass
        return result

    def _get_rfs_config(self, iface_path: str) -> Dict[str, str]:
        """Get RFS configuration for an interface."""
        result = {}
        try:
            rx_dirs = glob.glob(os.path.join(iface_path, "queues/rx-*"))
            for rx_dir in rx_dirs:
                queue_name = os.path.basename(rx_dir)
                rps_flow_cnt = self._read_file(os.path.join(rx_dir, "rps_flow_cnt"), "")
                
                if rps_flow_cnt and rps_flow_cnt != "0":
                    result[queue_name] = {"rps_flow_cnt": rps_flow_cnt}
        except OSError:
            pass
        return result

    def _get_rss_info(self, interface: str) -> Dict[str, str]:
        """Get RSS information using ethtool."""
        result = {}
        
        # Get RSS ring information
        output = self._run_command(["ethtool", "-l", interface], "")
        if output:
            result["ring_info"] = output
            
        # Get RSS hash function
        output = self._run_command(["ethtool", "-x", interface], "")
        if output:
            result["rss_hash"] = output
            
        return result

    def _get_ring_buffer_info(self, interface: str) -> Dict[str, str]:
        """Get ring buffer information using ethtool."""
        result = {}
        
        # Get current ring buffer settings
        output = self._run_command(["ethtool", "-g", interface], "")
        if output:
            result["current"] = output
            
        return result

    def _get_coalescing_info(self, interface: str) -> Dict[str, str]:
        """Get interrupt coalescing information using ethtool."""
        result = {}
        
        # Get current coalescing settings
        output = self._run_command(["ethtool", "-c", interface], "")
        if output:
            result["current"] = output
            
        return result

    def _get_offload_info(self, interface: str) -> Dict[str, str]:
        """Get offload information using ethtool."""
        result = {}
        
        # Get current offload settings
        output = self._run_command(["ethtool", "-k", interface], "")
        if output:
            result["features"] = output
            
        return result

    def _get_bonding_info(self, iface_path: str) -> Dict[str, str]:
        """Get bonding information for an interface."""
        result = {}
        
        # Check if this is a bonding interface
        bonding_path = os.path.join(iface_path, "bonding")
        if os.path.exists(bonding_path):
            # Read bonding mode
            mode = self._read_file(os.path.join(bonding_path, "mode"), "")
            if mode:
                result["mode"] = mode
                
            # Read LACP settings
            lacp_rate = self._read_file(os.path.join(bonding_path, "lacp_rate"), "")
            if lacp_rate:
                result["lacp_rate"] = lacp_rate
                
            # Read mii monitoring
            miimon = self._read_file(os.path.join(bonding_path, "miimon"), "")
            if miimon:
                result["miimon"] = miimon
                
            # Read slaves
            slaves = self._read_file(os.path.join(bonding_path, "slaves"), "")
            if slaves:
                result["slaves"] = slaves
                
        return result

    def _get_interrupt_info(self) -> Dict[str, Any]:
        """Get interrupt and IRQ affinity information."""
        result = {}
        
        # Read /proc/interrupts to get interrupt counts
        interrupts = self._read_file("/proc/interrupts", "")
        if interrupts:
            result["interrupts"] = self._parse_interrupts(interrupts)
            
        # Get IRQ affinity settings
        result["irq_affinity"] = self._get_irq_affinity()
        
        return result

    def _parse_interrupts(self, content: str) -> Dict[str, Any]:
        """Parse /proc/interrupts content."""
        result = {"network_irqs": []}
        
        lines = content.split('\n')
        if not lines:
            return result
            
        # First line contains CPU column headers
        header = lines[0].strip().split()
        cpu_count = len([col for col in header if col.startswith('CPU')])
        result["cpu_count"] = cpu_count
        
        # Parse network-related interrupts
        for line in lines[1:]:
            if not line.strip():
                continue
                
            parts = line.strip().split()
            if len(parts) < cpu_count + 3:  # IRQ + CPUs + type + device
                continue
                
            irq_num = parts[0].rstrip(':')
            irq_type = parts[cpu_count + 1] if len(parts) > cpu_count + 1 else ""
            device = ' '.join(parts[cpu_count + 2:]) if len(parts) > cpu_count + 2 else ""
            
            # Check if this is a network-related interrupt
            if any(keyword in device.lower() for keyword in ['eth', 'ens', 'enp', 'mlx', 'ixgbe', 'i40e', 'ice']):
                result["network_irqs"].append({
                    "irq": irq_num,
                    "type": irq_type,
                    "device": device,
                    "counts": parts[1:cpu_count + 1]
                })
                
        return result

    def _get_irq_affinity(self) -> Dict[str, str]:
        """Get IRQ affinity settings."""
        result = {}
        
        try:
            irq_dirs = glob.glob("/proc/irq/[0-9]*")
            for irq_dir in irq_dirs:
                irq_num = os.path.basename(irq_dir)
                affinity = self._read_file(os.path.join(irq_dir, "smp_affinity"), "")
                if affinity:
                    result[irq_num] = affinity
        except OSError:
            pass
            
        return result

    def _get_conntrack_info(self) -> Dict[str, str]:
        """Get connection tracking information."""
        result = {}
        
        # Get current conntrack count
        count = self._read_file("/proc/sys/net/netfilter/nf_conntrack_count", "")
        if count:
            result["nf_conntrack_count"] = count
            
        # Get conntrack hash size
        hashsize = self._read_file("/sys/module/nf_conntrack/parameters/hashsize", "")
        if hashsize:
            result["nf_conntrack_hashsize"] = hashsize
            
        return result
