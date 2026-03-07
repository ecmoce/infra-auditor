"""Storage information collector."""

import glob
import os
from typing import Any, Dict, List

from infra_auditor.collectors.base import BaseCollector


class StorageCollector(BaseCollector):
    """Collect storage hardware and tuning information."""

    def collect(self) -> Dict[str, Any]:
        """Collect storage information."""
        return {
            "devices": self._get_block_devices(),
            "mounts": self._get_mounts(),
        }

    def _get_block_devices(self) -> List[Dict[str, Any]]:
        """Get block device information."""
        devices = []
        try:
            dev_dirs = glob.glob("/sys/block/*")
        except OSError:
            return devices

        for dev_path in dev_dirs:
            name = os.path.basename(dev_path)
            # Skip virtual/loop devices
            if name.startswith(("loop", "ram", "dm-")):
                continue

            dev_info: Dict[str, Any] = {"name": "/dev/" + name}

            # Rotational
            rotational = self._read_file(
                os.path.join(dev_path, "queue/rotational"), ""
            )
            if rotational:
                dev_info["rotational"] = rotational == "1"
                dev_info["type"] = "hdd" if rotational == "1" else "ssd"
                if name.startswith("nvme"):
                    dev_info["type"] = "nvme"

            # Scheduler
            scheduler = self._read_file(
                os.path.join(dev_path, "queue/scheduler"), ""
            )
            if scheduler:
                dev_info["scheduler_raw"] = scheduler
                # Extract active scheduler: [mq-deadline] none
                import re

                match = re.search(r"\[(\w[\w-]*)\]", scheduler)
                if match:
                    dev_info["scheduler"] = match.group(1)
                else:
                    dev_info["scheduler"] = scheduler.strip()

            # Read-ahead
            ra = self._read_file(
                os.path.join(dev_path, "queue/read_ahead_kb"), ""
            )
            if ra:
                try:
                    dev_info["read_ahead_kb"] = int(ra)
                except ValueError:
                    pass

            # Nr requests
            nr = self._read_file(
                os.path.join(dev_path, "queue/nr_requests"), ""
            )
            if nr:
                try:
                    dev_info["nr_requests"] = int(nr)
                except ValueError:
                    pass

            # Size
            size_sectors = self._read_file(
                os.path.join(dev_path, "size"), ""
            )
            if size_sectors:
                try:
                    dev_info["size_gb"] = round(
                        int(size_sectors) * 512 / (1024**3), 1
                    )
                except ValueError:
                    pass

            devices.append(dev_info)

        return devices

    def _get_mounts(self) -> List[Dict[str, str]]:
        """Get mount information from /proc/mounts."""
        mounts = []
        content = self._read_file("/proc/mounts")
        for line in content.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[0].startswith("/dev/"):
                mounts.append(
                    {
                        "device": parts[0],
                        "mountpoint": parts[1],
                        "fstype": parts[2],
                        "options": parts[3],
                    }
                )
        return mounts
