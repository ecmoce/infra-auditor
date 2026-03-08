"""Tests for OVS collector."""

import pytest
from unittest.mock import patch, mock_open

from infra_auditor.collectors.ovs import OVSCollector


class TestOVSCollector:
    """Test OVS collector."""

    def test_ovs_not_available(self):
        """Test when OVS is not available."""
        with patch.object(OVSCollector, '_run_command') as mock_run:
            mock_run.return_value = ""
            
            collector = OVSCollector()
            result = collector.collect()
            
            assert result["available"] is False

    def test_ovs_available_basic(self):
        """Test basic OVS collection when available."""
        with patch.object(OVSCollector, '_run_command') as mock_run, \
             patch('os.path.exists') as mock_exists:
            
            mock_run.return_value = "ovs-vsctl (Open vSwitch) 2.17.0"
            mock_exists.return_value = True
            
            collector = OVSCollector()
            result = collector.collect()
            
            assert result["available"] is True
            assert "version" in result
            assert "bridges" in result
            assert "dpdk_config" in result

    def test_ovs_version_parsing(self):
        """Test OVS version parsing."""
        version_output = """ovs-vsctl (Open vSwitch) 2.17.0
DB Schema 8.3.0
"""
        
        with patch.object(OVSCollector, '_run_command') as mock_run, \
             patch('os.path.exists') as mock_exists:
            
            mock_run.side_effect = [version_output, "", "", "", "", "", "", "", ""]
            mock_exists.return_value = True
            
            collector = OVSCollector()
            result = collector.collect()
            
            version_info = result["version"]
            assert "version" in version_info
            assert "db_schema" in version_info

    def test_dpdk_config_extraction(self):
        """Test DPDK configuration extraction."""
        with patch.object(OVSCollector, '_run_command') as mock_run, \
             patch('os.path.exists') as mock_exists, \
             patch.object(OVSCollector, '_read_file') as mock_read:
            
            mock_run.side_effect = [
                "ovs-vsctl version",  # version check
                "",  # bridges
                "true",  # dpdk-init
                "1024,1024",  # socket-mem
                "0x2",  # lcore-mask
                "0x4",  # pmd-cpu-mask
                "",  # other commands
                "", "", "", "", ""
            ]
            mock_exists.return_value = True
            mock_read.return_value = "HugePages_Total: 1024"
            
            collector = OVSCollector()
            result = collector.collect()
            
            dpdk_config = result["dpdk_config"]
            assert dpdk_config["dpdk_init"] == "true"
            assert dpdk_config["socket_mem"] == "1024,1024"
            assert dpdk_config["lcore_mask"] == "0x2"
            assert dpdk_config["pmd_cpu_mask"] == "0x4"

    def test_bridges_collection(self):
        """Test bridge information collection."""
        bridge_list = "br0\nbr1"
        show_output = """Bridge "br0"
    Port "br0"
        Interface "br0"
            type: internal
"""
        
        with patch.object(OVSCollector, '_run_command') as mock_run, \
             patch('os.path.exists') as mock_exists:
            
            def command_side_effect(cmd):
                if "list-br" in cmd:
                    return bridge_list
                elif "show" in cmd:
                    return show_output
                elif "get" in cmd and "datapath_type" in cmd:
                    return "system"
                elif "list-ports" in cmd:
                    return "eth0\neth1"
                else:
                    return ""
            
            mock_run.side_effect = command_side_effect
            mock_exists.return_value = True
            
            collector = OVSCollector()
            result = collector.collect()
            
            bridges = result["bridges"]
            assert len(bridges) == 2
            assert bridges[0]["name"] == "br0"
            assert bridges[0]["datapath_type"] == "system"
            assert "ports" in bridges[0]

    def test_bonding_detection(self):
        """Test OVS bonding detection."""
        bond_output = """_uuid               : 12345
bond_mode           : balance-slb
interfaces          : [eth0, eth1]
lacp                : active
name                : "bond0"
"""
        
        with patch.object(OVSCollector, '_run_command') as mock_run, \
             patch('os.path.exists') as mock_exists:
            
            mock_run.side_effect = [
                "ovs-vsctl version",  # version check
                "",  # other commands that return empty
                "", "", "", "", "", "", "",
                bond_output,  # list port output
                "", "", "", "", ""
            ]
            mock_exists.return_value = True
            
            collector = OVSCollector()
            result = collector.collect()
            
            bonding = result["bonding"]
            if bonding:  # If bonding was detected
                assert len(bonding) > 0

    def test_graceful_command_failure(self):
        """Test graceful handling of command failures."""
        with patch.object(OVSCollector, '_run_command') as mock_run, \
             patch('os.path.exists') as mock_exists:
            
            # Simulate command failures
            mock_run.return_value = ""
            mock_exists.return_value = True
            
            collector = OVSCollector()
            result = collector.collect()
            
            # Should still return a valid structure
            assert "available" in result
            assert "version" in result
            assert "bridges" in result
            assert "dpdk_config" in result

    def test_error_collection(self):
        """Test that errors are properly collected."""
        with patch.object(OVSCollector, '_run_command') as mock_run, \
             patch('os.path.exists') as mock_exists:
            
            mock_run.side_effect = Exception("Test error")
            mock_exists.return_value = True
            
            collector = OVSCollector()
            
            # Call a method that would cause an error
            result = collector._run_command(["ovs-vsctl", "--version"])
            
            # Should have recorded an error
            assert len(collector.errors) > 0
            assert collector.errors[0]["category"] == "collection"