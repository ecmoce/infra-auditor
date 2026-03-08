# 역할별 OS 튜닝 규칙

## 개요

각 서버 역할(Control, Compute, Network, Storage-Ceph, Storage-S3)별로 최적화해야 할 OS 설정과 권장값을 정의합니다.

## 규칙 통계 (Phase 7 Infrastructure Enhanced)

- **전체 규칙 수**: 95개 (기존 62개 → 53% 증가)
- **공통 규칙**: 33개 (systemd, Docker, inotify 확장 포함)
- **역할별 규칙**: 62개 (OVS, Network Bonding, Docker, systemd 포함)

### 새로 추가된 고급 튜닝 영역

#### 네트워크 고급 튜닝 (모든 역할)
- **RPS/XPS/RFS 설정**: 멀티큐 네트워크 인터페이스 최적화
- **인터럽트 분산**: IRQ affinity 및 coalescing 설정
- **연결 추적**: nf_conntrack 대용량 환경 튜닝
- **TCP 고급 설정**: window scaling, busy polling

#### OVS (Open vSwitch) 튜닝 (Compute, Network 역할)
- **OVS-DPDK**: PMD CPU 바인딩, hugepage 할당, socket memory
- **Flow Tables**: 흐름 캐시 크기, EMC/megaflow 최적화
- **Handler/Revalidator**: 스레드 수 최적화
- **OVS Bonding**: balance-tcp, balance-slb, LACP 설정
- **vhost-user**: VM 연결 소켓 최적화

#### Network Bonding 튜닝 (Network, Storage 역할)
- **본딩 모드**: 802.3ad LACP, active-backup, balance-xor
- **LACP 최적화**: fast rate, layer3+4 해싱
- **장애 감지**: MII monitoring 간격, fail-over 설정
- **MTU 일치**: bond와 slave 인터페이스 일관성
- **점보프레임**: 스토리지 네트워크 MTU 9000

#### Docker 컨테이너 튜닝 (Control, Storage-S3 역할)
- **Storage Driver**: overlay2 권장, aufs/devicemapper 금지
- **Live Restore**: 데몬 재시작 시 컨테이너 연속성
- **로그 관리**: 로그 로테이션, 크기 제한
- **네트워크**: userland-proxy 비활성화, IP forwarding
- **보안**: bridge-nf-call-iptables 활성화

#### systemd 서비스 관리 (모든 역할)
- **서비스 상태**: 역할별 핵심 서비스 모니터링
- **Unit 파일 최적화**: LimitNOFILE, TasksMax, MemoryMax
- **journald 설정**: persistent storage, 디스크 사용량 제한
- **시스템 설정**: DefaultLimitNOFILE, 부트 시간 분석
- **실패 감지**: 실패한 유닛 수 모니터링

#### KVM/QEMU 가상화 튜닝 (Compute 역할)
- **중첩 가상화**: KVM nested 지원 활성화
- **CPU 격리**: C-state 제한, CPU pinning 최적화
- **메모리 최적화**: Hugepages, 오버커밋 정책
- **NUMA 최적화**: 토폴로지 인식 설정

#### Ceph 스토리지 최적화 (Storage-Ceph 역할)
- **BlueStore 튜닝**: OSD 메모리 타겟, RocksDB 최적화
- **I/O 스케줄러**: NVMe none, SSD mq-deadline 설정
- **네트워크**: 클러스터 통신 버퍼 최적화
- **파일시스템**: XFS noatime, allocsize 최적화

#### 메모리 관리 고급 (모든 역할)
- **KSM 활용**: Kernel Same-page Merging 설정
- **대용량 RAM**: 1-2TB 환경에 맞는 min_free_kbytes
- **NUMA 최적화**: zone_reclaim 비활성화
- **THP 정책**: 역할별 transparent hugepages 최적화

#### 커널 고급 튜닝 (모든 역할)
- **스케줄러**: migration cost, autogroup 설정
- **안정성**: panic_on_oops, watchdog 설정
- **I/O 한계**: aio-max-nr, inotify 대용량 설정
- **cgroup**: v1/v2 감지 및 최적화

## 공통 기본 규칙

### CPU 관련
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| governor | `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor` | performance | 일관된 성능, 지연 시간 최소화 |
| C-states | `cat /sys/module/intel_idle/parameters/max_cstate` | 1 | 깊은 절전 상태로 인한 지연 방지 |
| numa_balancing | `cat /proc/sys/kernel/numa_balancing` | 0 | 자동 NUMA 밸런싱은 성능 저하 야기 |

### Memory 관리
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| vm.swappiness | `/proc/sys/vm/swappiness` | 1 | 메모리 부족 시에만 스왑 사용 |
| vm.dirty_ratio | `/proc/sys/vm/dirty_ratio` | 15 | 쓰기 성능과 안정성의 균형 |
| vm.dirty_background_ratio | `/proc/sys/vm/dirty_background_ratio` | 5 | 백그라운드 플러시 최적화 |
| vm.overcommit_memory | `/proc/sys/vm/overcommit_memory` | 1 | 합리적 메모리 오버커밋 허용 |

### Network 기본
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| net.core.somaxconn | `/proc/sys/net/core/somaxconn` | 65535 | 대량 연결 처리 |
| net.core.netdev_max_backlog | `/proc/sys/net/core/netdev_max_backlog` | 5000 | 패킷 드롭 방지 |
| net.ipv4.tcp_congestion_control | `/proc/sys/net/ipv4/tcp_congestion_control` | bbr | 최신 혼잡 제어 알고리즘 |

### Storage 기본
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| I/O Scheduler (SSD) | `cat /sys/block/nvme0n1/queue/scheduler` | none/noop | SSD에서 불필요한 지연 제거 |
| I/O Scheduler (HDD) | `cat /sys/block/sda/queue/scheduler` | mq-deadline | HDD의 seek 시간 최적화 |
| read_ahead_kb | `cat /sys/block/*/queue/read_ahead_kb` | 512 | SSD 환경에서 적절한 readahead |

### Kernel 제한
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| fs.file-max | `/proc/sys/fs/file-max` | 2000000 | 대량 파일 핸들 지원 |
| kernel.pid_max | `/proc/sys/kernel/pid_max` | 4194304 | 대량 프로세스 지원 |
| kernel.threads-max | `/proc/sys/kernel/threads-max` | 2000000 | 대량 스레드 지원 |

---

## Control (Platform) 역할

### 특화 설정

#### CPU 최적화
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| isolcpus | `/proc/cmdline` 확인 | 설정 안함 | API 서버는 모든 CPU 활용 필요 |
| rcu_nocbs | `/proc/cmdline` 확인 | 설정 안함 | 관리 워크로드에 적합하지 않음 |

#### 네트워크 최적화 (API 서버)
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| net.ipv4.ip_local_port_range | `/proc/sys/net/ipv4/ip_local_port_range` | 10000 65535 | API 요청 처리 최적화 |
| net.ipv4.tcp_tw_reuse | `/proc/sys/net/ipv4/tcp_tw_reuse` | 1 | TIME_WAIT 소켓 재사용 |
| net.core.rmem_max | `/proc/sys/net/core/rmem_max` | 16777216 | 수신 버퍼 최적화 |
| net.core.wmem_max | `/proc/sys/net/core/wmem_max` | 16777216 | 송신 버퍼 최적화 |

#### 메모리 (etcd/DB 최적화)
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| vm.swappiness | `/proc/sys/vm/swappiness` | 1 | DB 성능 보장 |
| transparent_hugepage | `/sys/kernel/mm/transparent_hugepage/enabled` | never | DB에서 THP 문제 회피 |

#### 서비스별 확인
| 서비스 | 확인 방법 | 권장 설정 |
|--------|-----------|-----------|
| etcd | `systemctl is-active etcd` | 활성화 상태 |
| API server | `ss -tlnp | grep :6443` | 포트 바인딩 확인 |
| scheduler | `ss -tlnp | grep :10251` | 스케줄러 포트 확인 |

---

## Compute (VM) 역할

### 특화 설정

#### CPU 가상화 최적화
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| isolcpus | `/proc/cmdline` | CPU 0,1 격리 | 호스트 태스크와 VM 격리 |
| rcu_nocbs | `/proc/cmdline` | 0,1 | RCU 콜백을 특정 CPU에서 처리 |
| nohz_full | `/proc/cmdline` | 2-N | 틱 인터럽트 최소화 |
| intel_pstate | `/proc/cmdline` | disable | VM 워크로드에 적합한 주파수 제어 |

#### NUMA 최적화
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| kernel.numa_balancing | `/proc/sys/kernel/numa_balancing` | 0 | VM의 NUMA 토폴로지 유지 |
| vm.zone_reclaim_mode | `/proc/sys/vm/zone_reclaim_mode` | 0 | 원격 메모리 접근 허용 |

#### Hugepages (VM 성능)
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| hugepages-2048kB | `/proc/meminfo` | 총 메모리의 80% | VM 메모리 성능 향상 |
| transparent_hugepage | `/sys/kernel/mm/transparent_hugepage/enabled` | never | 명시적 hugepage 사용 |

#### KVM/QEMU 확인
| 서비스 | 확인 방법 | 권장 설정 |
|--------|-----------|-----------|
| libvirtd | `systemctl is-active libvirtd` | 활성화 |
| KVM 모듈 | `lsmod | grep kvm` | kvm_intel 로드 확인 |
| nested 가상화 | `/sys/module/kvm_intel/parameters/nested` | Y |

#### IRQ 친화도
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| NIC IRQ | `/proc/interrupts` | CPU 0,1에 바인딩 | VM과 네트워크 처리 분리 |

---

## Network (ELB) 역할

### 특화 설정

#### CPU 최적화 (DPDK/고성능 네트워킹)
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| isolcpus | `/proc/cmdline` | 0,1 격리 | 네트워크 처리용 CPU 확보 |
| nohz_full | `/proc/cmdline` | 2-N | 패킷 처리 지연 최소화 |
| rcu_nocbs | `/proc/cmdline` | 0,1 | RCU 오버헤드 격리 |

#### 네트워크 성능 최적화
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| net.core.rmem_max | `/proc/sys/net/core/rmem_max` | 67108864 | 대용량 수신 버퍼 |
| net.core.wmem_max | `/proc/sys/net/core/wmem_max` | 67108864 | 대용량 송신 버퍼 |
| net.ipv4.tcp_rmem | `/proc/sys/net/ipv4/tcp_rmem` | 4096 65536 16777216 | TCP 수신 버퍼 자동 조정 |
| net.ipv4.tcp_wmem | `/proc/sys/net/ipv4/tcp_wmem` | 4096 65536 16777216 | TCP 송신 버퍼 자동 조정 |

#### 연결 처리 최적화
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| net.core.somaxconn | `/proc/sys/net/core/somaxconn` | 65535 | 대량 연결 대기열 |
| net.ipv4.tcp_max_syn_backlog | `/proc/sys/net/ipv4/tcp_max_syn_backlog` | 65535 | SYN flood 방어 |
| net.netfilter.nf_conntrack_max | `/proc/sys/net/netfilter/nf_conntrack_max` | 1048576 | 연결 추적 확장 |

#### NIC 최적화 (Mellanox)
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| ring buffer | `ethtool -g <interface>` | RX: 4096, TX: 4096 | 패킷 드롭 방지 |
| MTU | `ip link show` | 9000 (jumbo frame) | 대용량 전송 효율성 |
| bonding mode | `/proc/net/bonding/bond0` | mode=802.3ad | 대역폭 집계 및 장애 복구 |

#### 인터럽트 최적화
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| IRQ balance | `/proc/interrupts` | 균등 분산 | CPU 간 인터럽트 로드 밸런싱 |
| RSS queue | `ethtool -l <interface>` | CPU 코어 수와 동일 | 수신 패킷 분산 |

#### HAProxy/nginx 확인
| 서비스 | 확인 방법 | 권장 설정 |
|--------|-----------|-----------|
| HAProxy | `systemctl is-active haproxy` | 활성화 |
| nginx | `systemctl is-active nginx` | 활성화 |
| 포트 바인딩 | `ss -tlnp | grep ':80\|:443'` | 로드밸런서 포트 확인 |

---

## Storage-Ceph 역할

### 특화 설정

#### CPU 최적화 (OSD 성능)
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| governor | `cpupower frequency-info` | performance | OSD 처리량 최적화 |
| C-states | `/sys/module/intel_idle/parameters/max_cstate` | 1 | 스토리지 지연 최소화 |

#### 메모리 최적화
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| vm.swappiness | `/proc/sys/vm/swappiness` | 1 | OSD 메모리 보호 |
| vm.dirty_ratio | `/proc/sys/vm/dirty_ratio` | 5 | 작은 버퍼로 일관된 쓰기 성능 |
| vm.dirty_background_ratio | `/proc/sys/vm/dirty_background_ratio` | 2 | 적극적 백그라운드 플러시 |

#### 스토리지 I/O 최적화
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| I/O scheduler (SSD) | `cat /sys/block/nvme*/queue/scheduler` | none | BlueStore는 자체 I/O 스케줄링 |
| I/O scheduler (HDD) | `cat /sys/block/sd*/queue/scheduler` | mq-deadline | 회전 디스크 최적화 |
| nr_requests | `cat /sys/block/*/queue/nr_requests` | 512 | 큐 깊이 최적화 |
| read_ahead_kb | `cat /sys/block/*/queue/read_ahead_kb` | 512 | Ceph 워크로드 최적화 |

#### 파일시스템 마운트 옵션
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| XFS 마운트 옵션 | `/proc/mounts` | noatime,largeio,inode64,swalloc | 메타데이터 오버헤드 최소화 |
| ext4 마운트 옵션 | `/proc/mounts` | noatime,data=writeback,barrier=0,nobh | 쓰기 성능 최적화 (주의: 일관성 위험) |

#### Ceph 설정 확인
| 서비스 | 확인 방법 | 권장 설정 |
|--------|-----------|-----------|
| ceph-osd | `systemctl list-units ceph-osd*` | 활성화된 OSD 확인 |
| BlueStore | `ceph osd metadata | grep bluestore` | BlueStore 사용 확인 |

#### 네트워크 (Cluster/Public 분리)
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| MTU (cluster) | `ip link show` | 9000 | 클러스터 통신 최적화 |
| bonding mode | `/proc/net/bonding/bond*` | mode=balance-xor | 복제 트래픽 분산 |

---

## Storage-S3 역할

### 특화 설정

#### CPU 최적화 (Object Storage)
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| governor | `cpupower frequency-info` | performance | 오브젝트 처리량 최적화 |
| C-states | `/sys/module/intel_idle/parameters/max_cstate` | 1 | 응답 시간 일관성 |

#### 메모리 최적화 (캐싱)
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| vm.swappiness | `/proc/sys/vm/swappiness` | 10 | 캐시 우선, 적당한 스왑 허용 |
| vm.dirty_ratio | `/proc/sys/vm/dirty_ratio` | 20 | 대량 오브젝트 쓰기 최적화 |
| vm.dirty_background_ratio | `/proc/sys/vm/dirty_background_ratio` | 10 | 백그라운드 쓰기 여유 |

#### 네트워크 (S3 API)
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| net.core.somaxconn | `/proc/sys/net/core/somaxconn` | 65535 | HTTP 연결 처리 |
| net.ipv4.tcp_tw_reuse | `/proc/sys/net/ipv4/tcp_tw_reuse` | 1 | 연결 재사용 최적화 |
| net.ipv4.ip_local_port_range | `/proc/sys/net/ipv4/ip_local_port_range` | 10000 65535 | 포트 범위 확장 |

#### 스토리지 최적화
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| I/O scheduler | `cat /sys/block/*/queue/scheduler` | none (SSD), mq-deadline (HDD) | S3 워크로드 특성 |
| read_ahead_kb | `cat /sys/block/*/queue/read_ahead_kb` | 1024 | 대용량 오브젝트 읽기 |
| nr_requests | `cat /sys/block/*/queue/nr_requests` | 256 | 적당한 큐 깊이 |

#### S3 서비스 확인
| 서비스 | 확인 방법 | 권장 설정 |
|--------|-----------|-----------|
| MinIO/RGW | `systemctl is-active minio` | 활성화 |
| S3 포트 | `ss -tlnp | grep ':9000'` | S3 API 포트 바인딩 |

---

## OS별 차이점

### CentOS 7 (kernel 3.10)
- `tuned-adm profile throughput-performance` 사용 권장
- systemd 버전 제한으로 일부 기능 제한
- 레거시 네트워크 스택 고려

### Ubuntu 22.04 (kernel 5.15+)
- 최신 네트워크 최적화 기능 활용 가능
- cgroup v2 지원
- io_uring 지원 확인

### Ubuntu 24.04 (kernel 6.8+)
- 최신 하드웨어 지원
- 향상된 NUMA 인식
- BBR v3 지원

### Rocky Linux 9 (kernel 5.14+)
- RHEL 9 호환성
- 최신 보안 기능
- 향상된 가상화 지원

## 심각도 분류

### Critical
- 성능에 직접적 영향 (50% 이상 성능 저하)
- 시스템 안정성 위험
- 보안 취약점

### Warning
- 성능 최적화 기회 (10-50% 성능 향상 가능)
- 모범 사례 위반
- 향후 문제 가능성

### Info
- 정보성 권장사항 (10% 미만 성능 향상)
- 환경 정보
- 구성 확인

이 규칙들은 지속적으로 업데이트되며, 실제 워크로드 테스트를 통한 검증이 필요합니다.

## 새로 추가된 규칙 카테고리 (Phase 7)

### OVS (Open vSwitch) 관련

#### Compute 역할
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| DPDK 초기화 | `ovs-vsctl get Open_vSwitch . other_config:dpdk-init` | true | VM 네트워크 성능 대폭 향상 |
| PMD CPU 마스크 | `ovs-vsctl get Open_vSwitch . other_config:pmd-cpu-mask` | configured | DPDK 스레드 전용 CPU 할당 |
| Hugepages | `/proc/meminfo \| grep HugePages_Total` | ≥1024 | DPDK 메모리 할당 필요 |

#### Network 역할
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| OVS 본딩 설정 | `ovs-vsctl list port \| grep bond_mode` | configured | OVS 레벨 고성능 본딩 |

### Network Bonding 관련

#### Network, Storage 역할
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| 본딩 모드 | `/sys/class/net/bond*/bonding/mode` | 802.3ad | 최대 대역폭 및 장애 복구 |
| LACP 속도 | `/sys/class/net/bond*/bonding/lacp_rate` | fast | 빠른 장애 감지 |
| 해시 정책 | `/sys/class/net/bond*/bonding/xmit_hash_policy` | layer3+4 | 균등한 트래픽 분산 |

#### Storage-Ceph 역할
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| 점보프레임 MTU | `/sys/class/net/bond*/mtu` | 9000 | 스토리지 트래픽 오버헤드 감소 |

### Docker 컨테이너 관련

#### Control, Storage-S3 역할
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| 스토리지 드라이버 | `docker info \| grep 'Storage Driver'` | overlay2 | 검증된 성능과 안정성 |
| Live Restore | `/etc/docker/daemon.json` | true | 데몬 재시작 시 컨테이너 유지 |
| 로그 로테이션 | `/etc/docker/daemon.json` | configured | 디스크 공간 관리 |

#### 공통 (Docker 사용 시)
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| IP 포워딩 | `/proc/sys/net/ipv4/ip_forward` | 1 | 컨테이너 네트워킹 필수 |
| iptables 브리지 | `/proc/sys/net/bridge/bridge-nf-call-iptables` | 1 | 네트워크 정책 적용 |
| inotify 감시 수 | `/proc/sys/fs/inotify/max_user_watches` | ≥1048576 | 다중 컨테이너 지원 |

### systemd 서비스 관리

#### 역할별 핵심 서비스 상태
- **Control**: etcd, kube-apiserver, kube-scheduler, kube-controller-manager, docker/containerd
- **Compute**: libvirtd, qemu-kvm, ovs-vswitchd, ovsdb-server, nova-compute  
- **Network**: haproxy, nginx, keepalived, ovs-vswitchd
- **Storage-Ceph**: ceph-osd@*, ceph-mon@*, ceph-mgr@*, ceph-mds@*
- **Storage-S3**: radosgw@*, nginx
- **공통**: chronyd/ntpd, rsyslog, auditd, firewalld/iptables, irqbalance, tuned

#### 시스템 설정
| 항목 | 수집 방법 | 권장값 | 근거 |
|------|-----------|--------|------|
| 실패한 유닛 수 | `systemctl list-units --failed` | 0 | 시스템 안정성 확보 |
| journald 스토리지 | `/etc/systemd/journald.conf` | persistent | 로그 영구 보존 |
| 기본 파일 제한 | `systemctl show --property=DefaultLimitNOFILE` | ≥65536 | 고성능 서비스 지원 |

## 설정 우선순위

### Critical (점수 15-25)
- OVS-DPDK 비활성화 (Compute)
- 핵심 서비스 중단 (모든 역할)
- Docker 스토리지 드라이버 문제

### Warning (점수 8-15) 
- 네트워크 본딩 모드 최적화
- Docker Live Restore 비활성화
- systemd 서비스 상태 이상

### Info (점수 3-8)
- OVS 기본 설정 확인
- 로그 로테이션 미설정
- journald 설정 최적화

## 호환성 노트

- **CentOS 7**: OVS/Docker 명령어 없으면 graceful skip
- **Ubuntu 22/24**: 모든 기능 지원
- **Rocky 9**: systemd v2 cgroup 지원