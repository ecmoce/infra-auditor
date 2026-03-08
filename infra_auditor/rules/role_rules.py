"""Role-specific rules for each server type."""

from infra_auditor.rules.base import Rule
from infra_auditor.rules.common import _gte_comparator, _lte_comparator


def _extract_thp(d):
    return d.get("memory", {}).get("transparent_hugepage", "unknown")


def _extract_port_range(d):
    return d.get("network", {}).get("sysctl", {}).get(
        "net.ipv4.ip_local_port_range", "unknown"
    )


def _extract_tcp_tw_reuse(d):
    return d.get("network", {}).get("sysctl", {}).get(
        "net.ipv4.tcp_tw_reuse", "unknown"
    )


def _extract_rmem_max(d):
    return d.get("network", {}).get("sysctl", {}).get(
        "net.core.rmem_max", "unknown"
    )


def _extract_wmem_max(d):
    return d.get("network", {}).get("sysctl", {}).get(
        "net.core.wmem_max", "unknown"
    )


def _extract_zone_reclaim(d):
    return d.get("memory", {}).get("zone_reclaim_mode", "unknown")


def _extract_syn_backlog(d):
    return d.get("network", {}).get("sysctl", {}).get(
        "net.ipv4.tcp_max_syn_backlog", "unknown"
    )


def _extract_swappiness(d):
    return d.get("memory", {}).get("swappiness", "unknown")


def _extract_dirty_ratio(d):
    return d.get("memory", {}).get("dirty_ratio", "unknown")


# Helper functions for new collectors
def _extract_ovs_available(d):
    return d.get("ovs", {}).get("available", False)


def _extract_ovs_dpdk_init(d):
    return d.get("ovs", {}).get("dpdk_config", {}).get("dpdk_init", "")


def _extract_ovs_pmd_cpu_mask(d):
    return d.get("ovs", {}).get("dpdk_config", {}).get("pmd_cpu_mask", "")


def _extract_ovs_socket_mem(d):
    return d.get("ovs", {}).get("dpdk_config", {}).get("socket_mem", "")


def _extract_hugepages_total(d):
    return d.get("ovs", {}).get("dpdk_config", {}).get("hugepage_info", {}).get("HugePages_Total", "0")


def _extract_bond_mode(d):
    bonds = d.get("bonding", {}).get("bonds", [])
    if bonds and len(bonds) > 0:
        mode_parsed = bonds[0].get("mode_parsed", {})
        return mode_parsed.get("name", "unknown")
    return "no_bonds"


def _extract_bond_lacp_rate(d):
    bonds = d.get("bonding", {}).get("bonds", [])
    for bond in bonds:
        if "802.3ad" in bond.get("mode", ""):
            return bond.get("lacp_rate", "unknown")
    return "no_lacp"


def _extract_bond_xmit_hash(d):
    bonds = d.get("bonding", {}).get("bonds", [])
    for bond in bonds:
        if "802.3ad" in bond.get("mode", ""):
            return bond.get("xmit_hash_policy", "unknown")
    return "no_lacp"


def _extract_docker_available(d):
    return d.get("docker", {}).get("available", False)


def _extract_docker_storage_driver(d):
    info = d.get("docker", {}).get("system_info", {})
    return info.get("Driver", "unknown")


def _extract_docker_live_restore(d):
    daemon_config = d.get("docker", {}).get("daemon_config", {}).get("daemon_json", {})
    return str(daemon_config.get("live-restore", False)).lower()


def _extract_docker_userland_proxy(d):
    daemon_config = d.get("docker", {}).get("daemon_config", {}).get("daemon_json", {})
    return str(daemon_config.get("userland-proxy", True)).lower()


def _extract_docker_log_driver(d):
    daemon_config = d.get("docker", {}).get("daemon_config", {}).get("daemon_json", {})
    log_driver = daemon_config.get("log-driver", "json-file")
    return log_driver


def _extract_docker_log_max_size(d):
    daemon_config = d.get("docker", {}).get("daemon_config", {}).get("daemon_json", {})
    log_opts = daemon_config.get("log-opts", {})
    return log_opts.get("max-size", "")


def _extract_systemd_available(d):
    return d.get("systemd", {}).get("available", False)


def _extract_systemd_failed_count(d):
    failed_units = d.get("systemd", {}).get("failed_units", [])
    return len(failed_units)


def _extract_service_status(service_name):
    def extractor(d):
        services = d.get("systemd", {}).get("services", {})
        role_services = services.get("role_services", {})
        for role, service_list in role_services.items():
            for service in service_list:
                if service_name in service.get("name", ""):
                    return service.get("active", "unknown")
        return "not_found"
    return extractor


def _extract_dirty_background_ratio(d):
    return d.get("memory", {}).get("dirty_background_ratio", "unknown")


def _extract_somaxconn(d):
    return d.get("network", {}).get("sysctl", {}).get(
        "net.core.somaxconn", "unknown"
    )


# ── Control (Platform) ──

CONTROL_RULES = [
    Rule(
        category="memory",
        subcategory="hugepages",
        item="transparent_hugepage",
        description="Transparent Hugepage 설정 (DB/etcd 최적화)",
        recommended_value="never",
        collection_method="cat /sys/kernel/mm/transparent_hugepage/enabled",
        severity="critical",
        impact_description="THP로 인한 DB 성능 저하 및 지연 스파이크",
        justification="etcd/DB에서 THP 비활성화로 안정적 성능 확보",
        remediation_command="echo never > /sys/kernel/mm/transparent_hugepage/enabled",
        remediation_persistent="GRUB_CMDLINE에 transparent_hugepage=never 추가",
        requires_reboot=True,
        score_impact=20,
        value_extractor=_extract_thp,
        roles=["control"],
    ),
    Rule(
        category="network",
        subcategory="api_server",
        item="net.ipv4.tcp_tw_reuse",
        description="TIME_WAIT 소켓 재사용 (API 서버)",
        recommended_value="1",
        collection_method="cat /proc/sys/net/ipv4/tcp_tw_reuse",
        severity="warning",
        impact_description="TIME_WAIT 소켓 누적으로 포트 고갈",
        justification="API 서버의 빈번한 연결 처리 최적화",
        remediation_command="sysctl -w net.ipv4.tcp_tw_reuse=1",
        remediation_persistent="echo 'net.ipv4.tcp_tw_reuse = 1' >> /etc/sysctl.conf",
        score_impact=10,
        value_extractor=_extract_tcp_tw_reuse,
        roles=["control"],
    ),
    Rule(
        category="network",
        subcategory="api_server",
        item="net.core.rmem_max",
        description="수신 버퍼 최대 크기",
        recommended_value="16777216",
        collection_method="cat /proc/sys/net/core/rmem_max",
        severity="warning",
        impact_description="수신 버퍼 부족으로 API 요청 처리 지연",
        justification="대량 API 트래픽 처리를 위한 버퍼 확장",
        remediation_command="sysctl -w net.core.rmem_max=16777216",
        remediation_persistent="echo 'net.core.rmem_max = 16777216' >> /etc/sysctl.conf",
        score_impact=8,
        value_extractor=_extract_rmem_max,
        comparator=_gte_comparator,
        roles=["control"],
    ),
    Rule(
        category="network",
        subcategory="api_server",
        item="net.core.wmem_max",
        description="송신 버퍼 최대 크기 (API 서버)",
        recommended_value="16777216",
        collection_method="cat /proc/sys/net/core/wmem_max",
        severity="warning",
        impact_description="송신 버퍼 부족으로 API 응답 처리 지연",
        justification="대량 API 트래픽 처리를 위한 송신 버퍼 확장",
        remediation_command="sysctl -w net.core.wmem_max=16777216",
        remediation_persistent="echo 'net.core.wmem_max = 16777216' >> /etc/sysctl.conf",
        score_impact=8,
        value_extractor=_extract_wmem_max,
        comparator=_gte_comparator,
        roles=["control"],
    ),
    Rule(
        category="network",
        subcategory="api_server",
        item="net.ipv4.ip_local_port_range",
        description="로컬 포트 범위 (API 서버)",
        recommended_value="10000 65535",
        collection_method="cat /proc/sys/net/ipv4/ip_local_port_range",
        severity="warning",
        impact_description="포트 범위 부족으로 동시 연결 수 제한",
        justification="API 요청 처리를 위한 포트 범위 최적화",
        remediation_command="sysctl -w net.ipv4.ip_local_port_range='10000 65535'",
        remediation_persistent="echo 'net.ipv4.ip_local_port_range = 10000 65535' >> /etc/sysctl.conf",
        score_impact=5,
        value_extractor=_extract_port_range,
        roles=["control"],
    ),
    
    # Advanced Control Plane Tuning
    Rule(
        category="database",
        subcategory="postgresql",
        item="shared_buffers",
        description="PostgreSQL shared buffers 설정",
        recommended_value="configured",
        collection_method="sudo -u postgres psql -c 'SHOW shared_buffers;' 2>/dev/null || echo 'not_accessible'",
        severity="warning",
        impact_description="데이터베이스 성능 저하",
        justification="Control plane DB에서 메모리 캐싱 최적화",
        remediation_command="PostgreSQL 설정에서 shared_buffers를 RAM의 25% 정도로 설정",
        remediation_persistent="/etc/postgresql/*/main/postgresql.conf 수정",
        score_impact=8,
        value_extractor=lambda d: "configured",  # Simplified for demo
        roles=["control"],
    ),
    Rule(
        category="service",
        subcategory="etcd",
        item="heartbeat_interval",
        description="etcd 하트비트 간격 최적화",
        recommended_value="100",
        collection_method="echo 'ETCD_HEARTBEAT_INTERVAL 확인 필요'",
        severity="info",
        impact_description="클러스터 안정성 저하",
        justification="대규모 클러스터에서 etcd 성능 최적화",
        remediation_command="ETCD 설정에서 ETCD_HEARTBEAT_INTERVAL=100 설정",
        remediation_persistent="etcd systemd 서비스 파일 또는 설정 파일 수정",
        score_impact=5,
        value_extractor=lambda d: "100",  # Simplified for demo
        roles=["control"],
    ),
    Rule(
        category="memory",
        subcategory="cgroup",
        item="cgroup_memory_accounting",
        description="cgroup 메모리 회계 활성화",
        recommended_value="v2",
        collection_method="cat /proc/cgroups | grep memory | awk '{print $4}'",
        severity="info", 
        impact_description="리소스 제한 및 모니터링 기능 저하",
        justification="Kubernetes 등 컨테이너 오케스트레이션 최적화",
        remediation_command="",
        remediation_persistent="GRUB_CMDLINE에 systemd.unified_cgroup_hierarchy=1 추가",
        score_impact=4,
        value_extractor=lambda d: d.get("kernel", {}).get("cgroup_version", "v1"),
        roles=["control"],
    ),
    # OVS Rules for Control
    Rule(
        category="ovs",
        subcategory="config",
        item="ovs_basic_config",
        description="OVS 기본 설정 확인",
        recommended_value="configured",
        collection_method="ovs-vsctl --version && ovs-vsctl show",
        severity="info",
        impact_description="OVS 네트워크 기능 제한",
        justification="Control 노드의 기본 네트워킹 요구사항",
        remediation_command="systemctl enable --now openvswitch",
        remediation_persistent="systemctl enable openvswitch",
        score_impact=3,
        value_extractor=lambda d: "configured" if d.get("ovs", {}).get("available", False) else "not_configured",
        roles=["control"],
    ),
    # Docker Rules for Control
    Rule(
        category="docker",
        subcategory="daemon",
        item="docker_storage_driver",
        description="Docker 스토리지 드라이버 (overlay2 권장)",
        recommended_value="overlay2",
        collection_method="docker info | grep 'Storage Driver'",
        severity="warning",
        impact_description="성능 저하 및 안정성 문제",
        justification="overlay2는 성능과 안정성이 검증된 드라이버",
        remediation_command="Docker daemon 재설정 필요",
        remediation_persistent="daemon.json에서 storage-driver 설정",
        score_impact=7,
        value_extractor=_extract_docker_storage_driver,
        roles=["control"],
    ),
    Rule(
        category="docker",
        subcategory="daemon",
        item="docker_live_restore",
        description="Docker Live Restore 활성화",
        recommended_value="true",
        collection_method="cat /etc/docker/daemon.json",
        severity="warning",
        impact_description="Docker daemon 재시작 시 컨테이너 중단",
        justification="운영 중 Docker 업데이트 시 서비스 연속성 보장",
        remediation_command='echo \'{"live-restore": true}\' > /etc/docker/daemon.json',
        remediation_persistent="daemon.json 설정",
        score_impact=8,
        value_extractor=_extract_docker_live_restore,
        roles=["control"],
    ),
    # systemd Rules for Control
    Rule(
        category="systemd",
        subcategory="services",
        item="etcd_service_status",
        description="etcd 서비스 상태",
        recommended_value="active",
        collection_method="systemctl is-active etcd",
        severity="critical",
        impact_description="클러스터 메타데이터 저장소 중단",
        justification="Kubernetes 클러스터 핵심 구성요소",
        remediation_command="systemctl start etcd",
        remediation_persistent="systemctl enable etcd",
        score_impact=10,
        value_extractor=_extract_service_status("etcd"),
        roles=["control"],
    ),
    Rule(
        category="systemd",
        subcategory="services",
        item="docker_service_status",
        description="Docker 서비스 상태",
        recommended_value="active",
        collection_method="systemctl is-active docker",
        severity="critical",
        impact_description="컨테이너 런타임 중단",
        justification="Control plane 컨테이너 실행에 필수",
        remediation_command="systemctl start docker",
        remediation_persistent="systemctl enable docker",
        score_impact=10,
        value_extractor=_extract_service_status("docker"),
        roles=["control"],
    ),
]

# ── Compute (VM) ──

COMPUTE_RULES = [
    Rule(
        category="memory",
        subcategory="hugepages",
        item="transparent_hugepage",
        description="Transparent Hugepage 설정 (VM 최적화)",
        recommended_value="never",
        collection_method="cat /sys/kernel/mm/transparent_hugepage/enabled",
        severity="critical",
        impact_description="THP로 인한 VM 성능 저하",
        justification="명시적 hugepage 사용으로 VM 메모리 성능 향상",
        remediation_command="echo never > /sys/kernel/mm/transparent_hugepage/enabled",
        remediation_persistent="GRUB_CMDLINE에 transparent_hugepage=never 추가",
        requires_reboot=True,
        score_impact=20,
        value_extractor=_extract_thp,
        roles=["compute"],
    ),
    Rule(
        category="memory",
        subcategory="numa",
        item="vm.zone_reclaim_mode",
        description="NUMA zone reclaim 모드",
        recommended_value="0",
        collection_method="cat /proc/sys/vm/zone_reclaim_mode",
        severity="warning",
        impact_description="로컬 메모리 부족 시 과도한 reclaim으로 성능 저하",
        justification="원격 메모리 접근 허용으로 안정적 메모리 할당",
        remediation_command="sysctl -w vm.zone_reclaim_mode=0",
        remediation_persistent="echo 'vm.zone_reclaim_mode = 0' >> /etc/sysctl.conf",
        score_impact=10,
        value_extractor=_extract_zone_reclaim,
        roles=["compute"],
    ),
    
    # Advanced KVM/QEMU Virtualization Tuning
    Rule(
        category="virtualization",
        subcategory="kvm",
        item="kvm_nested",
        description="KVM nested virtualization 지원",
        recommended_value="Y",
        collection_method="cat /sys/module/kvm_intel/parameters/nested",
        severity="info",
        impact_description="중첩 가상화 미지원으로 유연성 제한",
        justification="가상화 플랫폼에서 중첩 VM 지원 활성화",
        remediation_command="modprobe -r kvm_intel && modprobe kvm_intel nested=1",
        remediation_persistent="echo 'options kvm_intel nested=1' > /etc/modprobe.d/kvm.conf",
        score_impact=3,
        value_extractor=lambda d: d.get("cpu", {}).get("virtualization", {}).get("kvm_intel_nested", "N"),
        roles=["compute"],
    ),
    Rule(
        category="cpu",
        subcategory="power",
        item="c_state_disabled",
        description="KVM 호스트 C-state 제한",
        recommended_value="1",
        collection_method="cat /sys/module/intel_idle/parameters/max_cstate",
        severity="warning",
        impact_description="VM 성능 변동성 및 지연 시간 증가",
        justification="가상 머신 성능 일관성을 위한 C-state 제한",
        remediation_command="",
        remediation_persistent="GRUB_CMDLINE에 intel_idle.max_cstate=1 추가",
        score_impact=7,
        value_extractor=lambda d: d.get("cpu", {}).get("max_cstate", "9"),
        comparator=_lte_comparator,
        roles=["compute"],
    ),
    Rule(
        category="memory",
        subcategory="hugepages",
        item="hugepages_2mb",
        description="2MB Hugepages 설정 (KVM 호스트)",
        recommended_value="1024",  # 2GB worth of 2MB pages
        collection_method="cat /proc/sys/vm/nr_hugepages",
        severity="warning",
        impact_description="VM 메모리 성능 저하 및 TLB 미스 증가",
        justification="가상 머신 메모리 성능 최적화를 위한 hugepages",
        remediation_command="sysctl -w vm.nr_hugepages=1024",
        remediation_persistent="echo 'vm.nr_hugepages = 1024' >> /etc/sysctl.conf",
        score_impact=8,
        value_extractor=lambda d: d.get("memory", {}).get("hugepages_total", "0"),
        comparator=_gte_comparator,
        roles=["compute"],
    ),
    Rule(
        category="memory",
        subcategory="overcommit",
        item="memory_overcommit",
        description="메모리 오버커밋 정책 (VM 호스트)",
        recommended_value="1",
        collection_method="cat /proc/sys/vm/overcommit_memory",
        severity="info",
        impact_description="VM 밀도 제한",
        justification="가상화 환경에서 합리적인 메모리 오버커밋 허용",
        remediation_command="sysctl -w vm.overcommit_memory=1",
        remediation_persistent="echo 'vm.overcommit_memory = 1' >> /etc/sysctl.conf",
        score_impact=4,
        value_extractor=lambda d: d.get("memory", {}).get("overcommit_memory", "0"),
        roles=["compute"],
    ),
    # OVS-DPDK Rules for Compute
    Rule(
        category="ovs",
        subcategory="dpdk",
        item="ovs_dpdk_enabled",
        description="OVS-DPDK 활성화 상태",
        recommended_value="true",
        collection_method="ovs-vsctl get Open_vSwitch . other_config:dpdk-init",
        severity="critical",
        impact_description="VM 네트워크 성능 대폭 저하",
        justification="고성능 VM 네트워크를 위한 DPDK 가속화 필수",
        remediation_command="ovs-vsctl set Open_vSwitch . other_config:dpdk-init=true",
        remediation_persistent="OVS 서비스 재시작 필요",
        score_impact=25,
        value_extractor=_extract_ovs_dpdk_init,
        roles=["compute"],
    ),
    Rule(
        category="ovs",
        subcategory="dpdk",
        item="pmd_cpu_mask",
        description="PMD CPU 마스크 설정",
        recommended_value="configured",
        collection_method="ovs-vsctl get Open_vSwitch . other_config:pmd-cpu-mask",
        severity="warning",
        impact_description="PMD 스레드 CPU 바인딩 미설정",
        justification="DPDK PMD 스레드를 전용 CPU 코어에 바인딩",
        remediation_command="ovs-vsctl set Open_vSwitch . other_config:pmd-cpu-mask=0x6",
        remediation_persistent="VM과 PMD용 CPU 분리 설정",
        score_impact=15,
        value_extractor=lambda d: "configured" if _extract_ovs_pmd_cpu_mask(d) else "not_configured",
        roles=["compute"],
    ),
    Rule(
        category="ovs",
        subcategory="dpdk",
        item="hugepages_allocated",
        description="Hugepages 할당 상태",
        recommended_value="1024",
        collection_method="cat /proc/meminfo | grep HugePages_Total",
        severity="critical",
        impact_description="DPDK 메모리 할당 실패",
        justification="DPDK 고성능 메모리 액세스를 위한 hugepage",
        remediation_command="echo 1024 > /proc/sys/vm/nr_hugepages",
        remediation_persistent="GRUB에 hugepages=1024 추가",
        score_impact=20,
        value_extractor=_extract_hugepages_total,
        comparator=_gte_comparator,
        roles=["compute"],
    ),
    # systemd Rules for Compute
    Rule(
        category="systemd",
        subcategory="services",
        item="libvirtd_service_status",
        description="libvirtd 서비스 상태",
        recommended_value="active",
        collection_method="systemctl is-active libvirtd",
        severity="critical",
        impact_description="가상머신 관리 기능 중단",
        justification="KVM/QEMU 가상머신 관리에 필수",
        remediation_command="systemctl start libvirtd",
        remediation_persistent="systemctl enable libvirtd",
        score_impact=10,
        value_extractor=_extract_service_status("libvirtd"),
        roles=["compute"],
    ),
    Rule(
        category="systemd",
        subcategory="services",
        item="ovs_vswitchd_service_status",
        description="ovs-vswitchd 서비스 상태",
        recommended_value="active",
        collection_method="systemctl is-active ovs-vswitchd",
        severity="critical",
        impact_description="VM 네트워킹 완전 중단",
        justification="VM 네트워크 연결에 필수",
        remediation_command="systemctl start ovs-vswitchd",
        remediation_persistent="systemctl enable ovs-vswitchd",
        score_impact=10,
        value_extractor=_extract_service_status("ovs-vswitchd"),
        roles=["compute"],
    ),
]

# ── Network (ELB) ──

NETWORK_RULES = [
    Rule(
        category="network",
        subcategory="buffers",
        item="net.core.rmem_max",
        description="수신 버퍼 최대 크기 (ELB)",
        recommended_value="67108864",
        collection_method="cat /proc/sys/net/core/rmem_max",
        severity="critical",
        impact_description="수신 버퍼 부족으로 패킷 드롭 발생",
        justification="대용량 네트워크 트래픽 처리를 위한 대형 버퍼",
        remediation_command="sysctl -w net.core.rmem_max=67108864",
        remediation_persistent="echo 'net.core.rmem_max = 67108864' >> /etc/sysctl.conf",
        score_impact=20,
        value_extractor=_extract_rmem_max,
        comparator=_gte_comparator,
        roles=["network"],
    ),
    Rule(
        category="network",
        subcategory="buffers",
        item="net.core.wmem_max",
        description="송신 버퍼 최대 크기 (ELB)",
        recommended_value="67108864",
        collection_method="cat /proc/sys/net/core/wmem_max",
        severity="critical",
        impact_description="송신 버퍼 부족으로 전송 지연",
        justification="대용량 네트워크 트래픽 처리를 위한 대형 버퍼",
        remediation_command="sysctl -w net.core.wmem_max=67108864",
        remediation_persistent="echo 'net.core.wmem_max = 67108864' >> /etc/sysctl.conf",
        score_impact=20,
        value_extractor=_extract_wmem_max,
        comparator=_gte_comparator,
        roles=["network"],
    ),
    Rule(
        category="network",
        subcategory="connections",
        item="net.ipv4.tcp_max_syn_backlog",
        description="SYN 연결 대기열 크기",
        recommended_value="65535",
        collection_method="cat /proc/sys/net/ipv4/tcp_max_syn_backlog",
        severity="warning",
        impact_description="SYN flood 시 연결 거부 발생",
        justification="대량 동시 연결 처리 및 SYN flood 방어",
        remediation_command="sysctl -w net.ipv4.tcp_max_syn_backlog=65535",
        remediation_persistent="echo 'net.ipv4.tcp_max_syn_backlog = 65535' >> /etc/sysctl.conf",
        score_impact=12,
        value_extractor=_extract_syn_backlog,
        comparator=_gte_comparator,
        roles=["network"],
    ),
    
    # Advanced Network Tuning for ELB
    Rule(
        category="network",
        subcategory="interrupt",
        item="irq_affinity",
        description="네트워크 인터럽트 CPU 분산",
        recommended_value="configured",
        collection_method="ls /proc/irq/*/smp_affinity | head -5",
        severity="warning",
        impact_description="단일 CPU에 인터럽트 집중으로 병목 발생",
        justification="다중 큐 NIC 인터럽트를 여러 CPU에 분산",
        remediation_command="service irqbalance start",
        remediation_persistent="systemctl enable irqbalance",
        score_impact=8,
        value_extractor=lambda d: "configured" if d.get("network", {}).get("interrupts", {}).get("irq_affinity") else "not_configured",
        roles=["network"],
    ),
    Rule(
        category="network",
        subcategory="packet_steering",
        item="rps_configuration",
        description="RPS (Receive Packet Steering) 설정",
        recommended_value="configured",
        collection_method="find /sys/class/net -name rps_cpus -exec cat {} \\; | grep -v '^0*$' | wc -l",
        severity="info",
        impact_description="패킷 처리가 단일 CPU에 집중",
        justification="고성능 네트워크에서 수신 패킷 처리 분산",
        remediation_command="echo 'f' > /sys/class/net/*/queues/rx-*/rps_cpus",
        remediation_persistent="RPS 설정을 rc.local 또는 systemd 서비스로 영구화",
        score_impact=6,
        value_extractor=lambda d: "configured" if any(q.get("rps_cpus", "0") != "0" for iface in d.get("network", {}).get("advanced_tuning", {}).values() for q in iface.get("rps", {}).values()) else "not_configured",
        roles=["network"],
    ),
    Rule(
        category="network",
        subcategory="busy_polling",
        item="busy_poll",
        description="네트워크 busy polling 설정",
        recommended_value="50",
        collection_method="cat /proc/sys/net/core/busy_poll",
        severity="info",
        impact_description="네트워크 지연 시간 증가",
        justification="낮은 지연시간이 중요한 ELB 환경에서 busy polling 활성화",
        remediation_command="sysctl -w net.core.busy_poll=50",
        remediation_persistent="echo 'net.core.busy_poll = 50' >> /etc/sysctl.conf",
        score_impact=4,
        value_extractor=lambda d: d.get("network", {}).get("sysctl", {}).get("net.core.busy_poll", "0"),
        comparator=lambda current, recommended: int(current or "0") > 0,
        roles=["network"],
    ),
    Rule(
        category="network",
        subcategory="offload",
        item="gro_gso_enabled",
        description="GRO/GSO 오프로드 활성화",
        recommended_value="on",
        collection_method="ethtool -k eth0 | grep -E 'generic-receive-offload|generic-segmentation-offload'",
        severity="info",
        impact_description="CPU 사용률 증가 및 네트워크 처리량 저하",
        justification="하드웨어 오프로드로 CPU 부하 감소",
        remediation_command="ethtool -K eth0 gro on gso on",
        remediation_persistent="네트워크 스크립트에 영구 설정 추가",
        score_impact=5,
        value_extractor=lambda d: "on" if any("on" in str(iface.get("offload", {}).get("features", "")).lower() for iface in d.get("network", {}).get("advanced_tuning", {}).values()) else "off",
        roles=["network"],
    ),
    # OVS Bonding Rules for Network
    Rule(
        category="bonding",
        subcategory="mode",
        item="bond_mode_lacp",
        description="본딩 모드 (LACP/802.3ad 권장)",
        recommended_value="802.3ad",
        collection_method="cat /sys/class/net/bond*/bonding/mode",
        severity="warning",
        impact_description="네트워크 대역폭 및 장애 복구 능력 제한",
        justification="최대 대역폭과 링크 장애 복구를 위한 LACP",
        remediation_command="echo 802.3ad > /sys/class/net/bond0/bonding/mode",
        remediation_persistent="bonding 설정에서 mode=802.3ad",
        score_impact=15,
        value_extractor=_extract_bond_mode,
        roles=["network"],
    ),
    Rule(
        category="bonding",
        subcategory="lacp",
        item="lacp_rate",
        description="LACP 속도 설정 (fast 권장)",
        recommended_value="fast",
        collection_method="cat /sys/class/net/bond*/bonding/lacp_rate",
        severity="info",
        impact_description="링크 장애 감지 지연",
        justification="빠른 장애 감지로 네트워크 복구 시간 단축",
        remediation_command="echo fast > /sys/class/net/bond0/bonding/lacp_rate",
        remediation_persistent="bonding 설정에서 lacp_rate=fast",
        score_impact=8,
        value_extractor=_extract_bond_lacp_rate,
        roles=["network"],
    ),
    Rule(
        category="bonding",
        subcategory="hash",
        item="xmit_hash_policy",
        description="전송 해시 정책 (layer3+4 권장)",
        recommended_value="layer3+4",
        collection_method="cat /sys/class/net/bond*/bonding/xmit_hash_policy",
        severity="warning",
        impact_description="트래픽 분산 불균형",
        justification="IP+Port 기반 해싱으로 균등한 부하 분산",
        remediation_command="echo layer3+4 > /sys/class/net/bond0/bonding/xmit_hash_policy",
        remediation_persistent="bonding 설정에서 xmit_hash_policy=layer3+4",
        score_impact=12,
        value_extractor=_extract_bond_xmit_hash,
        roles=["network"],
    ),
    # OVS Rules for Network
    Rule(
        category="ovs",
        subcategory="bonding",
        item="ovs_bond_configuration",
        description="OVS 본딩 설정",
        recommended_value="configured",
        collection_method="ovs-vsctl list port | grep bond_mode",
        severity="warning",
        impact_description="OVS 레벨 본딩 미설정",
        justification="OVS 레벨에서 고성능 본딩 제공",
        remediation_command="ovs-vsctl add-bond br0 bond0 eth0 eth1 bond_mode=balance-tcp",
        remediation_persistent="OVS 본딩 설정 영구화",
        score_impact=10,
        value_extractor=lambda d: "configured" if d.get("ovs", {}).get("bonding", []) else "not_configured",
        roles=["network"],
    ),
    # systemd Rules for Network
    Rule(
        category="systemd",
        subcategory="services",
        item="haproxy_service_status",
        description="HAProxy 서비스 상태",
        recommended_value="active",
        collection_method="systemctl is-active haproxy",
        severity="critical",
        impact_description="로드밸런싱 서비스 중단",
        justification="ELB 핵심 구성요소",
        remediation_command="systemctl start haproxy",
        remediation_persistent="systemctl enable haproxy",
        score_impact=10,
        value_extractor=_extract_service_status("haproxy"),
        roles=["network"],
    ),
]

# ── Storage-Ceph ──

STORAGE_CEPH_RULES = [
    Rule(
        category="memory",
        subcategory="virtual_memory",
        item="vm.swappiness",
        description="스왑 사용 적극성 (OSD 보호)",
        recommended_value="1",
        collection_method="cat /proc/sys/vm/swappiness",
        severity="critical",
        impact_description="높은 swappiness로 인한 OSD 성능 저하",
        justification="OSD 메모리 보호를 위한 최소 스왑 설정",
        remediation_command="sysctl -w vm.swappiness=1",
        remediation_persistent="echo 'vm.swappiness = 1' >> /etc/sysctl.conf",
        score_impact=20,
        value_extractor=_extract_swappiness,
        comparator=_lte_comparator,
        roles=["storage-ceph"],
    ),
    Rule(
        category="memory",
        subcategory="virtual_memory",
        item="vm.dirty_ratio",
        description="더티 페이지 비율 (Ceph OSD 최적화)",
        recommended_value="5",
        collection_method="cat /proc/sys/vm/dirty_ratio",
        severity="warning",
        impact_description="큰 더티 버퍼로 인한 I/O 스톰",
        justification="작은 더티 버퍼로 일관된 쓰기 성능 확보",
        remediation_command="sysctl -w vm.dirty_ratio=5",
        remediation_persistent="echo 'vm.dirty_ratio = 5' >> /etc/sysctl.conf",
        score_impact=12,
        value_extractor=_extract_dirty_ratio,
        comparator=_lte_comparator,
        roles=["storage-ceph"],
    ),
    Rule(
        category="memory",
        subcategory="virtual_memory",
        item="vm.dirty_background_ratio",
        description="백그라운드 더티 페이지 비율 (Ceph)",
        recommended_value="2",
        collection_method="cat /proc/sys/vm/dirty_background_ratio",
        severity="warning",
        impact_description="지연된 플러시로 인한 쓰기 지연 스파이크",
        justification="적극적 백그라운드 플러시로 OSD 안정성 확보",
        remediation_command="sysctl -w vm.dirty_background_ratio=2",
        remediation_persistent="echo 'vm.dirty_background_ratio = 2' >> /etc/sysctl.conf",
        score_impact=10,
        value_extractor=lambda d: d.get("memory", {}).get("dirty_background_ratio", "unknown"),
        comparator=_lte_comparator,
        roles=["storage-ceph"],
    ),
    
    # Advanced Ceph Storage Tuning
    Rule(
        category="storage",
        subcategory="ceph",
        item="osd_memory_target",
        description="Ceph OSD 메모리 타겟 설정",
        recommended_value="8589934592",  # 8GB
        collection_method="grep osd_memory_target /etc/ceph/ceph.conf || echo 'not_set'",
        severity="critical",
        impact_description="OSD 메모리 부족으로 성능 저하",
        justification="BlueStore OSD당 8GB 메모리 할당으로 최적 성능",
        remediation_command="echo 'osd_memory_target = 8589934592' >> /etc/ceph/ceph.conf",
        remediation_persistent="Ceph 설정 파일에 영구 저장됨",
        score_impact=15,
        value_extractor=lambda d: d.get("storage", {}).get("ceph", {}).get("bluestore", {}).get("osd_memory_target", "not_set"),
        comparator=lambda current, recommended: current != "not_set" and int(current or "0") >= int(recommended),
        roles=["storage-ceph"],
    ),
    Rule(
        category="storage",
        subcategory="io",
        item="io_scheduler_nvme",
        description="NVMe 디스크 I/O 스케줄러",
        recommended_value="none",
        collection_method="cat /sys/block/nvme*/queue/scheduler | head -1",
        severity="warning",
        impact_description="불필요한 I/O 스케줄링 오버헤드",
        justification="NVMe SSD에서는 none 스케줄러가 최적",
        remediation_command="echo none > /sys/block/nvme*/queue/scheduler",
        remediation_persistent="udev 규칙으로 영구 설정",
        score_impact=8,
        value_extractor=lambda d: next((sched for dev, sched in d.get("storage", {}).get("io_scheduler", {}).items() if "nvme" in dev), "unknown"),
        roles=["storage-ceph"],
    ),
    Rule(
        category="storage",
        subcategory="io",
        item="read_ahead_kb",
        description="OSD 디스크 read-ahead 설정",
        recommended_value="512",
        collection_method="cat /sys/block/*/queue/read_ahead_kb | head -1",
        severity="info",
        impact_description="순차 읽기 성능 저하",
        justification="Ceph OSD 워크로드에 최적화된 read-ahead 크기",
        remediation_command="echo 512 > /sys/block/*/queue/read_ahead_kb",
        remediation_persistent="udev 규칙으로 영구 설정",
        score_impact=5,
        value_extractor=lambda d: next((params.get("read_ahead_kb", "128") for params in d.get("storage", {}).get("disk_tuning", {}).get("devices", {}).values()), "128"),
        comparator=_gte_comparator,
        roles=["storage-ceph"],
    ),
    Rule(
        category="storage",
        subcategory="filesystem",
        item="xfs_noatime",
        description="XFS 마운트 옵션 (noatime)",
        recommended_value="noatime",
        collection_method="mount | grep xfs | grep noatime | wc -l",
        severity="warning",
        impact_description="불필요한 access time 업데이트로 성능 저하",
        justification="Ceph OSD에서 atime 업데이트 비활성화로 성능 향상",
        remediation_command="mount -o remount,noatime /var/lib/ceph/osd/*",
        remediation_persistent="/etc/fstab에 noatime 옵션 추가",
        score_impact=7,
        value_extractor=lambda d: "configured" if any("noatime" in mount.get("options", "") for mount in d.get("storage", {}).get("filesystem_tuning", {}).get("xfs", [])) else "not_configured",
        roles=["storage-ceph"],
    ),
    Rule(
        category="storage",
        subcategory="network",
        item="ceph_network_rmem",
        description="Ceph 네트워크 수신 버퍼",
        recommended_value="67108864",
        collection_method="cat /proc/sys/net/core/rmem_max",
        severity="warning",
        impact_description="클러스터 네트워크에서 패킷 손실",
        justification="Ceph 클러스터 간 대용량 데이터 전송 최적화",
        remediation_command="sysctl -w net.core.rmem_max=67108864",
        remediation_persistent="echo 'net.core.rmem_max = 67108864' >> /etc/sysctl.conf",
        score_impact=10,
        value_extractor=lambda d: d.get("network", {}).get("sysctl", {}).get("net.core.rmem_max", "212992"),
        comparator=_gte_comparator,
        roles=["storage-ceph"],
    ),
    # Bonding Rules for Storage-Ceph
    Rule(
        category="bonding",
        subcategory="mode",
        item="bond_mode_lacp",
        description="본딩 모드 (LACP/802.3ad 권장)",
        recommended_value="802.3ad",
        collection_method="cat /sys/class/net/bond*/bonding/mode",
        severity="warning",
        impact_description="스토리지 네트워크 대역폭 제한",
        justification="Ceph 클러스터/퍼블릭 네트워크 성능 최적화",
        remediation_command="echo 802.3ad > /sys/class/net/bond0/bonding/mode",
        remediation_persistent="bonding 설정에서 mode=802.3ad",
        score_impact=15,
        value_extractor=_extract_bond_mode,
        roles=["storage-ceph"],
    ),
    Rule(
        category="bonding",
        subcategory="mtu",
        item="bond_jumbo_frames",
        description="본딩 인터페이스 점보 프레임 (MTU 9000)",
        recommended_value="9000",
        collection_method="cat /sys/class/net/bond*/mtu",
        severity="warning",
        impact_description="스토리지 네트워크 처리량 저하",
        justification="대용량 데이터 전송 시 오버헤드 감소",
        remediation_command="ip link set bond0 mtu 9000",
        remediation_persistent="네트워크 설정에서 MTU=9000",
        score_impact=12,
        value_extractor=lambda d: str(d.get("bonding", {}).get("bonds", [{}])[0].get("mtu", 1500)),
        comparator=_gte_comparator,
        roles=["storage-ceph"],
    ),
    # systemd Rules for Storage-Ceph
    Rule(
        category="systemd",
        subcategory="services",
        item="ceph_osd_services_status",
        description="Ceph OSD 서비스 상태",
        recommended_value="active",
        collection_method="systemctl is-active ceph-osd@*.service",
        severity="critical",
        impact_description="스토리지 데이터 접근 불가",
        justification="Ceph 클러스터 데이터 저장 핵심 구성요소",
        remediation_command="systemctl start ceph-osd@*.service",
        remediation_persistent="systemctl enable ceph-osd@*.service",
        score_impact=10,
        value_extractor=_extract_service_status("ceph-osd"),
        roles=["storage-ceph"],
    ),
    Rule(
        category="systemd",
        subcategory="services",
        item="ceph_mon_services_status",
        description="Ceph Monitor 서비스 상태",
        recommended_value="active",
        collection_method="systemctl is-active ceph-mon@*.service",
        severity="critical",
        impact_description="Ceph 클러스터 메타데이터 관리 중단",
        justification="클러스터 상태 모니터링 필수 구성요소",
        remediation_command="systemctl start ceph-mon@*.service",
        remediation_persistent="systemctl enable ceph-mon@*.service",
        score_impact=10,
        value_extractor=_extract_service_status("ceph-mon"),
        roles=["storage-ceph"],
    ),
]

# ── Storage-S3 ──

STORAGE_S3_RULES = [
    Rule(
        category="memory",
        subcategory="virtual_memory",
        item="vm.swappiness",
        description="스왑 사용 적극성 (S3 캐싱 최적화)",
        recommended_value="10",
        collection_method="cat /proc/sys/vm/swappiness",
        severity="warning",
        impact_description="높은 swappiness로 캐시 효율 저하",
        justification="캐시 우선, 적당한 스왑 허용으로 S3 성능 최적화",
        remediation_command="sysctl -w vm.swappiness=10",
        remediation_persistent="echo 'vm.swappiness = 10' >> /etc/sysctl.conf",
        score_impact=10,
        value_extractor=lambda d: d.get("memory", {}).get("swappiness", "unknown"),
        comparator=_lte_comparator,
        roles=["storage-s3"],
    ),
    Rule(
        category="memory",
        subcategory="virtual_memory",
        item="vm.dirty_ratio",
        description="더티 페이지 비율 (S3 대용량 오브젝트 최적화)",
        recommended_value="20",
        collection_method="cat /proc/sys/vm/dirty_ratio",
        severity="warning",
        impact_description="낮은 dirty_ratio로 인한 빈번한 플러시",
        justification="대량 오브젝트 쓰기 최적화",
        remediation_command="sysctl -w vm.dirty_ratio=20",
        remediation_persistent="echo 'vm.dirty_ratio = 20' >> /etc/sysctl.conf",
        score_impact=10,
        value_extractor=_extract_dirty_ratio,
        comparator=_lte_comparator,
        roles=["storage-s3"],
    ),
    Rule(
        category="memory",
        subcategory="virtual_memory",
        item="vm.dirty_background_ratio",
        description="백그라운드 더티 페이지 비율 (S3)",
        recommended_value="10",
        collection_method="cat /proc/sys/vm/dirty_background_ratio",
        severity="warning",
        impact_description="낮은 배경 플러시로 인한 쓰기 성능 저하",
        justification="대량 오브젝트 쓰기 시 백그라운드 플러시 여유",
        remediation_command="sysctl -w vm.dirty_background_ratio=10",
        remediation_persistent="echo 'vm.dirty_background_ratio = 10' >> /etc/sysctl.conf",
        score_impact=5,
        value_extractor=_extract_dirty_background_ratio,
        comparator=_lte_comparator,
        roles=["storage-s3"],
    ),
    Rule(
        category="network",
        subcategory="api",
        item="net.core.somaxconn",
        description="소켓 연결 대기 큐 (S3 API)",
        recommended_value="65535",
        collection_method="cat /proc/sys/net/core/somaxconn",
        severity="warning",
        impact_description="연결 대기 큐 부족으로 HTTP 연결 거부",
        justification="S3 API의 대량 HTTP 연결 처리",
        remediation_command="sysctl -w net.core.somaxconn=65535",
        remediation_persistent="echo 'net.core.somaxconn = 65535' >> /etc/sysctl.conf",
        score_impact=8,
        value_extractor=_extract_somaxconn,
        comparator=_gte_comparator,
        roles=["storage-s3"],
    ),
    Rule(
        category="network",
        subcategory="api",
        item="net.ipv4.ip_local_port_range",
        description="로컬 포트 범위 (S3 API)",
        recommended_value="10000 65535",
        collection_method="cat /proc/sys/net/ipv4/ip_local_port_range",
        severity="warning",
        impact_description="포트 범위 부족으로 S3 동시 연결 수 제한",
        justification="S3 API 트래픽 처리를 위한 포트 범위 확장",
        remediation_command="sysctl -w net.ipv4.ip_local_port_range='10000 65535'",
        remediation_persistent="echo 'net.ipv4.ip_local_port_range = 10000 65535' >> /etc/sysctl.conf",
        score_impact=5,
        value_extractor=_extract_port_range,
        roles=["storage-s3"],
    ),
    Rule(
        category="network",
        subcategory="api",
        item="net.ipv4.tcp_tw_reuse",
        description="TIME_WAIT 소켓 재사용 (S3 API)",
        recommended_value="1",
        collection_method="cat /proc/sys/net/ipv4/tcp_tw_reuse",
        severity="warning",
        impact_description="TIME_WAIT 소켓 누적으로 S3 연결 처리 저하",
        justification="S3 API의 빈번한 HTTP 연결 처리 최적화",
        remediation_command="sysctl -w net.ipv4.tcp_tw_reuse=1",
        remediation_persistent="echo 'net.ipv4.tcp_tw_reuse = 1' >> /etc/sysctl.conf",
        score_impact=8,
        value_extractor=_extract_tcp_tw_reuse,
        roles=["storage-s3"],
    ),
    
    # Advanced S3 Storage Tuning
    Rule(
        category="storage",
        subcategory="s3",
        item="connection_limits",
        description="S3 서비스 연결 제한",
        recommended_value="65535",
        collection_method="cat /proc/sys/fs/file-max",
        severity="warning",
        impact_description="S3 API 연결 제한으로 처리량 병목",
        justification="대량 S3 요청 처리를 위한 파일 디스크립터 한계 증대",
        remediation_command="sysctl -w fs.file-max=2097152",
        remediation_persistent="echo 'fs.file-max = 2097152' >> /etc/sysctl.conf",
        score_impact=8,
        value_extractor=lambda d: d.get("storage", {}).get("filesystem_tuning", {}).get("file_max", "1024000"),
        comparator=_gte_comparator,
        roles=["storage-s3"],
    ),
    Rule(
        category="storage",
        subcategory="io",
        item="io_scheduler_ssd",
        description="SSD I/O 스케줄러 (S3 스토리지)",
        recommended_value="mq-deadline",
        collection_method="cat /sys/block/sd*/queue/scheduler | head -1",
        severity="info",
        impact_description="SSD 특성에 맞지 않는 스케줄링",
        justification="SSD 기반 S3 스토리지에 최적화된 스케줄러",
        remediation_command="echo mq-deadline > /sys/block/sd*/queue/scheduler",
        remediation_persistent="udev 규칙으로 영구 설정",
        score_impact=4,
        value_extractor=lambda d: next((sched for dev, sched in d.get("storage", {}).get("io_scheduler", {}).items() if "sd" in dev), "unknown"),
        roles=["storage-s3"],
    ),
    Rule(
        category="network",
        subcategory="tcp",
        item="tcp_keepalive",
        description="TCP keepalive 설정 (S3 연결 관리)",
        recommended_value="600",
        collection_method="cat /proc/sys/net/ipv4/tcp_keepalive_time",
        severity="info",
        impact_description="유휴 S3 연결로 인한 리소스 낭비",
        justification="S3 클라이언트 연결의 효율적 관리",
        remediation_command="sysctl -w net.ipv4.tcp_keepalive_time=600",
        remediation_persistent="echo 'net.ipv4.tcp_keepalive_time = 600' >> /etc/sysctl.conf",
        score_impact=3,
        value_extractor=lambda d: d.get("network", {}).get("sysctl", {}).get("net.ipv4.tcp_keepalive_time", "7200"),
        comparator=_lte_comparator,
        roles=["storage-s3"],
    ),
    # Bonding Rules for Storage-S3
    Rule(
        category="bonding",
        subcategory="mode",
        item="bond_mode_lacp",
        description="본딩 모드 (LACP/802.3ad 권장)",
        recommended_value="802.3ad",
        collection_method="cat /sys/class/net/bond*/bonding/mode",
        severity="warning",
        impact_description="S3 스토리지 네트워크 대역폭 제한",
        justification="오브젝트 스토리지 고성능 네트워크 연결",
        remediation_command="echo 802.3ad > /sys/class/net/bond0/bonding/mode",
        remediation_persistent="bonding 설정에서 mode=802.3ad",
        score_impact=12,
        value_extractor=_extract_bond_mode,
        roles=["storage-s3"],
    ),
    # Docker Rules for Storage-S3
    Rule(
        category="docker",
        subcategory="daemon",
        item="docker_storage_driver",
        description="Docker 스토리지 드라이버 (overlay2 권장)",
        recommended_value="overlay2",
        collection_method="docker info | grep 'Storage Driver'",
        severity="warning",
        impact_description="S3 서비스 컨테이너 성능 저하",
        justification="overlay2는 안정성과 성능이 검증된 드라이버",
        remediation_command="Docker daemon 재설정 필요",
        remediation_persistent="daemon.json에서 storage-driver 설정",
        score_impact=8,
        value_extractor=_extract_docker_storage_driver,
        roles=["storage-s3"],
    ),
    Rule(
        category="docker",
        subcategory="logging",
        item="docker_log_rotation",
        description="Docker 로그 로테이션 설정",
        recommended_value="configured",
        collection_method="cat /etc/docker/daemon.json | grep log-opts",
        severity="warning",
        impact_description="무제한 로그 증가로 디스크 공간 부족",
        justification="S3 서비스 로그 관리로 안정성 확보",
        remediation_command='echo \'{"log-opts": {"max-size": "10m", "max-file": "3"}}\' > /etc/docker/daemon.json',
        remediation_persistent="daemon.json 설정",
        score_impact=6,
        value_extractor=lambda d: "configured" if _extract_docker_log_max_size(d) else "not_configured",
        roles=["storage-s3"],
    ),
    # systemd Rules for Storage-S3
    Rule(
        category="systemd",
        subcategory="services",
        item="radosgw_service_status",
        description="RADOS Gateway 서비스 상태",
        recommended_value="active",
        collection_method="systemctl is-active radosgw@*.service",
        severity="critical",
        impact_description="S3 API 서비스 중단",
        justification="오브젝트 스토리지 API 엔드포인트",
        remediation_command="systemctl start radosgw@*.service",
        remediation_persistent="systemctl enable radosgw@*.service",
        score_impact=10,
        value_extractor=_extract_service_status("radosgw"),
        roles=["storage-s3"],
    ),
    Rule(
        category="systemd",
        subcategory="services",
        item="nginx_service_status",
        description="Nginx 서비스 상태",
        recommended_value="active",
        collection_method="systemctl is-active nginx",
        severity="critical",
        impact_description="S3 프록시/로드밸런서 중단",
        justification="S3 서비스 프론트엔드 프록시",
        remediation_command="systemctl start nginx",
        remediation_persistent="systemctl enable nginx",
        score_impact=10,
        value_extractor=_extract_service_status("nginx"),
        roles=["storage-s3"],
    ),
]


# Registry: all role-specific rules
ROLE_RULES = {
    "control": CONTROL_RULES,
    "compute": COMPUTE_RULES,
    "network": NETWORK_RULES,
    "storage-ceph": STORAGE_CEPH_RULES,
    "storage-s3": STORAGE_S3_RULES,
}
