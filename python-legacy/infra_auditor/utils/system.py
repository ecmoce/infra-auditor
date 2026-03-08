"""System utility functions."""

import os
import platform
import socket
from typing import Dict


def get_server_info(role: str, role_detection: Dict) -> Dict:
    """Get basic server information."""
    return {
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
        "role": role,
        "role_detection": role_detection,
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "distribution": _get_distribution(),
        },
        "environment": os.environ.get(
            "INFRA_AUDITOR_ENV", "production"
        ),
    }


def _get_distribution() -> Dict:
    """Get Linux distribution info."""
    info = {"name": "unknown", "version": "unknown", "id": "unknown"}

    # Try /etc/os-release (modern Linux)
    try:
        with open("/etc/os-release", "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("NAME="):
                    info["name"] = line.split("=", 1)[1].strip('"')
                elif line.startswith("VERSION_ID="):
                    info["version"] = line.split("=", 1)[1].strip('"')
                elif line.startswith("ID="):
                    info["id"] = line.split("=", 1)[1].strip('"')
    except (IOError, OSError):
        pass

    return info
