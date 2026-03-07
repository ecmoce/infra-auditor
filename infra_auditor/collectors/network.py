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
        ]
        result = {}
        for key in keys:
            val = self._read_sysctl(key, "")
            if val:
                result[key] = val
        return result
