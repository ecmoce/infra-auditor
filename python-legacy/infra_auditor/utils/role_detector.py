"""Automatic server role detection."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from infra_auditor.collectors.service import ServiceCollector

logger = logging.getLogger(__name__)

# Role detection scoring: (service_name, weight)
ROLE_INDICATORS: Dict[str, List[Tuple[str, int]]] = {
    "control": [
        ("etcd", 30),
        ("kube-apiserver", 30),
        ("kube-scheduler", 20),
        ("kube-controller-manager", 20),
    ],
    "compute": [
        ("libvirtd", 40),
        ("qemu-kvm", 30),
        ("nova-compute", 30),
    ],
    "network": [
        ("haproxy", 40),
        ("nginx", 30),
        ("keepalived", 30),
    ],
    "storage-ceph": [
        ("ceph-osd", 40),
        ("ceph-mon", 30),
        ("ceph-mgr", 30),
    ],
    "storage-s3": [
        ("minio", 50),
        ("radosgw", 50),
    ],
}

# Port-based detection as fallback
PORT_INDICATORS: Dict[str, List[Tuple[str, int]]] = {
    "control": [("6443", 30), ("2379", 25), ("10251", 15)],
    "compute": [("16509", 30), ("16514", 20)],
    "network": [("80", 15), ("443", 15)],
    "storage-s3": [("9000", 25)],
}

# Module-based detection
MODULE_INDICATORS: Dict[str, List[Tuple[str, int]]] = {
    "compute": [("kvm", 20), ("kvm_intel", 15), ("kvm_amd", 15), ("vhost_net", 10)],
    "storage-ceph": [("ceph", 20), ("rbd", 15)],
    "network": [("nf_conntrack", 10), ("bonding", 5)],
}

VALID_ROLES = [
    "control",
    "compute",
    "network",
    "storage-ceph",
    "storage-s3",
]


def detect_role(
    service_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Detect server role based on running services, ports, and modules.

    Returns a dict with:
        role: detected role name
        confidence: 0.0-1.0
        method: "auto"
        evidence: dict of what was found
    """
    if service_data is None:
        collector = ServiceCollector()
        service_data = collector.collect()

    services = service_data.get("services", {})
    ports = service_data.get("listening_ports", [])
    modules = service_data.get("loaded_modules", [])

    port_set = {p.get("port", "") for p in ports}

    scores: Dict[str, int] = {role: 0 for role in VALID_ROLES}
    evidence: Dict[str, List[str]] = {role: [] for role in VALID_ROLES}

    # Service-based scoring
    for role, indicators in ROLE_INDICATORS.items():
        for svc, weight in indicators:
            if services.get(svc) == "active":
                scores[role] += weight
                evidence[role].append(f"service:{svc}")

    # Port-based scoring
    for role, indicators in PORT_INDICATORS.items():
        for port, weight in indicators:
            if port in port_set:
                scores[role] += weight
                evidence[role].append(f"port:{port}")

    # Module-based scoring
    for role, indicators in MODULE_INDICATORS.items():
        for mod, weight in indicators:
            if mod in modules:
                scores[role] += weight
                evidence[role].append(f"module:{mod}")

    # Find best match
    best_role = max(scores, key=lambda r: scores[r])
    best_score = scores[best_role]

    if best_score == 0:
        return {
            "role": "unknown",
            "confidence": 0.0,
            "method": "auto",
            "evidence": {},
            "scores": scores,
        }

    # Normalize confidence (max possible ~100 per role)
    confidence = min(best_score / 100.0, 1.0)

    logger.info(
        "Detected role: %s (confidence: %.2f, score: %d)",
        best_role,
        confidence,
        best_score,
    )

    return {
        "role": best_role,
        "confidence": round(confidence, 2),
        "method": "auto",
        "evidence": {k: v for k, v in evidence.items() if v},
        "scores": scores,
    }
