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
            "ceph": self._get_ceph_info(),
            "io_scheduler": self._get_io_scheduler_info(),
            "disk_tuning": self._get_disk_tuning_info(),
            "filesystem_tuning": self._get_filesystem_tuning(),
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

    def _get_ceph_info(self) -> Dict[str, Any]:
        """Get Ceph-specific configuration and tuning information."""
        result = {}
        
        # Check if Ceph services are running
        ceph_services = []
        service_patterns = ['ceph-osd@*', 'ceph-mon@*', 'ceph-mds@*', 'ceph-mgr@*', 'ceph-rgw@*']
        
        for pattern in service_patterns:
            services = self._run_command(["systemctl", "list-units", "--no-pager", f"{pattern}.service"], "")
            if services and "running" in services:
                ceph_services.append(pattern.replace('@*', ''))
                
        if ceph_services:
            result["running_services"] = ceph_services
            
        # Check for Ceph configuration
        ceph_conf = self._read_file("/etc/ceph/ceph.conf", "")
        if ceph_conf:
            result["config_exists"] = True
            
            # Parse key configuration parameters
            config_params = {}
            for line in ceph_conf.split('\n'):
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    config_params[key.strip()] = value.strip()
                    
            if config_params:
                result["config_params"] = config_params
                
        # Check for BlueStore tuning
        bluestore_params = {}
        
        # Check for RocksDB options in Ceph config
        if ceph_conf and "bluestore_rocksdb_options" in ceph_conf:
            for line in ceph_conf.split('\n'):
                if "bluestore_rocksdb_options" in line and not line.strip().startswith('#'):
                    bluestore_params["rocksdb_options"] = line.split('=', 1)[1].strip()
                    
        # Check OSD memory target
        if ceph_conf and "osd_memory_target" in ceph_conf:
            for line in ceph_conf.split('\n'):
                if "osd_memory_target" in line and not line.strip().startswith('#'):
                    bluestore_params["osd_memory_target"] = line.split('=', 1)[1].strip()
                    
        if bluestore_params:
            result["bluestore"] = bluestore_params
            
        return result

    def _get_io_scheduler_info(self) -> Dict[str, str]:
        """Get I/O scheduler information for block devices."""
        result = {}
        
        try:
            dev_dirs = glob.glob("/sys/block/*")
        except OSError:
            return result
            
        for dev_path in dev_dirs:
            name = os.path.basename(dev_path)
            # Skip virtual devices
            if name.startswith(('loop', 'ram', 'dm-')):
                continue
                
            scheduler_path = os.path.join(dev_path, "queue/scheduler")
            scheduler = self._read_file(scheduler_path, "")
            if scheduler:
                # Extract current scheduler from format like: "noop [deadline] cfq"
                current = None
                schedulers = scheduler.split()
                for sched in schedulers:
                    if sched.startswith('[') and sched.endswith(']'):
                        current = sched[1:-1]
                        break
                        
                if current:
                    result[name] = current
                    
        return result

    def _get_disk_tuning_info(self) -> Dict[str, Any]:
        """Get disk tuning parameters."""
        result = {}
        
        try:
            dev_dirs = glob.glob("/sys/block/*")
        except OSError:
            return result
            
        disk_params = {}
        for dev_path in dev_dirs:
            name = os.path.basename(dev_path)
            # Skip virtual devices
            if name.startswith(('loop', 'ram', 'dm-')):
                continue
                
            device_info = {}
            
            # Get read-ahead setting
            readahead = self._read_file(os.path.join(dev_path, "queue/read_ahead_kb"), "")
            if readahead:
                device_info["read_ahead_kb"] = readahead
                
            # Get nr_requests
            nr_requests = self._read_file(os.path.join(dev_path, "queue/nr_requests"), "")
            if nr_requests:
                device_info["nr_requests"] = nr_requests
                
            # Get rotational flag
            rotational = self._read_file(os.path.join(dev_path, "queue/rotational"), "")
            if rotational:
                device_info["rotational"] = rotational
                
            # Get optimal I/O size
            optimal_io_size = self._read_file(os.path.join(dev_path, "queue/optimal_io_size"), "")
            if optimal_io_size:
                device_info["optimal_io_size"] = optimal_io_size
                
            # Get minimum I/O size
            min_io_size = self._read_file(os.path.join(dev_path, "queue/minimum_io_size"), "")
            if min_io_size:
                device_info["minimum_io_size"] = min_io_size
                
            if device_info:
                disk_params[name] = device_info
                
        if disk_params:
            result["devices"] = disk_params
            
        return result

    def _get_filesystem_tuning(self) -> Dict[str, Any]:
        """Get filesystem-specific tuning parameters."""
        result = {}
        
        # Get mounted filesystems and their options
        mounts = self._get_mounts()
        xfs_mounts = []
        ext4_mounts = []
        
        for mount in mounts:
            if mount["fstype"] == "xfs":
                xfs_mounts.append({
                    "device": mount["device"],
                    "mountpoint": mount["mountpoint"],
                    "options": mount["options"]
                })
            elif mount["fstype"] == "ext4":
                ext4_mounts.append({
                    "device": mount["device"],
                    "mountpoint": mount["mountpoint"],
                    "options": mount["options"]
                })
                
        if xfs_mounts:
            result["xfs"] = xfs_mounts
            
        if ext4_mounts:
            result["ext4"] = ext4_mounts
            
        # Check for aio limits
        aio_max_nr = self._read_file("/proc/sys/fs/aio-max-nr", "")
        if aio_max_nr:
            result["aio_max_nr"] = aio_max_nr
            
        # Check for file descriptor limits
        file_max = self._read_file("/proc/sys/fs/file-max", "")
        if file_max:
            result["file_max"] = file_max
            
        # Check inotify limits
        inotify_watches = self._read_file("/proc/sys/fs/inotify/max_user_watches", "")
        if inotify_watches:
            result["inotify_max_user_watches"] = inotify_watches
            
        return result
