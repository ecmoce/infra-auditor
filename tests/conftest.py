"""Shared test fixtures."""

import pytest


@pytest.fixture
def mock_collected_data():
    """Sample collected data for testing rules engine."""
    return {
        "cpu": {
            "model": "Intel(R) Xeon(R) Gold 6348 CPU @ 2.60GHz",
            "architecture": "x86_64",
            "sockets": 2,
            "cores_per_socket": 28,
            "threads_per_core": 2,
            "total_cores": 56,
            "total_threads": 112,
            "numa_nodes": 2,
            "governor": "ondemand",
            "max_cstate": "9",
        },
        "memory": {
            "total_kb": 1073741824,
            "total_gb": 1024.0,
            "available_kb": 536870912,
            "swap_total_kb": 4194304,
            "hugepages_total": 0,
            "hugepages_free": 0,
            "hugepage_size_kb": 2048,
            "swappiness": "60",
            "dirty_ratio": "20",
            "dirty_background_ratio": "10",
            "overcommit_memory": "0",
            "transparent_hugepage": "always",
            "numa_balancing": "1",
            "zone_reclaim_mode": "1",
        },
        "network": {
            "interfaces": [
                {
                    "name": "ens1f0",
                    "speed_mbps": 100000,
                    "mtu": 1500,
                    "driver": "mlx5_core",
                    "operstate": "up",
                }
            ],
            "sysctl": {
                "net.core.somaxconn": "128",
                "net.core.netdev_max_backlog": "1000",
                "net.core.rmem_max": "212992",
                "net.core.wmem_max": "212992",
                "net.ipv4.tcp_congestion_control": "cubic",
                "net.ipv4.ip_local_port_range": "32768 60999",
                "net.ipv4.tcp_tw_reuse": "0",
                "net.ipv4.tcp_max_syn_backlog": "1024",
                "net.ipv4.tcp_rmem": "4096 131072 6291456",
                "net.ipv4.tcp_wmem": "4096 16384 4194304",
            },
        },
        "storage": {
            "devices": [
                {
                    "name": "/dev/nvme0n1",
                    "type": "nvme",
                    "rotational": False,
                    "scheduler": "none",
                    "read_ahead_kb": 128,
                    "nr_requests": 128,
                    "size_gb": 2000.0,
                }
            ],
            "mounts": [
                {
                    "device": "/dev/nvme0n1p1",
                    "mountpoint": "/",
                    "fstype": "xfs",
                    "options": "rw,relatime",
                }
            ],
        },
        "kernel": {
            "file_max": "100000",
            "pid_max": "32768",
            "threads_max": "256000",
            "cmdline": {},
        },
        "service": {
            "services": {
                "etcd": "inactive",
                "libvirtd": "active",
                "qemu-kvm": "active",
                "haproxy": "inactive",
                "ceph-osd": "inactive",
                "minio": "inactive",
            },
            "listening_ports": [
                {"address": "0.0.0.0:16509", "port": "16509"},
            ],
            "loaded_modules": ["kvm", "kvm_intel", "vhost_net"],
        },
    }


@pytest.fixture
def mock_compliant_data():
    """Sample data that passes most common rules."""
    return {
        "cpu": {
            "model": "Intel Xeon",
            "architecture": "x86_64",
            "sockets": 2,
            "cores_per_socket": 28,
            "threads_per_core": 2,
            "total_cores": 56,
            "total_threads": 112,
            "numa_nodes": 2,
            "governor": "performance",
            "max_cstate": "1",
        },
        "memory": {
            "total_kb": 1073741824,
            "total_gb": 1024.0,
            "available_kb": 536870912,
            "swap_total_kb": 4194304,
            "hugepages_total": 0,
            "hugepages_free": 0,
            "hugepage_size_kb": 2048,
            "swappiness": "1",
            "dirty_ratio": "15",
            "dirty_background_ratio": "5",
            "overcommit_memory": "1",
            "transparent_hugepage": "never",
            "numa_balancing": "0",
            "zone_reclaim_mode": "0",
        },
        "network": {
            "interfaces": [],
            "sysctl": {
                "net.core.somaxconn": "65535",
                "net.core.netdev_max_backlog": "5000",
                "net.core.rmem_max": "67108864",
                "net.core.wmem_max": "67108864",
                "net.ipv4.tcp_congestion_control": "bbr",
                "net.ipv4.ip_local_port_range": "10000 65535",
                "net.ipv4.tcp_tw_reuse": "1",
                "net.ipv4.tcp_max_syn_backlog": "65535",
            },
        },
        "storage": {"devices": [], "mounts": []},
        "kernel": {
            "file_max": "2000000",
            "pid_max": "4194304",
            "threads_max": "2000000",
            "cmdline": {},
        },
        "service": {
            "services": {},
            "listening_ports": [],
            "loaded_modules": [],
        },
    }
