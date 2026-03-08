"""Linux network bonding information collector."""

import glob
import os
from typing import Any, Dict, List

from infra_auditor.collectors.base import BaseCollector


class BondingCollector(BaseCollector):
    """Collect Linux network bonding configuration and status."""

    def collect(self) -> Dict[str, Any]:
        """Collect bonding information."""
        return {
            "bonds": self._get_bonds(),
            "bonding_module": self._get_bonding_module_info(),
        }

    def _get_bonds(self) -> List[Dict[str, Any]]:
        """Get information about all bond interfaces."""
        bonds = []
        
        # Find all bond interfaces
        bond_dirs = glob.glob("/sys/class/net/bond*")
        
        for bond_dir in bond_dirs:
            bond_name = os.path.basename(bond_dir)
            bond_info = self._get_bond_details(bond_name, bond_dir)
            if bond_info:
                bonds.append(bond_info)
        
        # Also check /proc/net/bonding for any additional info
        proc_bonding_dir = "/proc/net/bonding"
        if os.path.exists(proc_bonding_dir):
            proc_bonds = []
            try:
                proc_bond_files = os.listdir(proc_bonding_dir)
                for bond_file in proc_bond_files:
                    bond_proc_info = self._read_file(
                        os.path.join(proc_bonding_dir, bond_file)
                    )
                    if bond_proc_info:
                        proc_bonds.append({
                            "name": bond_file,
                            "proc_info": bond_proc_info
                        })
            except (OSError, PermissionError):
                pass
            
            # Merge proc info with sys info
            for bond in bonds:
                for proc_bond in proc_bonds:
                    if bond["name"] == proc_bond["name"]:
                        bond["proc_info"] = proc_bond["proc_info"]
                        break
        
        return bonds

    def _get_bond_details(self, bond_name: str, bond_dir: str) -> Dict[str, Any]:
        """Get detailed information about a specific bond interface."""
        bond_info: Dict[str, Any] = {"name": bond_name}
        
        bonding_dir = os.path.join(bond_dir, "bonding")
        if not os.path.exists(bonding_dir):
            return bond_info
        
        # Basic bond configuration
        bond_info.update({
            "mode": self._read_file(os.path.join(bonding_dir, "mode"), "unknown"),
            "active_slave": self._read_file(os.path.join(bonding_dir, "active_slave"), ""),
            "miimon": self._read_file(os.path.join(bonding_dir, "miimon"), "0"),
            "updelay": self._read_file(os.path.join(bonding_dir, "updelay"), "0"),
            "downdelay": self._read_file(os.path.join(bonding_dir, "downdelay"), "0"),
            "use_carrier": self._read_file(os.path.join(bonding_dir, "use_carrier"), "1"),
            "primary": self._read_file(os.path.join(bonding_dir, "primary"), ""),
            "primary_reselect": self._read_file(os.path.join(bonding_dir, "primary_reselect"), "always"),
            "fail_over_mac": self._read_file(os.path.join(bonding_dir, "fail_over_mac"), "none"),
        })

        # Parse mode to get mode name and number
        mode_info = bond_info["mode"]
        if mode_info and mode_info != "unknown":
            # Format is typically "balance-rr 0" or "802.3ad 4"
            bond_info["mode_parsed"] = self._parse_bond_mode(mode_info)

        # LACP specific settings
        if "802.3ad" in bond_info["mode"] or "4" in bond_info["mode"]:
            bond_info.update({
                "lacp_rate": self._read_file(os.path.join(bonding_dir, "lacp_rate"), "slow"),
                "xmit_hash_policy": self._read_file(
                    os.path.join(bonding_dir, "xmit_hash_policy"), "layer2"
                ),
                "ad_select": self._read_file(os.path.join(bonding_dir, "ad_select"), "stable"),
                "ad_actor_sys_prio": self._read_file(
                    os.path.join(bonding_dir, "ad_actor_sys_prio"), "65535"
                ),
                "ad_user_port_key": self._read_file(
                    os.path.join(bonding_dir, "ad_user_port_key"), "0"
                ),
            })

        # ARP monitoring (alternative to MII)
        bond_info.update({
            "arp_interval": self._read_file(os.path.join(bonding_dir, "arp_interval"), "0"),
            "arp_ip_target": self._read_file(os.path.join(bonding_dir, "arp_ip_target"), ""),
            "arp_validate": self._read_file(os.path.join(bonding_dir, "arp_validate"), "none"),
            "arp_all_targets": self._read_file(os.path.join(bonding_dir, "arp_all_targets"), "any"),
        })

        # Get slave interfaces
        slaves_info = self._get_slave_interfaces(bond_name, bonding_dir)
        bond_info["slaves"] = slaves_info

        # Get network interface details
        bond_info.update(self._get_interface_details(bond_dir))

        return bond_info

    def _parse_bond_mode(self, mode_string: str) -> Dict[str, str]:
        """Parse bond mode string to extract mode name and number."""
        parts = mode_string.strip().split()
        mode_info = {"raw": mode_string}
        
        if len(parts) >= 2:
            mode_info["name"] = parts[0]
            mode_info["number"] = parts[1]
        elif len(parts) == 1:
            # Sometimes only mode name or number is shown
            if parts[0].isdigit():
                mode_info["number"] = parts[0]
                # Map numbers to names
                mode_map = {
                    "0": "balance-rr",
                    "1": "active-backup", 
                    "2": "balance-xor",
                    "3": "broadcast",
                    "4": "802.3ad",
                    "5": "balance-tlb",
                    "6": "balance-alb"
                }
                mode_info["name"] = mode_map.get(parts[0], "unknown")
            else:
                mode_info["name"] = parts[0]
        
        return mode_info

    def _get_slave_interfaces(self, bond_name: str, bonding_dir: str) -> List[Dict[str, Any]]:
        """Get information about slave interfaces in the bond."""
        slaves = []
        
        # Get list of slave interfaces
        slaves_list = self._read_file(os.path.join(bonding_dir, "slaves"), "")
        if not slaves_list:
            return slaves
        
        slave_names = slaves_list.split()
        
        for slave_name in slave_names:
            slave_info: Dict[str, Any] = {"name": slave_name}
            
            # Get slave-specific details
            slave_dir = f"/sys/class/net/{slave_name}"
            if os.path.exists(slave_dir):
                slave_info.update(self._get_interface_details(slave_dir))
                
                # Slave state in bond
                slave_state_file = f"/sys/class/net/{bond_name}/slave_{slave_name}/slave_state"
                if os.path.exists(slave_state_file):
                    slave_info["slave_state"] = self._read_file(slave_state_file, "unknown")

                # MII status
                mii_status_file = f"/sys/class/net/{bond_name}/slave_{slave_name}/mii_status"
                if os.path.exists(mii_status_file):
                    slave_info["mii_status"] = self._read_file(mii_status_file, "unknown")

                # Link failure count
                link_failure_file = f"/sys/class/net/{bond_name}/slave_{slave_name}/link_failure_count"
                if os.path.exists(link_failure_file):
                    slave_info["link_failure_count"] = self._read_file(link_failure_file, "0")

            slaves.append(slave_info)
        
        return slaves

    def _get_interface_details(self, iface_dir: str) -> Dict[str, Any]:
        """Get basic network interface details."""
        details: Dict[str, Any] = {}
        
        # MTU
        mtu = self._read_file(os.path.join(iface_dir, "mtu"), "")
        if mtu:
            try:
                details["mtu"] = int(mtu)
            except ValueError:
                details["mtu"] = mtu
        
        # Speed (for physical interfaces)
        speed = self._read_file(os.path.join(iface_dir, "speed"), "")
        if speed and speed != "-1":
            try:
                details["speed_mbps"] = int(speed)
            except ValueError:
                details["speed_mbps"] = speed
        
        # Duplex
        duplex = self._read_file(os.path.join(iface_dir, "duplex"), "")
        if duplex:
            details["duplex"] = duplex
        
        # Operational state
        operstate = self._read_file(os.path.join(iface_dir, "operstate"), "")
        if operstate:
            details["operstate"] = operstate
        
        # Carrier state
        carrier = self._read_file(os.path.join(iface_dir, "carrier"), "")
        if carrier:
            details["carrier"] = carrier
        
        # MAC address
        address = self._read_file(os.path.join(iface_dir, "address"), "")
        if address:
            details["mac_address"] = address
        
        # Driver info
        device_dir = os.path.join(iface_dir, "device")
        if os.path.exists(device_dir):
            # Try to get driver name
            try:
                driver_link = os.readlink(os.path.join(device_dir, "driver"))
                details["driver"] = os.path.basename(driver_link)
            except (OSError, FileNotFoundError):
                pass
            
            # PCI device info if available
            pci_vendor = self._read_file(os.path.join(device_dir, "vendor"), "")
            pci_device = self._read_file(os.path.join(device_dir, "device"), "")
            if pci_vendor and pci_device:
                details["pci_vendor"] = pci_vendor
                details["pci_device"] = pci_device
        
        return details

    def _get_bonding_module_info(self) -> Dict[str, Any]:
        """Get Linux bonding module information."""
        module_info: Dict[str, Any] = {}
        
        # Check if bonding module is loaded
        modules_output = self._run_command(["lsmod"])
        bonding_loaded = "bonding" in modules_output
        module_info["module_loaded"] = bonding_loaded
        
        if bonding_loaded:
            # Get module parameters
            bonding_params_dir = "/sys/module/bonding/parameters"
            if os.path.exists(bonding_params_dir):
                params = {}
                try:
                    param_files = os.listdir(bonding_params_dir)
                    for param_file in param_files:
                        param_value = self._read_file(
                            os.path.join(bonding_params_dir, param_file), ""
                        )
                        params[param_file] = param_value
                except (OSError, PermissionError):
                    pass
                module_info["parameters"] = params
            
            # Get module version info
            modinfo_output = self._run_command(["modinfo", "bonding"])
            module_info["modinfo"] = modinfo_output
        
        return module_info