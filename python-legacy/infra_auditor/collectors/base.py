"""Base collector class for system information gathering."""

import logging
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseCollector:
    """Base class for all system collectors."""

    def __init__(self):
        self.errors: List[Dict[str, Any]] = []

    def collect(self) -> Dict[str, Any]:
        """Collect system information. Override in subclasses."""
        raise NotImplementedError

    def _read_file(self, path: str, default: str = "") -> str:
        """Read a file and return its contents, or default on failure."""
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except (IOError, OSError, PermissionError) as e:
            self._record_error("collection", path, str(e))
            return default

    def _read_sysctl(self, key: str, default: str = "") -> str:
        """Read a sysctl value via /proc/sys path."""
        path = "/proc/sys/" + key.replace(".", "/")
        return self._read_file(path, default)

    def _run_command(
        self, cmd: List[str], default: str = "", timeout: int = 10
    ) -> str:
        """Run a command and return stdout, or default on failure."""
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=timeout,
            )
            return result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as e:
            self._record_error("collection", " ".join(cmd), str(e))
            return default

    def _record_error(
        self,
        category: str,
        item: str,
        message: str,
        severity: str = "warning",
    ) -> None:
        """Record a collection error."""
        from datetime import datetime, timezone

        self.errors.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "category": category,
                "item": item,
                "error_code": "COLLECTION_ERROR",
                "message": message,
                "severity": severity,
            }
        )
        logger.warning("Collection error [%s/%s]: %s", category, item, message)
