"""Docker configuration and container information collector."""

import json
import os
from typing import Any, Dict, List

from infra_auditor.collectors.base import BaseCollector


class DockerCollector(BaseCollector):
    """Collect Docker daemon configuration and container information."""

    def collect(self) -> Dict[str, Any]:
        """Collect Docker information."""
        # Check if Docker is available
        if not self._is_docker_available():
            return {"available": False}
        
        return {
            "available": True,
            "daemon_config": self._get_daemon_config(),
            "system_info": self._get_docker_info(),
            "containers": self._get_containers_info(),
            "images": self._get_images_info(),
            "networks": self._get_networks_info(),
            "volumes": self._get_volumes_info(),
            "system_df": self._get_system_df(),
            "kernel_settings": self._get_kernel_settings(),
        }

    def _is_docker_available(self) -> bool:
        """Check if Docker is available on the system."""
        return (
            self._run_command(["docker", "--version"]) != ""
            or self._run_command(["which", "docker"]) != ""
        )

    def _get_daemon_config(self) -> Dict[str, Any]:
        """Get Docker daemon configuration."""
        daemon_config: Dict[str, Any] = {}
        
        # Read daemon.json if it exists
        daemon_json_paths = [
            "/etc/docker/daemon.json",
            "/usr/local/etc/docker/daemon.json"  # macOS
        ]
        
        for path in daemon_json_paths:
            if os.path.exists(path):
                daemon_json_content = self._read_file(path)
                if daemon_json_content:
                    try:
                        daemon_config["daemon_json"] = json.loads(daemon_json_content)
                        daemon_config["daemon_json_path"] = path
                        break
                    except json.JSONDecodeError as e:
                        self._record_error("docker_config", path, f"Invalid JSON: {e}")
                        daemon_config["daemon_json_error"] = str(e)
        
        # Get Docker daemon CLI args (from systemd or other init systems)
        daemon_config["systemd_config"] = self._get_docker_systemd_config()
        
        return daemon_config

    def _get_docker_systemd_config(self) -> Dict[str, Any]:
        """Get Docker systemd configuration."""
        systemd_config: Dict[str, Any] = {}
        
        # Check systemd service file
        service_files = [
            "/etc/systemd/system/docker.service",
            "/usr/lib/systemd/system/docker.service",
            "/lib/systemd/system/docker.service"
        ]
        
        for service_file in service_files:
            if os.path.exists(service_file):
                content = self._read_file(service_file)
                if content:
                    systemd_config["service_file"] = service_file
                    systemd_config["content"] = content
                    
                    # Extract ExecStart line
                    for line in content.split("\n"):
                        if "ExecStart=" in line:
                            systemd_config["exec_start"] = line.strip()
                            break
                    break
        
        # Get current systemd status
        status_output = self._run_command(["systemctl", "status", "docker.service"])
        systemd_config["status"] = status_output
        
        return systemd_config

    def _get_docker_info(self) -> Dict[str, Any]:
        """Get Docker system information."""
        info_output = self._run_command(["docker", "info", "--format", "json"])
        docker_info: Dict[str, Any] = {}
        
        if info_output:
            try:
                docker_info = json.loads(info_output)
            except json.JSONDecodeError:
                # Fallback to plain text output
                plain_info = self._run_command(["docker", "info"])
                docker_info["raw_info"] = plain_info
        
        return docker_info

    def _get_containers_info(self) -> List[Dict[str, Any]]:
        """Get information about Docker containers."""
        containers = []
        
        # Get all containers (including stopped ones)
        containers_output = self._run_command([
            "docker", "ps", "-a", "--format", 
            "json:{{.ID}}\t{{.Image}}\t{{.Command}}\t{{.CreatedAt}}\t{{.Status}}\t{{.Names}}"
        ])
        
        if containers_output:
            for line in containers_output.split("\n"):
                if line.strip():
                    parts = line.strip().split("\t")
                    if len(parts) >= 6:
                        container_basic = {
                            "id": parts[0],
                            "image": parts[1], 
                            "command": parts[2],
                            "created": parts[3],
                            "status": parts[4],
                            "names": parts[5]
                        }
                        
                        # Get detailed info for running containers
                        if "Up" in container_basic["status"]:
                            detailed_info = self._get_container_details(container_basic["id"])
                            container_basic.update(detailed_info)
                        
                        containers.append(container_basic)
        
        return containers

    def _get_container_details(self, container_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific container."""
        details: Dict[str, Any] = {}
        
        # Get container inspect info
        inspect_output = self._run_command(["docker", "inspect", container_id])
        if inspect_output:
            try:
                inspect_data = json.loads(inspect_output)
                if inspect_data and len(inspect_data) > 0:
                    container_data = inspect_data[0]
                    
                    # Extract key configuration
                    config = container_data.get("Config", {})
                    host_config = container_data.get("HostConfig", {})
                    
                    details.update({
                        "restart_policy": host_config.get("RestartPolicy", {}),
                        "memory_limit": host_config.get("Memory", 0),
                        "cpu_limit": host_config.get("NanoCpus", 0),
                        "pids_limit": host_config.get("PidsLimit", 0),
                        "privileged": host_config.get("Privileged", False),
                        "read_only_rootfs": host_config.get("ReadonlyRootfs", False),
                        "network_mode": host_config.get("NetworkMode", ""),
                        "pid_mode": host_config.get("PidMode", ""),
                        "security_opt": host_config.get("SecurityOpt", []),
                        "log_driver": host_config.get("LogConfig", {}).get("Type", ""),
                        "log_config": host_config.get("LogConfig", {}),
                        "mounts": container_data.get("Mounts", []),
                        "env": config.get("Env", []),
                        "healthcheck": config.get("Healthcheck", {}),
                    })
            except json.JSONDecodeError:
                pass
        
        # Get container stats if running
        stats_output = self._run_command([
            "docker", "stats", container_id, "--no-stream", "--format", 
            "{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}"
        ])
        if stats_output:
            parts = stats_output.strip().split("\t")
            if len(parts) >= 6:
                details.update({
                    "cpu_percent": parts[0],
                    "memory_usage": parts[1], 
                    "memory_percent": parts[2],
                    "net_io": parts[3],
                    "block_io": parts[4],
                    "pids": parts[5]
                })
        
        return details

    def _get_images_info(self) -> List[Dict[str, Any]]:
        """Get information about Docker images."""
        images = []
        
        images_output = self._run_command([
            "docker", "images", "--format", 
            "{{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}\t{{.Size}}"
        ])
        
        if images_output:
            for line in images_output.split("\n"):
                if line.strip():
                    parts = line.strip().split("\t")
                    if len(parts) >= 5:
                        images.append({
                            "repository": parts[0],
                            "tag": parts[1],
                            "image_id": parts[2],
                            "created": parts[3],
                            "size": parts[4]
                        })
        
        return images

    def _get_networks_info(self) -> List[Dict[str, Any]]:
        """Get Docker networks information."""
        networks = []
        
        networks_output = self._run_command(["docker", "network", "ls", "--format", "json"])
        if networks_output:
            for line in networks_output.split("\n"):
                if line.strip():
                    try:
                        network_data = json.loads(line)
                        # Get detailed network info
                        network_id = network_data.get("ID", "")
                        if network_id:
                            inspect_output = self._run_command([
                                "docker", "network", "inspect", network_id
                            ])
                            if inspect_output:
                                try:
                                    inspect_data = json.loads(inspect_output)
                                    if inspect_data and len(inspect_data) > 0:
                                        networks.append(inspect_data[0])
                                except json.JSONDecodeError:
                                    networks.append(network_data)
                            else:
                                networks.append(network_data)
                    except json.JSONDecodeError:
                        pass
        
        return networks

    def _get_volumes_info(self) -> List[Dict[str, Any]]:
        """Get Docker volumes information."""
        volumes = []
        
        volumes_output = self._run_command(["docker", "volume", "ls", "--format", "json"])
        if volumes_output:
            for line in volumes_output.split("\n"):
                if line.strip():
                    try:
                        volume_data = json.loads(line)
                        volumes.append(volume_data)
                    except json.JSONDecodeError:
                        pass
        
        return volumes

    def _get_system_df(self) -> Dict[str, Any]:
        """Get Docker system disk usage."""
        df_output = self._run_command(["docker", "system", "df", "--format", "json"])
        system_df: Dict[str, Any] = {}
        
        if df_output:
            try:
                system_df = json.loads(df_output)
            except json.JSONDecodeError:
                # Fallback to plain text
                plain_df = self._run_command(["docker", "system", "df"])
                system_df["raw_output"] = plain_df
        
        return system_df

    def _get_kernel_settings(self) -> Dict[str, Any]:
        """Get kernel settings relevant to Docker."""
        kernel_settings: Dict[str, Any] = {}
        
        # Docker-related sysctl settings
        settings_to_check = [
            "net.ipv4.ip_forward",
            "net.bridge.bridge-nf-call-iptables", 
            "net.bridge.bridge-nf-call-ip6tables",
            "fs.inotify.max_user_watches",
            "fs.inotify.max_user_instances",
            "kernel.keys.maxkeys",
            "kernel.keys.maxbytes",
        ]
        
        for setting in settings_to_check:
            value = self._read_sysctl(setting)
            if value:
                kernel_settings[setting] = value
        
        # Check cgroup version
        if os.path.exists("/sys/fs/cgroup/cgroup.controllers"):
            kernel_settings["cgroup_version"] = "v2"
        elif os.path.exists("/sys/fs/cgroup/memory"):
            kernel_settings["cgroup_version"] = "v1"
        else:
            kernel_settings["cgroup_version"] = "unknown"
        
        # Check if iptables is available
        iptables_version = self._run_command(["iptables", "--version"])
        kernel_settings["iptables_available"] = bool(iptables_version)
        if iptables_version:
            kernel_settings["iptables_version"] = iptables_version
        
        return kernel_settings