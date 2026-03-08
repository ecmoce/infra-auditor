"""Tests for bonding collector."""

import pytest
from unittest.mock import patch, mock_open
import tempfile
import os

from infra_auditor.collectors.bonding import BondingCollector


class TestBondingCollector:
    """Test bonding collector."""

    def test_no_bonds_available(self):
        """Test when no bonds are available."""
        with patch('glob.glob') as mock_glob:
            mock_glob.return_value = []
            
            collector = BondingCollector()
            result = collector.collect()
            
            assert "bonds" in result
            assert len(result["bonds"]) == 0

    def test_single_bond_collection(self):
        """Test collection of a single bond interface."""
        with patch('glob.glob') as mock_glob, \
             patch('os.path.exists') as mock_exists, \
             patch.object(BondingCollector, '_read_file') as mock_read:
            
            mock_glob.return_value = ["/sys/class/net/bond0"]
            mock_exists.return_value = True
            
            def read_file_side_effect(path, default=""):
                if "mode" in path:
                    return "802.3ad 4"
                elif "active_slave" in path:
                    return "eth0"
                elif "miimon" in path:
                    return "100"
                elif "lacp_rate" in path:
                    return "fast"
                elif "xmit_hash_policy" in path:
                    return "layer3+4"
                elif "slaves" in path:
                    return "eth0 eth1"
                elif "mtu" in path:
                    return "1500"
                elif "speed" in path:
                    return "1000"
                elif "operstate" in path:
                    return "up"
                else:
                    return default
            
            mock_read.side_effect = read_file_side_effect
            
            collector = BondingCollector()
            result = collector.collect()
            
            bonds = result["bonds"]
            assert len(bonds) == 1
            
            bond = bonds[0]
            assert bond["name"] == "bond0"
            assert bond["mode"] == "802.3ad 4"
            assert bond["active_slave"] == "eth0"
            assert bond["miimon"] == "100"
            assert bond["lacp_rate"] == "fast"
            assert bond["xmit_hash_policy"] == "layer3+4"
            assert len(bond["slaves"]) == 2

    def test_bond_mode_parsing(self):
        """Test bond mode parsing functionality."""
        collector = BondingCollector()
        
        # Test full mode string
        mode_info = collector._parse_bond_mode("802.3ad 4")
        assert mode_info["name"] == "802.3ad"
        assert mode_info["number"] == "4"
        
        # Test number only
        mode_info = collector._parse_bond_mode("4")
        assert mode_info["name"] == "802.3ad"
        assert mode_info["number"] == "4"
        
        # Test name only
        mode_info = collector._parse_bond_mode("balance-rr")
        assert mode_info["name"] == "balance-rr"

    def test_slave_interface_details(self):
        """Test slave interface detail collection."""
        with patch('glob.glob') as mock_glob, \
             patch('os.path.exists') as mock_exists, \
             patch.object(BondingCollector, '_read_file') as mock_read:
            
            mock_glob.return_value = ["/sys/class/net/bond0"]
            
            def exists_side_effect(path):
                return True  # All paths exist for this test
            
            def read_file_side_effect(path, default=""):
                if "bond0/bonding" in path:
                    if "mode" in path:
                        return "802.3ad 4"
                    elif "slaves" in path:
                        return "eth0 eth1"
                elif "eth0" in path or "eth1" in path:
                    if "slave_state" in path:
                        return "active"
                    elif "mii_status" in path:
                        return "up"
                    elif "link_failure_count" in path:
                        return "0"
                    elif "mtu" in path:
                        return "1500"
                    elif "speed" in path:
                        return "1000"
                    elif "operstate" in path:
                        return "up"
                    elif "address" in path:
                        return "00:11:22:33:44:55"
                return default
            
            mock_exists.side_effect = exists_side_effect
            mock_read.side_effect = read_file_side_effect
            
            collector = BondingCollector()
            result = collector.collect()
            
            bonds = result["bonds"]
            assert len(bonds) == 1
            
            slaves = bonds[0]["slaves"]
            assert len(slaves) == 2
            
            slave = slaves[0]
            assert slave["name"] == "eth0"
            assert slave["slave_state"] == "active"
            assert slave["mii_status"] == "up"
            assert slave["link_failure_count"] == "0"
            assert slave["mtu"] == 1500
            assert slave["speed_mbps"] == 1000
            assert slave["operstate"] == "up"
            assert slave["mac_address"] == "00:11:22:33:44:55"

    def test_bonding_module_info(self):
        """Test bonding module information collection."""
        with patch.object(BondingCollector, '_run_command') as mock_run, \
             patch('os.path.exists') as mock_exists, \
             patch('os.listdir') as mock_listdir, \
             patch.object(BondingCollector, '_read_file') as mock_read:
            
            mock_run.side_effect = [
                "bonding                123456  0",  # lsmod output
                "filename: /lib/modules/5.4.0/kernel/drivers/net/bonding/bonding.ko\nversion: 3.7.1"  # modinfo
            ]
            mock_exists.return_value = True
            mock_listdir.return_value = ["mode", "miimon", "lacp_rate"]
            mock_read.side_effect = ["balance-rr", "100", "slow"]
            
            collector = BondingCollector()
            result = collector.collect()
            
            module_info = result["bonding_module"]
            assert module_info["module_loaded"] is True
            assert "parameters" in module_info
            assert module_info["parameters"]["mode"] == "balance-rr"
            assert module_info["parameters"]["miimon"] == "100"
            assert module_info["parameters"]["lacp_rate"] == "slow"

    def test_proc_bonding_info_merge(self):
        """Test merging of /proc/net/bonding information."""
        proc_bonding_content = """Ethernet Channel Bonding Driver: v3.7.1
Bonding Mode: IEEE 802.3ad Dynamic link aggregation
Transmit Hash Policy: layer3+4 (1)
MII Status: up
MII Polling Interval (ms): 100
Up Delay (ms): 0
Down Delay (ms): 0

Slave Interface: eth0
MII Status: up
Speed: 1000 Mbps
Duplex: full
Link Failure Count: 0
Permanent HW addr: 00:11:22:33:44:55
"""
        
        with patch('glob.glob') as mock_glob, \
             patch('os.path.exists') as mock_exists, \
             patch('os.listdir') as mock_listdir, \
             patch.object(BondingCollector, '_read_file') as mock_read:
            
            mock_glob.return_value = ["/sys/class/net/bond0"]
            
            def exists_side_effect(path):
                if "/proc/net/bonding" in path:
                    return True
                elif "bonding" in path:
                    return True
                return False
            
            def read_file_side_effect(path, default=""):
                if "/proc/net/bonding/bond0" in path:
                    return proc_bonding_content
                elif "mode" in path:
                    return "802.3ad 4"
                elif "slaves" in path:
                    return "eth0"
                return default
            
            mock_exists.side_effect = exists_side_effect
            mock_listdir.return_value = ["bond0"]
            mock_read.side_effect = read_file_side_effect
            
            collector = BondingCollector()
            result = collector.collect()
            
            bonds = result["bonds"]
            assert len(bonds) == 1
            assert "proc_info" in bonds[0]
            assert "Bonding Mode: IEEE 802.3ad" in bonds[0]["proc_info"]

    def test_multiple_bonds(self):
        """Test handling of multiple bond interfaces."""
        with patch('glob.glob') as mock_glob, \
             patch('os.path.exists') as mock_exists, \
             patch.object(BondingCollector, '_read_file') as mock_read:
            
            mock_glob.return_value = ["/sys/class/net/bond0", "/sys/class/net/bond1"]
            mock_exists.return_value = True
            
            def read_file_side_effect(path, default=""):
                if "bond0" in path and "mode" in path:
                    return "802.3ad 4"
                elif "bond1" in path and "mode" in path:
                    return "active-backup 1"
                elif "slaves" in path:
                    return "eth0 eth1"
                return default
            
            mock_read.side_effect = read_file_side_effect
            
            collector = BondingCollector()
            result = collector.collect()
            
            bonds = result["bonds"]
            assert len(bonds) == 2
            assert bonds[0]["name"] == "bond0"
            assert bonds[1]["name"] == "bond1"
            assert "802.3ad" in bonds[0]["mode"]
            assert "active-backup" in bonds[1]["mode"]

    def test_graceful_error_handling(self):
        """Test graceful handling of various error conditions."""
        with patch('glob.glob') as mock_glob:
            # Simulate glob failure
            mock_glob.side_effect = OSError("Permission denied")
            
            collector = BondingCollector()
            result = collector.collect()
            
            # Should still return valid structure
            assert "bonds" in result
            assert "bonding_module" in result

    def test_missing_bonding_directory(self):
        """Test handling when bonding directory doesn't exist."""
        with patch('glob.glob') as mock_glob, \
             patch('os.path.exists') as mock_exists:
            
            mock_glob.return_value = ["/sys/class/net/bond0"]
            mock_exists.return_value = False  # bonding directory doesn't exist
            
            collector = BondingCollector()
            result = collector.collect()
            
            bonds = result["bonds"]
            assert len(bonds) == 1
            assert bonds[0]["name"] == "bond0"
            # Should have minimal info when bonding directory missing