"""Service and process collector for role detection."""

from typing import Any, Dict, List

from infra_auditor.collectors.base import BaseCollector


class ServiceCollector(BaseCollector):
    """Collect running service and process information."""

    # Services to check, grouped by role
    ROLE_SERVICES = {
        "control": ["etcd", "kube-apiserver", "kube-scheduler", "kube-controller-manager"],
        "compute": ["libvirtd", "qemu-kvm", "nova-compute"],
        "network": ["haproxy", "nginx", "keepalived"],
        "storage-ceph": ["ceph-osd", "ceph-mon", "ceph-mgr"],
        "storage-s3": ["minio", "radosgw"],
    }

    def collect(self) -> Dict[str, Any]:
        """Collect service information."""
        return {
            "services": self._check_services(),
            "listening_ports": self._get_listening_ports(),
            "loaded_modules": self._get_relevant_modules(),
        }

    def _check_services(self) -> Dict[str, str]:
        """Check status of known services via systemctl."""
        all_services = set()
        for svc_list in self.ROLE_SERVICES.values():
            all_services.update(svc_list)

        results = {}
        for svc in sorted(all_services):
            status = self._run_command(
                ["systemctl", "is-active", svc], default="unknown"
            )
            results[svc] = status
        return results

    def _get_listening_ports(self) -> List[Dict[str, str]]:
        """Get listening TCP ports."""
        output = self._run_command(
            ["ss", "-tlnp"],
            default="",
        )
        ports = []
        for line in output.splitlines()[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 4:
                local_addr = parts[3]
                # Extract port from address like *:6443 or 0.0.0.0:6443
                if ":" in local_addr:
                    port = local_addr.rsplit(":", 1)[-1]
                    ports.append({"address": local_addr, "port": port})
        return ports

    def _get_relevant_modules(self) -> List[str]:
        """Get loaded kernel modules relevant to server roles."""
        interesting = [
            "kvm", "kvm_intel", "kvm_amd",
            "vhost_net", "tun", "bridge",
            "bonding", "8021q",
            "ceph", "rbd",
            "nf_conntrack",
        ]
        output = self._run_command(["lsmod"], default="")
        loaded = []
        for line in output.splitlines()[1:]:
            module_name = line.split()[0] if line.split() else ""
            if module_name in interesting:
                loaded.append(module_name)
        return loaded
