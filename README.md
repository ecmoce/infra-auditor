# infra-auditor

서버 성능을 끌어올리고 싶다면, 먼저 현재 상태를 정확히 알아야 합니다. infra-auditor는 리눅스 서버의 OS 튜닝 상태를 자동으로 점검하고, 역할별 최적화 권장사항을 제공하는 도구입니다.

## 왜 만들었는가?

대규모 클라우드 인프라를 운영하다 보면, 수백 대의 서버가 제각각 다른 설정으로 돌아가는 경우가 많습니다. 어떤 서버는 네트워크 버퍼가 기본값 그대로여서 100Gbps NIC을 달고도 실제로는 1Gbps급 성능만 나오고, 어떤 서버는 스왑이 활성화되어 있어 VM이 갑자기 느려지곤 합니다.

이런 문제를 하나씩 찾아 수정하는 대신, 체계적으로 점검하고 표준화할 수 있는 도구가 필요했습니다. infra-auditor는 그런 필요에서 출발했습니다.

## 30초 만에 시작하기

```bash
# 바이너리 다운로드
curl -L https://github.com/ecmoce/infra-auditor/releases/latest/download/infra-auditor-linux-amd64 -o infra-auditor
chmod +x infra-auditor

# 현재 서버 점검
./infra-auditor scan

# 결과가 JSON으로 출력되면서 문제점과 권장사항을 보여줍니다
```

단일 바이너리로 만들어서 복잡한 설치 과정 없이 어디서든 바로 실행할 수 있습니다.

## 설치 방법

### 바이너리 다운로드 (권장)

```bash
# 리눅스 AMD64
curl -L https://github.com/ecmoce/infra-auditor/releases/latest/download/infra-auditor-linux-amd64 -o infra-auditor

# 리눅스 ARM64
curl -L https://github.com/ecmoce/infra-auditor/releases/latest/download/infra-auditor-linux-arm64 -o infra-auditor

chmod +x infra-auditor
```

### 소스에서 빌드

```bash
git clone https://github.com/ecmoce/infra-auditor.git
cd infra-auditor
make build
```

Go 1.19+ 필요합니다.

### Docker로 실행

```bash
# 전체 스택 실행 (Agent + Aggregator + 웹 대시보드)
docker compose up -d

# 개별 서버 점검
docker run --rm -v /proc:/host/proc:ro -v /sys:/host/sys:ro \
  infra-auditor scan --role auto
```

## 사용법

### 단일 서버 점검

가장 기본적인 사용법입니다. 서버 역할을 자동 감지해서 해당하는 규칙들을 적용합니다.

```bash
# 자동 역할 감지로 점검
infra-auditor scan

# 특정 역할로 점검 (더 정확한 결과)
infra-auditor scan --role compute

# 특정 카테고리만 점검 (빠른 진단)
infra-auditor scan --categories network,memory

# 중요도가 높은 문제만 확인
infra-auditor scan --severity critical,high
```

### 여러 서버 관리 - Aggregator 활용

한 대씩 점검하는 건 소규모에서나 가능합니다. 수십 대가 넘으면 중앙에서 관리해야 합니다.

**1단계: Aggregator 서버 시작**

```bash
# 중앙 서버 실행
infra-auditor serve --port 8080

# 웹 대시보드: http://your-server:8080/dashboard
# API 문서: http://your-server:8080/docs
```

**2단계: 각 서버에서 Agent 실행**

```bash
# 점검 후 결과를 Aggregator로 전송
infra-auditor scan --submit-to http://aggregator:8080/api/reports
```

이렇게 하면 웹 대시보드에서 모든 서버의 상태를 한눈에 볼 수 있습니다. 어느 서버가 문제인지, 어떤 설정이 표준과 다른지 바로 알 수 있습니다.

### 변경 추적 - Drift Detection

서버 설정은 시간이 지나면서 조금씩 변합니다. 누군가 임시로 바꾼 설정이 그대로 남거나, 패키지 업데이트 때 설정이 초기화되거나 하는 일들이 생깁니다.

```bash
# 이전 보고서와 비교
infra-auditor drift --previous last-week.json --current today.json

# 변경된 항목들과 영향도를 보여줍니다
```

정기적으로 실행해서 설정 드리프트를 추적하면, 문제가 커지기 전에 미리 발견할 수 있습니다.

### 자동 수정 - Remediation

문제를 찾아주는 것도 좋지만, 수정하는 것까지 도와주면 더 좋겠죠. infra-auditor는 안전한 수정 스크립트를 자동으로 생성해줍니다.

```bash
# 수정 스크립트 생성
infra-auditor remediate --input report.json --output fix.sh

# 스크립트를 검토한 후 실행
bash fix.sh
```

생성된 스크립트는 백업과 롤백 기능이 포함되어 있어서, 문제가 생기면 쉽게 되돌릴 수 있습니다.

## 서버 역할별 최적화

모든 서버가 같은 설정으로 최적화될 수는 없습니다. 웹 서버와 데이터베이스 서버의 최적 설정은 완전히 다르니까요.

### Compute (가상화 호스트)
VM을 돌리는 서버들입니다. CPU 격리, Hugepages, NUMA 최적화가 핵심입니다.

```bash
infra-auditor scan --role compute
```

**중요한 체크 항목들:**
- CPU governor가 performance로 설정되어 있는가?
- Hugepages가 VM용으로 충분히 할당되었는가?
- 호스트 태스크와 VM이 서로 다른 CPU에서 돌고 있는가?
- KVM nested virtualization이 활성화되어 있는가?

### Storage-Ceph
Ceph 클러스터를 돌리는 서버들입니다. BlueStore 최적화와 네트워크 튜닝이 중요합니다.

```bash
infra-auditor scan --role storage-ceph
```

**중요한 체크 항목들:**
- I/O 스케줄러가 SSD에 맞게 설정되었는가? (none 권장)
- OSD 메모리 타겟이 적절한가? (8GB+ 권장)
- 클러스터 네트워크 버퍼가 충분한가? (64MB+ 권장)
- XFS 마운트 옵션이 최적화되어 있는가? (noatime 등)

### Network (로드밸런서)
트래픽을 받아서 분산하는 서버들입니다. 네트워크 처리량과 연결 수 최적화가 핵심입니다.

```bash
infra-auditor scan --role network
```

**중요한 체크 항목들:**
- 네트워크 링 버퍼가 충분한가? (4096+ 권장)
- TCP 연결 대기열이 적절한가? (somaxconn 65535)
- MTU가 점보 프레임으로 설정되었는가? (9000)
- IRQ가 여러 CPU에 분산되고 있는가?

### Controller (관리 노드)
API 서버, etcd, 스케줄러 등이 돌아가는 서버들입니다. 안정성과 응답성이 최우선입니다.

```bash
infra-auditor scan --role controller
```

### Storage-S3
오브젝트 스토리지를 돌리는 서버들입니다. 대용량 파일 처리 최적화가 중요합니다.

```bash
infra-auditor scan --role storage-s3
```

## 설정 방법

### 환경변수

```bash
# Aggregator 서버 주소
export INFRA_AUDITOR_SERVER=https://aggregator.internal:8080

# 로그 레벨
export INFRA_AUDITOR_LOG_LEVEL=info

# 서버 역할 고정 (자동 감지 비활성화)
export INFRA_AUDITOR_ROLE=compute
```

### 설정 파일

`/etc/infra-auditor/config.yaml`:
```yaml
server:
  host: "0.0.0.0"
  port: 8080
  database_path: "/var/lib/infra-auditor/reports.db"

agent:
  role: "auto"  # 또는 고정 역할
  categories:
    - cpu
    - memory
    - network
    - storage
  
  # 제외할 규칙들
  exclude_rules:
    - "hugepages.allocation"  # 메모리가 부족한 서버에서

submission:
  enabled: true
  server: "https://aggregator.internal:8080"
  interval: "1h"
```

## 실제 사용 시나리오

### 시나리오 1: 새 Compute 노드 100대 추가

클라우드 확장으로 VM 호스트 100대를 새로 추가했다면:

```bash
# 1. 표준 설정 스크립트 생성 (기준 서버에서)
infra-auditor scan --role compute --output standard.json
infra-auditor remediate --input standard.json --output setup.sh

# 2. 모든 신규 서버에 배포 (Ansible 등 활용)
for server in compute-{001..100}; do
  scp infra-auditor setup.sh $server:/tmp/
  ssh $server "cd /tmp && chmod +x infra-auditor setup.sh && ./setup.sh"
done

# 3. 적용 후 검증
for server in compute-{001..100}; do
  ssh $server "/tmp/infra-auditor scan --submit-to http://aggregator:8080/api/reports"
done
```

### 시나리오 2: 성능 문제 긴급 진단

갑자기 VM 성능이 느려졌다는 제보가 들어왔을 때:

```bash
# 문제 서버에서 빠른 진단
infra-auditor scan --severity critical --categories cpu,memory,network

# 정상 서버와 비교
infra-auditor drift --previous normal-server.json --current problem-server.json
```

보통은 CPU governor가 powersave로 바뀌었거나, 스왑이 활성화되어 있거나, hugepages가 줄어들어 있는 경우가 많습니다.

### 시나리오 3: 정기 점검 자동화

```bash
# crontab 추가
0 2 * * * /usr/local/bin/infra-auditor scan --submit-to http://aggregator:8080/api/reports

# 주간 드리프트 분석
0 3 * * 1 /usr/local/bin/infra-auditor drift --previous /var/log/infra-auditor/last-week.json --current /var/log/infra-auditor/this-week.json --output /var/log/infra-auditor/drift-$(date +%Y%m%d).json
```

## 아키텍처 개요

infra-auditor는 단순한 구조를 지향합니다. 복잡한 의존성 없이 어디서든 돌아갈 수 있도록 설계했습니다.

```
┌──────────────┐  HTTP   ┌─────────────────┐  Web   ┌─────────────┐
│    Agent     │────────▶│   Aggregator    │◀──────▶│ Dashboard   │
│ (각 서버)    │  JSON   │ (중앙 서버)      │  UI    │ (브라우저)   │
└──────────────┘         └─────────────────┘        └─────────────┘
       │                           │
   ┌───▼────┐                 ┌────▼────┐
   │ 수집기  │                 │  저장소  │
   └────────┘                 └─────────┘
```

**Agent**: 각 서버에서 실행되어 시스템 정보를 수집하고 규칙을 평가합니다. 정적 바이너리 하나로 구성되어 있어서 설치가 간단합니다.

**Aggregator**: 여러 Agent에서 온 보고서를 모아서 저장하고, 웹 대시보드와 API를 제공합니다. 트렌드 분석과 드리프트 감지도 여기서 처리합니다.

**Dashboard**: 브라우저에서 접근할 수 있는 웹 인터페이스입니다. 서버별 상태, 컴플라이언스 점수, 변경 히스토리 등을 시각적으로 보여줍니다.

## 기여하기

새로운 규칙이나 수집기를 추가하고 싶으시다면 `docs/CONTRIBUTING.md`를 참고하세요. 특히 새로운 하드웨어나 소프트웨어에 대한 최적화 규칙은 언제든 환영입니다.

## 라이선스

MIT License. 자유롭게 사용하고 수정하실 수 있습니다.

---

infra-auditor는 서버 성능 최적화를 체계화하고 자동화하려는 시도입니다. 완벽하지는 않지만, 실무에서 바로 쓸 수 있도록 실용성에 중점을 뒀습니다. 문제가 있거나 개선 아이디어가 있으시면 언제든 이슈를 올려주세요.