"""Report generation following docs/REPORT-SCHEMA.md."""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import infra_auditor
from infra_auditor.collectors.cpu import CPUCollector
from infra_auditor.collectors.kernel import KernelCollector
from infra_auditor.collectors.memory import MemoryCollector
from infra_auditor.collectors.network import NetworkCollector
from infra_auditor.collectors.service import ServiceCollector
from infra_auditor.collectors.storage import StorageCollector
from infra_auditor.rules.engine import RulesEngine
from infra_auditor.utils.role_detector import detect_role
from infra_auditor.utils.system import get_server_info


class Report:
    """Collect system info, evaluate rules, and generate a JSON report."""

    def __init__(self, role: Optional[str] = None):
        self.role = role
        self.collected_data: Dict[str, Any] = {}
        self.errors: list = []
        self.scan_id = str(uuid.uuid4())
        self.start_time: Optional[float] = None
        self.role_detection: Dict[str, Any] = {}

    def collect(self) -> None:
        """Run all collectors."""
        self.start_time = time.time()

        collectors = [
            ("cpu", CPUCollector()),
            ("memory", MemoryCollector()),
            ("network", NetworkCollector()),
            ("storage", StorageCollector()),
            ("kernel", KernelCollector()),
            ("service", ServiceCollector()),
        ]

        for name, collector in collectors:
            try:
                self.collected_data[name] = collector.collect()
                self.errors.extend(collector.errors)
            except Exception as e:
                self.errors.append(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "category": "collection",
                        "item": name,
                        "error_code": "COLLECTOR_FAILED",
                        "message": str(e),
                        "severity": "error",
                    }
                )

        # Detect role if auto
        if self.role is None or self.role == "auto":
            self.role_detection = detect_role(
                self.collected_data.get("service")
            )
            self.role = self.role_detection.get("role", "unknown")
        else:
            self.role_detection = {
                "role": self.role,
                "confidence": 1.0,
                "method": "manual",
            }

    def evaluate(self) -> Dict[str, Any]:
        """Run rules engine against collected data."""
        engine = RulesEngine(self.role)
        return engine.evaluate(self.collected_data)

    def generate(self) -> Dict[str, Any]:
        """Generate full report following REPORT-SCHEMA.md."""
        self.collect()
        evaluation = self.evaluate()
        duration = time.time() - (self.start_time or time.time())

        report = {
            "metadata": {
                "version": "1.0.0",
                "agent_version": infra_auditor.__version__,
                "scan_id": self.scan_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "scan_duration_seconds": round(duration, 2),
                "scan_type": "full",
            },
            "server_info": get_server_info(self.role, self.role_detection),
            "hardware_info": {
                "cpu": self.collected_data.get("cpu", {}),
                "memory": {
                    "total_gb": self.collected_data.get("memory", {}).get(
                        "total_gb", 0
                    ),
                },
                "network": {
                    "interfaces": self.collected_data.get("network", {}).get(
                        "interfaces", []
                    ),
                },
                "storage": {
                    "devices": self.collected_data.get("storage", {}).get(
                        "devices", []
                    ),
                },
            },
            "scan_results": evaluation.get("scan_results", {}),
            "compliance": evaluation.get("compliance", {}),
            "errors": self.errors,
        }

        return report

    def to_json(self, indent: int = 2) -> str:
        """Generate report as JSON string."""
        return json.dumps(self.generate(), indent=indent, ensure_ascii=False)

    def save(self, path: str, indent: int = 2) -> None:
        """Generate and save report to file."""
        with open(path, "w") as f:
            f.write(self.to_json(indent=indent))
