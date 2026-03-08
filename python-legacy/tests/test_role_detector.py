"""Tests for role detector."""

import pytest

from infra_auditor.utils.role_detector import VALID_ROLES, detect_role


class TestRoleDetector:
    def test_detect_compute(self):
        data = {
            "services": {
                "libvirtd": "active",
                "qemu-kvm": "active",
            },
            "listening_ports": [{"address": "0.0.0.0:16509", "port": "16509"}],
            "loaded_modules": ["kvm", "kvm_intel", "vhost_net"],
        }
        result = detect_role(data)
        assert result["role"] == "compute"
        assert result["confidence"] > 0.5
        assert result["method"] == "auto"

    def test_detect_control(self):
        data = {
            "services": {
                "etcd": "active",
                "kube-apiserver": "active",
                "kube-scheduler": "active",
            },
            "listening_ports": [
                {"address": "0.0.0.0:6443", "port": "6443"},
                {"address": "0.0.0.0:2379", "port": "2379"},
            ],
            "loaded_modules": [],
        }
        result = detect_role(data)
        assert result["role"] == "control"
        assert result["confidence"] > 0.5

    def test_detect_network(self):
        data = {
            "services": {"haproxy": "active", "keepalived": "active"},
            "listening_ports": [
                {"address": "0.0.0.0:80", "port": "80"},
                {"address": "0.0.0.0:443", "port": "443"},
            ],
            "loaded_modules": ["nf_conntrack", "bonding"],
        }
        result = detect_role(data)
        assert result["role"] == "network"

    def test_detect_storage_ceph(self):
        data = {
            "services": {"ceph-osd": "active", "ceph-mon": "active"},
            "listening_ports": [],
            "loaded_modules": ["ceph", "rbd"],
        }
        result = detect_role(data)
        assert result["role"] == "storage-ceph"

    def test_detect_storage_s3(self):
        data = {
            "services": {"minio": "active"},
            "listening_ports": [{"address": "0.0.0.0:9000", "port": "9000"}],
            "loaded_modules": [],
        }
        result = detect_role(data)
        assert result["role"] == "storage-s3"

    def test_detect_unknown(self):
        data = {
            "services": {},
            "listening_ports": [],
            "loaded_modules": [],
        }
        result = detect_role(data)
        assert result["role"] == "unknown"
        assert result["confidence"] == 0.0

    def test_evidence_included(self):
        data = {
            "services": {"libvirtd": "active"},
            "listening_ports": [],
            "loaded_modules": ["kvm"],
        }
        result = detect_role(data)
        assert "evidence" in result
        assert len(result["evidence"]) > 0

    def test_valid_roles_constant(self):
        assert "control" in VALID_ROLES
        assert "compute" in VALID_ROLES
        assert "network" in VALID_ROLES
        assert "storage-ceph" in VALID_ROLES
        assert "storage-s3" in VALID_ROLES
