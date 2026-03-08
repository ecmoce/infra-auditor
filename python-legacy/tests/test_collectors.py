"""Tests for collectors using mocks."""

import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

from infra_auditor.collectors.base import BaseCollector
from infra_auditor.collectors.cpu import CPUCollector
from infra_auditor.collectors.kernel import KernelCollector
from infra_auditor.collectors.memory import MemoryCollector
from infra_auditor.collectors.network import NetworkCollector
from infra_auditor.collectors.service import ServiceCollector
from infra_auditor.collectors.storage import StorageCollector


class TestBaseCollector:
    def test_read_file_missing(self):
        c = BaseCollector()
        result = c._read_file("/nonexistent/path", "fallback")
        assert result == "fallback"
        assert len(c.errors) == 1

    def test_read_file_success(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        c = BaseCollector()
        assert c._read_file(str(f)) == "hello"
        assert len(c.errors) == 0

    def test_read_sysctl(self):
        c = BaseCollector()
        with patch.object(c, "_read_file", return_value="60"):
            result = c._read_sysctl("vm.swappiness")
            assert result == "60"

    def test_run_command_success(self):
        c = BaseCollector()
        result = c._run_command(["echo", "test"])
        assert result == "test"

    def test_run_command_failure(self):
        c = BaseCollector()
        result = c._run_command(["/nonexistent/binary"], default="nope")
        assert result == "nope"
        assert len(c.errors) == 1

    def test_record_error(self):
        c = BaseCollector()
        c._record_error("test", "item", "msg")
        assert len(c.errors) == 1
        assert c.errors[0]["category"] == "test"


class TestCPUCollector:
    CPUINFO = (
        "processor\t: 0\n"
        "model name\t: Intel Xeon Gold 6348\n"
        "physical id\t: 0\n"
        "cpu cores\t: 28\n"
        "\n"
        "processor\t: 1\n"
        "model name\t: Intel Xeon Gold 6348\n"
        "physical id\t: 0\n"
        "cpu cores\t: 28\n"
        "\n"
        "processor\t: 2\n"
        "model name\t: Intel Xeon Gold 6348\n"
        "physical id\t: 1\n"
        "cpu cores\t: 28\n"
    )

    def test_get_cpu_model(self):
        c = CPUCollector()
        with patch.object(c, "_read_file", return_value=self.CPUINFO):
            model = c._get_cpu_model()
            assert "Intel Xeon Gold 6348" in model

    def test_get_sockets(self):
        c = CPUCollector()
        with patch.object(c, "_read_file", return_value=self.CPUINFO):
            assert c._get_sockets() == 2

    def test_get_cores_per_socket(self):
        c = CPUCollector()
        with patch.object(c, "_read_file", return_value=self.CPUINFO):
            assert c._get_cores_per_socket() == 28

    @patch("glob.glob", return_value=[])
    def test_get_total_threads_fallback(self, mock_glob):
        c = CPUCollector()
        # Falls back to os.cpu_count()
        result = c._get_total_threads()
        assert result >= 1

    def test_collect_returns_dict(self):
        c = CPUCollector()
        with patch.object(c, "_read_file", return_value=self.CPUINFO):
            with patch("glob.glob", return_value=[]):
                data = c.collect()
                assert "model" in data
                assert "architecture" in data
                assert "governor" in data


class TestMemoryCollector:
    MEMINFO = (
        "MemTotal:       32946236 kB\n"
        "MemAvailable:   25000000 kB\n"
        "SwapTotal:       4194304 kB\n"
        "HugePages_Total:       0\n"
        "HugePages_Free:        0\n"
        "Hugepagesize:       2048 kB\n"
    )

    def test_parse_meminfo(self):
        c = MemoryCollector()
        with patch.object(c, "_read_file", return_value=self.MEMINFO):
            info = c._parse_meminfo()
            assert info["MemTotal"] == 32946236
            assert info["SwapTotal"] == 4194304

    def test_get_thp_status(self):
        c = MemoryCollector()
        with patch.object(
            c, "_read_file", return_value="always [madvise] never"
        ):
            assert c._get_thp_status() == "madvise"

    def test_get_thp_status_no_bracket(self):
        c = MemoryCollector()
        with patch.object(c, "_read_file", return_value="unknown"):
            assert c._get_thp_status() == "unknown"

    def test_collect(self):
        c = MemoryCollector()

        def fake_read(path, default=""):
            if "meminfo" in path:
                return self.MEMINFO
            if "transparent_hugepage" in path:
                return "always [madvise] never"
            return "42"

        with patch.object(c, "_read_file", side_effect=fake_read):
            data = c.collect()
            assert "total_gb" in data
            assert "swappiness" in data


class TestNetworkCollector:
    def test_get_network_sysctl(self):
        c = NetworkCollector()
        with patch.object(c, "_read_sysctl", return_value="65535"):
            data = c._get_network_sysctl()
            assert "net.core.somaxconn" in data

    @patch("glob.glob", return_value=[])
    def test_get_interfaces_empty(self, mock_glob):
        c = NetworkCollector()
        assert c._get_interfaces() == []


class TestStorageCollector:
    @patch("glob.glob", return_value=[])
    def test_get_block_devices_empty(self, mock_glob):
        c = StorageCollector()
        assert c._get_block_devices() == []

    def test_get_mounts(self):
        c = StorageCollector()
        mount_data = "/dev/sda1 / ext4 rw,relatime 0 0\nproc /proc proc rw 0 0"
        with patch.object(c, "_read_file", return_value=mount_data):
            mounts = c._get_mounts()
            assert len(mounts) == 1
            assert mounts[0]["device"] == "/dev/sda1"


class TestKernelCollector:
    def test_cmdline_params(self):
        c = KernelCollector()
        cmdline = "BOOT_IMAGE=... isolcpus=0,1 nohz_full=2-111 rcu_nocbs=0,1 ro"
        with patch.object(c, "_read_file", return_value=cmdline):
            params = c._get_cmdline_params()
            assert params["isolcpus"] == "0,1"
            assert params["nohz_full"] == "2-111"
            assert params["rcu_nocbs"] == "0,1"

    def test_collect(self):
        c = KernelCollector()
        with patch.object(c, "_read_sysctl", return_value="100000"):
            with patch.object(c, "_read_file", return_value=""):
                data = c.collect()
                assert "file_max" in data
                assert "cmdline" in data


class TestServiceCollector:
    def test_check_services(self):
        c = ServiceCollector()
        with patch.object(c, "_run_command", return_value="active"):
            services = c._check_services()
            assert all(v == "active" for v in services.values())

    def test_get_listening_ports(self):
        c = ServiceCollector()
        ss_output = (
            "State    Recv-Q   Send-Q     Local Address:Port\n"
            "LISTEN   0        128              0.0.0.0:6443\n"
            "LISTEN   0        128              0.0.0.0:2379\n"
        )
        with patch.object(c, "_run_command", return_value=ss_output):
            ports = c._get_listening_ports()
            assert len(ports) == 2
            assert ports[0]["port"] == "6443"

    def test_get_relevant_modules(self):
        c = ServiceCollector()
        lsmod_output = (
            "Module                  Size  Used by\n"
            "kvm_intel             364544  0\n"
            "kvm                   1003520  1 kvm_intel\n"
            "random_module          12345  0\n"
        )
        with patch.object(c, "_run_command", return_value=lsmod_output):
            mods = c._get_relevant_modules()
            assert "kvm_intel" in mods
            assert "kvm" in mods
            assert "random_module" not in mods
