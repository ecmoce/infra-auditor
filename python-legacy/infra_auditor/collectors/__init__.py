"""System information collectors."""

from infra_auditor.collectors.cpu import CPUCollector
from infra_auditor.collectors.memory import MemoryCollector
from infra_auditor.collectors.network import NetworkCollector
from infra_auditor.collectors.storage import StorageCollector
from infra_auditor.collectors.kernel import KernelCollector
from infra_auditor.collectors.service import ServiceCollector

__all__ = [
    "CPUCollector",
    "MemoryCollector",
    "NetworkCollector",
    "StorageCollector",
    "KernelCollector",
    "ServiceCollector",
]
