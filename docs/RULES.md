# 역할별 OS 튜닝 규칙

서버 튜닝은 단순히 설정값을 바꾸는 게 아닙니다. 각 서버의 역할과 하드웨어 환경을 이해하고, 그에 맞는 최적화를 해야 합니다. 이 문서는 infra-auditor가 왜 특정 설정을 확인하는지, 그리고 그 설정이 실제 성능에 어떤 영향을 미치는지 설명합니다.

## 네트워크 튜닝 - 모든 역할의 기본

### 왜 네트워크부터 시작하는가?

현대 서버는 네트워크 없이는 아무것도 할 수 없습니다. VM끼리 통신하고, 스토리지에 접근하고, API 요청을 처리하는 모든 일이 네트워크를 통해 일어납니다. 하지만 리눅스의 기본 설정은 아직도 1Gbps 시대에 맞춰져 있습니다.

### 수신 버퍼 크기의 중요성

**net.core.rmem_max**를 기본값 212KB 그대로 두면 어떤 일이 벌어질까요? 간단한 계산을 해보겠습니다.

100Gbps NIC 4장을 본딩해서 쓰는 환경에서, RTT가 1ms인 같은 랙 내 통신을 한다고 가정하면:

```
이론적 최대 throughput = 수신 버퍼 크기 / RTT
                       = 212KB / 1ms
                       = 212MB/s
```

하드웨어는 400Gbps(50GB/s)를 처리할 수 있는데, 커널 설정 때문에 212MB/s로 제한되는 겁니다. 이게 바로 "비싼 하드웨어를 사서 기본 설정으로 쓰는" 문제입니다.

**권장값: 64MB (67108864)**
- Ceph OSD 간 replication
- VM 라이브 마이그레이션  
- 데이터베이스 백업/복구
- 컨테이너 이미지 다운로드

이런 작업들이 실제로 100Gbps 대역폭을 활용할 수 있게 됩니다.

### TCP 연결 대기열 최적화

**net.core.somaxconn**의 기본값은 4096입니다. 이게 부족하면 어떻게 될까요?

웹 서버나 API 서버를 운영해보신 분들은 경험이 있을 겁니다. 갑자기 트래픽이 몰리면 연결 에러가 발생하기 시작합니다. 서버 자체는 여유가 있는데 새로운 연결을 받아들이지 못하는 상황이 생깁니다.

**권장값: 65535**

이렇게 설정하면 순간적으로 6만 개가 넘는 연결 요청이 들어와도 안정적으로 처리할 수 있습니다. 특히 마이크로서비스 아키텍처에서는 서비스 간 호출이 많아서 이런 설정이 중요합니다.

### TCP 혼잡 제어 알고리즘

**net.ipv4.tcp_congestion_control**을 아직도 'cubic'으로 쓰고 계신가요?

BBR(Bottleneck Bandwidth and Round-trip)은 Google이 개발한 최신 혼잡 제어 알고리즘입니다. 기존 CUBIC이 패킷 손실을 기반으로 대역폭을 조절한다면, BBR은 실제 네트워크 상황을 분석해서 최적의 전송 속도를 찾습니다.

실제 효과는:
- WAN 연결에서 10-25% 처리량 향상
- 지연 시간 감소
- 패킷 손실 상황에서의 안정성 향상

**권장값: bbr**

단, 커널 4.9+ 에서만 지원되므로 CentOS 7 같은 구형 시스템에서는 'htcp'나 'cubic'을 사용합니다.

## CPU 및 전력 관리

### CPU Governor의 선택

**CPU governor**는 전력 효율성과 성능 사이의 트레이드오프를 결정합니다.

'powersave'로 설정되어 있으면 어떨까요? VM이 갑자기 느려지는 현상을 경험해본 적이 있을 겁니다. 전력 절약을 위해 CPU 클럭이 낮아졌다가, 부하가 증가해도 즉시 올라가지 않기 때문입니다.

**ondemand vs performance**
- ondemand: 부하에 따라 동적 조절 (수백ms 지연)
- performance: 항상 최고 클럭 유지

데이터센터에서는 전력비보다 성능 예측 가능성이 더 중요합니다. VM 응답 시간이 들쭉날쭉하면 사용자 경험이 나빠지죠.

**권장값: performance**

### C-states 제어

깊은 C-state(C3, C6 등)는 전력을 절약하지만, 깨어나는 데 수십 마이크로초가 걸릴 수 있습니다. 고성능 컴퓨팅이나 실시간 처리가 중요한 환경에서는 이 지연이 문제가 될 수 있습니다.

**권장값: C1만 사용**
```bash
intel_idle.max_cstate=1
```

특히 Compute 노드에서는 VM의 실시간성을 보장하기 위해 이런 설정이 필요합니다.

## 메모리 관리 최적화

### 스왑 정책

**vm.swappiness**의 기본값은 60입니다. 이는 메모리 사용률이 40%만 넘어도 스왑을 사용하기 시작한다는 뜻입니다.

서버에서 스왑이 발생하면:
- 디스크 I/O가 발생해서 전체 시스템 성능 저하
- VM의 메모리가 스왑되면 심각한 성능 저하
- 데이터베이스 버퍼가 스왑되면 쿼리 성능 급감

**권장값: 1**

완전히 0으로 설정하지 않는 이유는 커널의 OOM killer가 너무 공격적으로 동작할 수 있기 때문입니다. 1로 설정하면 정말로 메모리가 부족한 상황에서만 최소한의 스왑을 사용합니다.

### Dirty Page 관리

**vm.dirty_ratio**와 **vm.dirty_background_ratio**는 메모리에 쌓인 더티 페이지를 디스크에 언제 쓸지 결정합니다.

기본값(dirty_ratio=20, dirty_background_ratio=10)은 메모리의 20%까지 더티 페이지를 허용합니다. 32GB RAM 서버라면 6.4GB의 데이터가 메모리에만 있고 디스크에는 안 써진 상태가 될 수 있습니다.

문제는 시스템이 갑자기 shutdown되거나 crash가 발생할 때입니다. 6GB의 데이터를 잃을 수 있습니다.

**권장값: dirty_ratio=15, dirty_background_ratio=5**

더 자주 디스크에 쓰기는 하지만, 데이터 안정성이 향상됩니다. SSD 환경에서는 성능 저하도 거의 없습니다.

### Transparent Huge Pages

**THP(Transparent Huge Pages)**는 메모리 관리 효율성을 높이기 위한 기능이지만, 예상치 못한 문제를 일으킬 수 있습니다.

데이터베이스(Redis, MongoDB, PostgreSQL 등)에서는 THP 때문에 갑작스러운 지연이 발생할 수 있습니다. 작은 메모리 할당 요청이 2MB 페이지를 할당받으면서 불필요한 메모리 사용과 fragmentation이 발생하기 때문입니다.

**역할별 권장값:**
- Database/Cache 서버: **never**
- Compute 노드: **madvise** (명시적 hugepage 사용)
- 일반 서버: **madvise**

## 스토리지 I/O 최적화

### I/O 스케줄러 선택

스토리지 종류에 따라 최적의 I/O 스케줄러가 다릅니다.

**SSD/NVMe에서 왜 'none'인가?**

전통적인 HDD는 헤드가 움직여서 데이터를 읽어야 하므로, 요청을 재정렬해서 헤드 이동을 최소화하는 것이 중요했습니다. 하지만 SSD는 랜덤 접근 비용이 거의 없습니다.

오히려 커널에서 I/O를 재정렬하려고 하면:
- 불필요한 지연 발생
- CPU 오버헤드 증가
- 복잡한 스케줄링 로직으로 인한 버그 위험

**권장값:**
- NVMe: **none**
- SSD: **none** 또는 **noop**
- HDD: **mq-deadline** 또는 **cfq**

### Read-ahead 설정

**read_ahead_kb**는 순차 읽기 패턴을 감지했을 때 미리 얼마나 많은 데이터를 읽어올지 결정합니다.

기본값은 128KB인데, 이는 HDD 시대의 설정입니다. SSD에서는 더 큰 값을 사용해도 성능상 불이익이 없고, 특정 워크로드에서는 성능 향상을 볼 수 있습니다.

**권장값:**
- 일반 서버: **512KB**
- Ceph OSD: **512KB** (오브젝트 크기와 맞춤)
- 스트리밍/백업 서버: **1024KB**

## 역할별 전문 튜닝

### Compute 노드 - 가상화 최적화

Compute 노드는 VM을 실행하는 서버입니다. 호스트와 게스트 간의 리소스 경합을 최소화하는 것이 핵심입니다.

**CPU 격리 (isolcpus)**
```bash
isolcpus=0,1 rcu_nocbs=0,1 nohz_full=2-47
```

CPU 0, 1은 호스트 태스크(인터럽트 처리, 시스템 데몬 등)에만 사용하고, 나머지 코어는 VM 전용으로 예약합니다. 이렇게 하면:
- VM 성능의 예측 가능성 향상
- 호스트 작업이 VM에 미치는 영향 최소화
- NUMA locality 개선

**Hugepages 설정**

일반적으로 VM은 큰 메모리 블록을 사용합니다. 4KB 페이지를 사용하면:
- Page table 크기 증가 (메모리 오버헤드)
- TLB miss 빈발 (성능 저하)
- 메모리 관리 오버헤드 증가

2MB 또는 1GB hugepage를 사용하면 이런 문제들이 크게 개선됩니다.

**KVM nested virtualization**
```bash
echo 'Y' > /sys/module/kvm_intel/parameters/nested
```

컨테이너 환경에서 VM을 실행하거나, VM 안에서 다시 VM을 실행해야 하는 경우가 있습니다. 중첩 가상화를 활성화하면 이런 상황에서도 하드웨어 가속을 사용할 수 있습니다.

### Storage-Ceph 노드 - 분산 스토리지 최적화

Ceph는 분산 스토리지 시스템으로, 네트워크와 스토리지 I/O가 모두 중요합니다.

**BlueStore 메모리 설정**

Ceph OSD는 BlueStore를 사용해서 데이터를 저장합니다. BlueStore는 내부적으로 RocksDB를 사용하는데, 이 DB의 캐시 크기가 성능에 결정적인 영향을 미칩니다.

**권장값: OSD당 8GB**

OSD가 많은 서버에서는 메모리 사용량을 계산해봐야 합니다:
- 12 OSD × 8GB = 96GB
- 시스템 예약 메모리: 8-16GB
- 최소 필요 메모리: 104-112GB

**클러스터 네트워크 최적화**

Ceph는 클라이언트 트래픽과 클러스터 내부 복제 트래픽이 분리되어 있습니다. 클러스터 네트워크에서는 대용량 데이터를 빠르게 전송해야 하므로:

```bash
# 클러스터 네트워크 인터페이스에 대해
echo 67108864 > /proc/sys/net/core/rmem_max  # 64MB
echo 67108864 > /proc/sys/net/core/wmem_max  # 64MB
```

**XFS 최적화**

OSD 데이터를 저장하는 파일시스템은 보통 XFS를 사용합니다:
```bash
mount -o noatime,largeio,inode64,swalloc /dev/sdb1 /var/lib/ceph/osd/
```

- **noatime**: 읽기 접근 시간 기록 안 함 (성능 향상)
- **largeio**: 대용량 I/O 최적화
- **inode64**: 64비트 inode 번호 사용 (대용량 파일시스템)
- **swalloc**: stripe width allocation (RAID 최적화)

### Network 노드 - 로드밸런서 최적화

Network 노드는 외부 트래픽을 받아서 내부 서버들에게 분산하는 역할을 합니다.

**연결 추적 최적화**

로드밸런서는 수십만 개의 동시 연결을 처리해야 할 수 있습니다. 리눅스의 연결 추적(conntrack) 테이블이 부족하면 새로운 연결이 거부됩니다.

```bash
echo 1048576 > /proc/sys/net/netfilter/nf_conntrack_max  # 100만 연결
```

**TCP TIME_WAIT 최적화**

웹 트래픽 처리에서는 짧은 연결이 많습니다. 연결이 종료된 후 TIME_WAIT 상태로 머무르는 시간이 길면 포트가 고갈될 수 있습니다.

```bash
echo 1 > /proc/sys/net/ipv4/tcp_tw_reuse  # TIME_WAIT 소켓 재사용
echo 10000 65535 > /proc/sys/net/ipv4/ip_local_port_range  # 포트 범위 확장
```

**NIC 하드웨어 최적화**

고성능 NIC(Mellanox ConnectX 등)을 사용할 때는 하드웨어 기능을 최대한 활용해야 합니다:

```bash
# 링 버퍼 크기 증가
ethtool -G eth0 rx 4096 tx 4096

# 멀티큐 활성화
ethtool -L eth0 combined 8

# 점보 프레임 활성화 (내부 네트워크)
ip link set eth0 mtu 9000
```

**RSS(Receive Side Scaling) 설정**

멀티코어 CPU에서 네트워크 처리를 병렬화하려면 RSS 설정이 중요합니다:

```bash
# 각 RX 큐를 다른 CPU에 할당
echo 1 > /sys/class/net/eth0/queues/rx-0/rps_cpus
echo 2 > /sys/class/net/eth0/queues/rx-1/rps_cpus
echo 4 > /sys/class/net/eth0/queues/rx-2/rps_cpus
echo 8 > /sys/class/net/eth0/queues/rx-3/rps_cpus
```

### Controller 노드 - 관리 서비스 최적화

Controller 노드는 API 서버, 스케줄러, etcd 같은 관리 서비스가 실행됩니다. 안정성과 응답성이 최우선입니다.

**etcd 최적화**

etcd는 클러스터 상태를 저장하는 분산 데이터베이스입니다. 디스크 I/O 지연이 전체 클러스터 성능에 영향을 미칩니다:

```bash
# 스왑 완전 비활성화
echo 0 > /proc/sys/vm/swappiness

# THP 비활성화 (etcd는 작은 객체를 많이 사용)
echo never > /sys/kernel/mm/transparent_hugepage/enabled

# 디스크 I/O 우선순위
ionice -c1 -n4 etcd
```

**API 서버 네트워크 최적화**

Kubernetes API 서버는 수천 개의 동시 연결을 처리합니다:

```bash
echo 65535 > /proc/sys/net/core/somaxconn
echo 16777216 > /proc/sys/net/core/rmem_max
echo 16777216 > /proc/sys/net/core/wmem_max
```

### Storage-S3 노드 - 오브젝트 스토리지 최적화

S3 호환 스토리지(MinIO, Ceph RGW 등)를 실행하는 노드입니다.

**대용량 파일 처리 최적화**

오브젝트 스토리지는 큰 파일을 많이 다룹니다. 읽기 버퍼와 네트워크 설정을 그에 맞게 조정해야 합니다:

```bash
# read-ahead 증가
echo 1024 > /sys/block/*/queue/read_ahead_kb

# TCP 버퍼 증가
echo "4096 87380 16777216" > /proc/sys/net/ipv4/tcp_rmem
echo "4096 65536 16777216" > /proc/sys/net/ipv4/tcp_wmem
```

**캐시 최적화**

S3 서비스는 메모리 캐싱에 크게 의존합니다. 페이지 캐시를 최대한 활용하도록 설정:

```bash
# dirty ratio를 높여서 쓰기 버퍼링 증가
echo 20 > /proc/sys/vm/dirty_ratio
echo 10 > /proc/sys/vm/dirty_background_ratio

# 캐시 메모리 재활용 정책
echo 1 > /proc/sys/vm/overcommit_memory
```

## OS별 특별 고려사항

### CentOS 7 (kernel 3.10)

구형 커널이지만 아직 많이 사용되고 있습니다. 최신 기능은 사용할 수 없지만, 기본적인 튜닝은 충분히 가능합니다:

- BBR 불가 → htcp 사용
- BPF 기능 제한 → 전통적인 네트워크 툴 사용
- 일부 sysctl 파라미터 미지원

### Ubuntu 22.04/24.04

최신 기능을 모두 활용할 수 있습니다:
- BBR v1/v2 지원
- 향상된 cgroup v2
- io_uring 지원
- 최신 하드웨어 드라이버

### Rocky Linux 9

RHEL 9 호환으로 엔터프라이즈 환경에 적합:
- 보안 강화 기능
- 컨테이너 최적화
- 최신 가상화 기능

## 심각도 분류와 실제 영향

### Critical (중요)

시스템 안정성이나 보안에 직접적인 영향을 미치는 설정:
- CPU governor가 powersave (성능 50%+ 저하 가능)
- 스왑이 활성화된 상태에서 VM 실행 (응답시간 10배+ 증가)
- 네트워크 버퍼 부족으로 패킷 드롭

### High (높음)

성능에 상당한 영향을 미치지만 즉시 문제가 되지는 않는 설정:
- I/O 스케줄러 미최화 (20-30% 성능 저하)
- TCP 혼잡 제어 알고리즘 (WAN에서 10-25% 성능 저하)
- Hugepages 미설정 (메모리 집약적 워크로드에서 10-15% 성능 저하)

### Medium (보통)

최적화 기회이지만 대부분의 환경에서 눈에 띄는 차이는 없는 설정:
- dirty ratio 미조정
- 파일 핸들 제한
- 프로세스 수 제한

### Low (낮음) / Info (정보)

정보성 권장사항이나 특정 상황에서만 중요한 설정:
- 로그 로테이션 설정
- 시간 동기화
- 모니터링 에이전트 설정

## 실제 적용 시 주의사항

### 단계적 적용

모든 설정을 한 번에 바꾸지 마세요. 문제가 생겼을 때 원인을 찾기 어렵습니다:

1. **Critical 등급부터 적용**
2. **한 카테고리씩 적용** (네트워크 → CPU → 메모리 → 스토리지)
3. **적용 후 모니터링** (최소 24-48시간)
4. **문제가 없으면 다음 단계**

### 테스트 환경에서 검증

프로덕션에 적용하기 전에 테스트 환경에서 충분히 검증하세요:
- 성능 벤치마크 실행
- 스트레스 테스트
- 장애 시나리오 테스트

### 롤백 계획

설정 변경 전에 항상 롤백 계획을 세우세요:
```bash
# 백업
cp /etc/sysctl.conf /etc/sysctl.conf.backup.$(date +%Y%m%d)

# 적용
sysctl -p

# 롤백 (필요시)
cp /etc/sysctl.conf.backup.20260308 /etc/sysctl.conf
sysctl -p
```

### 모니터링 강화

설정 변경 후에는 모니터링을 강화해서 부작용을 빠르게 감지하세요:
- CPU 사용률 및 응답시간 모니터링
- 네트워크 처리량 및 에러율 모니터링
- 메모리 사용량 및 스왑 사용량 모니터링
- 디스크 I/O 및 응답시간 모니터링

이런 규칙들은 수년간의 실무 경험과 다양한 벤더(Red Hat, Ubuntu, Intel, AMD)의 권장사항을 종합한 것입니다. 하지만 모든 환경이 다르므로, 여러분의 특수한 요구사항에 맞게 조정해서 사용하시기 바랍니다.