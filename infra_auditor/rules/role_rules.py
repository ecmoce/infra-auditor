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
]

# ── Storage-Ceph ──

STORAGE_CEPH_RULES = [
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
        value_extractor=lambda d: d.get("memory", {}).get("dirty_ratio", "unknown"),
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
]


# Registry: all role-specific rules
ROLE_RULES = {
    "control": CONTROL_RULES,
    "compute": COMPUTE_RULES,
    "network": NETWORK_RULES,
    "storage-ceph": STORAGE_CEPH_RULES,
    "storage-s3": STORAGE_S3_RULES,
}
