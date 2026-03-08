# 배포 가이드

실제 인프라에 infra-auditor를 배포할 때는 단순히 바이너리를 복사하는 것 이상의 고려사항들이 있습니다. 이 가이드는 수십 대부터 수천 대까지 다양한 규모의 환경에서 안정적으로 운영하는 방법을 다룹니다.

## 배포 전략 개요

infra-auditor는 두 가지 배포 모델을 지원합니다:

**에이전트 중심 배포**: 각 서버에서 독립적으로 점검하고 결과를 파일로 저장
**중앙 집중식 배포**: Aggregator 서버를 운영하고 모든 에이전트가 결과를 전송

어떤 방식을 선택할지는 인프라 규모와 관리 정책에 따라 달라집니다.

## 1. 바이너리 배포

### 다운로드 방식 (소규모)

10-50대 정도의 서버라면 직접 다운로드가 가장 간단합니다.

```bash
# 각 서버에서 실행
curl -L https://github.com/ecmoce/infra-auditor/releases/latest/download/infra-auditor-linux-amd64 \
  -o /usr/local/bin/infra-auditor
chmod +x /usr/local/bin/infra-auditor

# 동작 확인
/usr/local/bin/infra-auditor version
```

### SCP 일괄 배포 (중소규모)

```bash
#!/bin/bash
# deploy.sh

BINARY="./infra-auditor-linux-amd64"
SERVERS=(
  "web-01.company.com"
  "web-02.company.com"
  "db-01.company.com"
  # ... 서버 목록
)

for server in "${SERVERS[@]}"; do
  echo "Deploying to $server..."
  scp "$BINARY" "$server:/tmp/infra-auditor"
  ssh "$server" "sudo mv /tmp/infra-auditor /usr/local/bin/ && sudo chmod +x /usr/local/bin/infra-auditor"
  
  # 동작 확인
  ssh "$server" "/usr/local/bin/infra-auditor version" || echo "Failed on $server"
done
```

### Ansible 배포 (대규모)

수백 대 이상의 서버에는 Ansible이나 Salt 같은 구성 관리 도구를 사용합니다.

**playbook.yml**:
```yaml
---
- hosts: all
  become: true
  vars:
    infra_auditor_version: "2.0.0-go"
    infra_auditor_url: "https://github.com/ecmoce/infra-auditor/releases/download/v{{ infra_auditor_version }}/infra-auditor-linux-{{ ansible_architecture }}"
  
  tasks:
    - name: Download infra-auditor binary
      get_url:
        url: "{{ infra_auditor_url }}"
        dest: "/usr/local/bin/infra-auditor"
        mode: '0755'
        owner: root
        group: root
      
    - name: Verify installation
      command: /usr/local/bin/infra-auditor version
      register: version_check
      changed_when: false
      
    - name: Display version
      debug:
        msg: "{{ version_check.stdout }}"
```

실행:
```bash
ansible-playbook -i inventory playbook.yml
```

### 공유 NFS 배포

NFS 공유 스토리지가 있다면 한 곳에만 바이너리를 두고 모든 서버에서 실행할 수 있습니다.

```bash
# NFS 서버에서
sudo mkdir -p /shared/tools
sudo cp infra-auditor-linux-amd64 /shared/tools/infra-auditor
sudo chmod +x /shared/tools/infra-auditor

# 각 클라이언트에서
echo "/shared/tools/infra-auditor scan" > /etc/cron.d/infra-auditor
```

이 방법의 장점은 업데이트가 간단하다는 것입니다. 한 곳만 바꾸면 모든 서버가 새 버전을 사용합니다.

## 2. 정기 점검 자동화

### Cron 설정

**기본 설정** (일일 점검):
```bash
# /etc/cron.d/infra-auditor
0 2 * * * root /usr/local/bin/infra-auditor scan --output /var/log/infra-auditor/$(date +\%Y\%m\%d).json
```

**고급 설정** (역할별 다른 주기):
```bash
# Compute 노드 - 매 시간 (VM 성능 모니터링)
0 * * * * root /usr/local/bin/infra-auditor scan --role compute --categories cpu,memory --output /var/log/infra-auditor/hourly-$(date +\%Y\%m\%d\%H).json

# Storage 노드 - 매 6시간 (디스크 상태 모니터링)
0 */6 * * * root /usr/local/bin/infra-auditor scan --role storage-ceph --output /var/log/infra-auditor/storage-$(date +\%Y\%m\%d\%H).json

# Controller 노드 - 매일 (안정성 우선)
0 3 * * * root /usr/local/bin/infra-auditor scan --role controller --output /var/log/infra-auditor/daily-$(date +\%Y\%m\%d).json
```

### Systemd 타이머 (권장)

Cron보다 systemd 타이머를 사용하면 더 정밀한 제어와 로깅이 가능합니다.

**/etc/systemd/system/infra-auditor.service**:
```ini
[Unit]
Description=Infrastructure Auditor Scan
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/infra-auditor scan --output /var/log/infra-auditor/%i.json
User=root
StandardOutput=journal
StandardError=journal
```

**/etc/systemd/system/infra-auditor.timer**:
```ini
[Unit]
Description=Run infra-auditor daily
Requires=infra-auditor.service

[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=3600

[Install]
WantedBy=timers.target
```

활성화:
```bash
sudo systemctl daemon-reload
sudo systemctl enable infra-auditor.timer
sudo systemctl start infra-auditor.timer

# 상태 확인
sudo systemctl list-timers infra-auditor.timer
```

### 로그 로테이션

점검 결과가 쌓이면 디스크 공간이 부족해질 수 있습니다.

**/etc/logrotate.d/infra-auditor**:
```
/var/log/infra-auditor/*.json {
    daily
    missingok
    rotate 30
    compress
    notifempty
    create 644 root root
}
```

## 3. Aggregator 서버 운영

### 서버 사양

Aggregator 서버의 사양은 관리할 서버 수에 따라 결정됩니다:

**소규모 (1-100대)**:
- CPU: 2-4 코어
- RAM: 4-8GB
- 디스크: 100GB SSD
- 네트워크: 1Gbps

**중규모 (100-1000대)**:
- CPU: 4-8 코어
- RAM: 8-16GB
- 디스크: 500GB SSD
- 네트워크: 10Gbps

**대규모 (1000대 이상)**:
- CPU: 8-16 코어
- RAM: 32-64GB
- 디스크: 1TB+ SSD
- 네트워크: 10Gbps+

### Systemd 서비스 설정

**/etc/systemd/system/infra-auditor-aggregator.service**:
```ini
[Unit]
Description=Infrastructure Auditor Aggregator
After=network.target
StartLimitInterval=0

[Service]
Type=simple
Restart=always
RestartSec=5
User=infra-auditor
ExecStart=/usr/local/bin/infra-auditor serve \
  --host 0.0.0.0 \
  --port 8080 \
  --db-path /var/lib/infra-auditor/reports.db
ExecReload=/bin/kill -HUP $MAINPID
StandardOutput=journal
StandardError=journal
SyslogIdentifier=infra-auditor-aggregator

# 보안 강화
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/infra-auditor /var/log/infra-auditor

# 리소스 제한
LimitNOFILE=65536
MemoryMax=2G

[Install]
WantedBy=multi-user.target
```

사용자 및 디렉토리 생성:
```bash
# 전용 사용자 생성
sudo useradd --system --home /var/lib/infra-auditor --shell /bin/false infra-auditor

# 디렉토리 생성
sudo mkdir -p /var/lib/infra-auditor /var/log/infra-auditor
sudo chown infra-auditor:infra-auditor /var/lib/infra-auditor /var/log/infra-auditor

# 서비스 시작
sudo systemctl enable infra-auditor-aggregator
sudo systemctl start infra-auditor-aggregator
```

### 리버스 프록시 설정 (Nginx)

실제 운영 환경에서는 Nginx를 앞에 두고 SSL 종료, 로드 밸런싱, 캐싱을 처리하는 것이 일반적입니다.

**/etc/nginx/sites-available/infra-auditor**:
```nginx
upstream infra_auditor {
    server 127.0.0.1:8080;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name infra-auditor.company.com;

    # SSL 설정
    ssl_certificate /etc/ssl/certs/infra-auditor.crt;
    ssl_certificate_key /etc/ssl/private/infra-auditor.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-CHACHA20-POLY1305;
    ssl_prefer_server_ciphers off;

    # 보안 헤더
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    # 정적 파일 캐싱
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API 요청
    location /api/ {
        proxy_pass http://infra_auditor;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 큰 보고서 업로드 허용
        client_max_body_size 10M;
        proxy_request_buffering off;
    }

    # 웹 대시보드
    location / {
        proxy_pass http://infra_auditor;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 헬스 체크
    location /health {
        proxy_pass http://infra_auditor/api/health;
        access_log off;
    }
}

# HTTP에서 HTTPS로 리다이렉션
server {
    listen 80;
    server_name infra-auditor.company.com;
    return 301 https://$server_name$request_uri;
}
```

### 에이전트 설정 (중앙 전송)

각 서버의 에이전트가 Aggregator로 보고서를 전송하도록 설정합니다.

**/etc/infra-auditor/config.yaml**:
```yaml
# Aggregator 서버 정보
aggregator:
  url: "https://infra-auditor.company.com"
  api_key: "your-api-key-here"
  timeout: 30s

# 스캔 설정
scan:
  role: "auto"  # 자동 감지
  categories:
    - cpu
    - memory
    - network
    - storage
    - kernel
    - service

# 제출 설정
submission:
  enabled: true
  retry_count: 3
  retry_delay: 10s
  compress: true  # 대용량 보고서 압축

# 로깅
logging:
  level: "info"
  file: "/var/log/infra-auditor/agent.log"
```

Cron 설정:
```bash
# 매일 새벽 3시에 스캔 후 전송
0 3 * * * root /usr/local/bin/infra-auditor scan --config /etc/infra-auditor/config.yaml --submit
```

## 4. 모니터링 연동

### Prometheus 메트릭

Aggregator 서버는 Prometheus 형식의 메트릭을 노출합니다.

**메트릭 예시**:
```
# 서버별 컴플라이언스 점수
infra_auditor_compliance_score{server_id="web-01.company.com",role="compute"} 85.2

# 실패한 규칙 수
infra_auditor_failed_rules{server_id="web-01.company.com",category="network"} 3

# 스캔 실행 시간
infra_auditor_scan_duration_seconds{server_id="web-01.company.com"} 2.5

# Aggregator 상태
infra_auditor_server_status{component="api"} 1
infra_auditor_server_status{component="database"} 1
```

Prometheus 설정에 추가:
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'infra-auditor'
    static_configs:
      - targets: ['infra-auditor.company.com:8080']
    metrics_path: '/api/metrics'
    scrape_interval: 60s
```

### Grafana 대시보드

시각적 모니터링을 위한 Grafana 대시보드를 구성할 수 있습니다.

**주요 패널**:
- 전체 컴플라이언스 점수 트렌드
- 서버별/역할별 점수 분포
- 가장 많이 실패하는 규칙 TOP 10
- 스캔 성공률 및 응답시간
- 드리프트 감지 알림

### 알림 설정

중요한 이벤트에 대해서는 즉시 알림을 받아야 합니다.

**Alertmanager 규칙**:
```yaml
# alerts.yml
groups:
- name: infra-auditor
  rules:
  
  # 컴플라이언스 점수가 급격히 떨어진 경우
  - alert: ComplianceScoreDrop
    expr: decrease(infra_auditor_compliance_score[1h]) > 20
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "서버 {{ $labels.server_id }}의 컴플라이언스 점수가 급격히 하락했습니다"
      description: "지난 1시간 동안 {{ $value }}점 하락"

  # 스캔 실패
  - alert: ScanFailure
    expr: up{job="infra-auditor"} == 0
    for: 10m
    labels:
      severity: warning
    annotations:
      summary: "infra-auditor 스캔이 실패하고 있습니다"

  # 새로운 critical 이슈 발견
  - alert: NewCriticalIssue
    expr: increase(infra_auditor_failed_rules{severity="critical"}[24h]) > 0
    labels:
      severity: critical
    annotations:
      summary: "새로운 Critical 이슈가 발견되었습니다"
      description: "서버 {{ $labels.server_id }}에서 {{ $labels.rule_id }} 규칙 실패"
```

### ELK 스택 연동

로그 분석을 위해 Elasticsearch + Kibana와 연동할 수 있습니다.

**Filebeat 설정** (각 서버):
```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  paths:
    - /var/log/infra-auditor/*.json
  json.keys_under_root: true
  json.add_error_key: true
  fields:
    service: infra-auditor
    environment: production

output.elasticsearch:
  hosts: ["elasticsearch.company.com:9200"]
  index: "infra-auditor-%{+yyyy.MM.dd}"
```

## 5. 보안 고려사항

### 네트워크 보안

**방화벽 설정**:
```bash
# Aggregator 서버에서만 필요한 포트 개방
sudo ufw allow from 10.0.0.0/8 to any port 8080 comment 'infra-auditor aggregator'
sudo ufw allow from 172.16.0.0/12 to any port 8080
sudo ufw allow from 192.168.0.0/16 to any port 8080

# 외부 접근 차단 (reverse proxy 통해서만 접근)
sudo ufw deny from any to any port 8080
```

**API 키 관리**:
```bash
# 강력한 API 키 생성
openssl rand -hex 32 > /etc/infra-auditor/api-key.txt
chmod 600 /etc/infra-auditor/api-key.txt

# 환경변수로 설정
export INFRA_AUDITOR_API_KEY=$(cat /etc/infra-auditor/api-key.txt)
```

### 실행 권한 최소화

infra-auditor는 시스템 정보를 읽어야 하므로 root 권한이 필요합니다. 하지만 가능한 한 권한을 제한해야 합니다.

**sudoers 설정** (에이전트를 non-root로 실행하려는 경우):
```bash
# /etc/sudoers.d/infra-auditor
infra-auditor ALL=(root) NOPASSWD: /usr/local/bin/infra-auditor scan
```

**SELinux/AppArmor 정책**:
```bash
# SELinux에서 읽기 전용 컨텍스트 설정
sudo setsebool -P deny_execmem on
sudo chcon -t bin_t /usr/local/bin/infra-auditor
```

### 데이터 보호

**전송 중 암호화**: 
- 모든 통신은 HTTPS/TLS 1.2+ 사용
- API 키는 환경변수나 보안 볼트에 저장
- 보고서에 민감한 정보(비밀번호, 키 등) 포함 금지

**저장 중 암호화**:
```bash
# 데이터 디렉토리 암호화
sudo cryptsetup luksFormat /dev/sdb1
sudo cryptsetup open /dev/sdb1 infra-auditor-data
sudo mkfs.ext4 /dev/mapper/infra-auditor-data
sudo mount /dev/mapper/infra-auditor-data /var/lib/infra-auditor
```

**접근 제어**:
```bash
# 파일 권한 최소화
sudo chmod 700 /var/lib/infra-auditor
sudo chmod 640 /var/lib/infra-auditor/*.json
sudo chown -R infra-auditor:infra-auditor /var/lib/infra-auditor
```

### 감사 로깅

보안 감사를 위해 모든 중요한 작업을 로깅합니다.

**rsyslog 설정**:
```bash
# /etc/rsyslog.d/50-infra-auditor.conf
# infra-auditor 로그를 별도 파일로 분리
:programname, isequal, "infra-auditor" /var/log/infra-auditor/audit.log
& stop
```

**로그 예시**:
```json
{
  "timestamp": "2026-03-08T13:41:00Z",
  "event": "scan_started",
  "user": "root",
  "server_id": "web-01.company.com",
  "role": "compute",
  "ip_address": "192.168.1.100"
}
```

## 6. 대규모 환경 최적화

### 배치 처리

수천 대 서버를 관리할 때는 배치 처리로 부하를 분산합니다.

```bash
#!/bin/bash
# batch-scan.sh

# 서버 목록을 10개 그룹으로 나누어 순차 실행
TOTAL_SERVERS=1000
BATCH_SIZE=100

for ((i=0; i<$TOTAL_SERVERS; i+=$BATCH_SIZE)); do
  echo "Processing batch $((i/BATCH_SIZE + 1))..."
  
  # 병렬로 배치 실행
  for ((j=i; j<i+BATCH_SIZE && j<TOTAL_SERVERS; j++)); do
    ssh server-$(printf "%03d" $j) "/usr/local/bin/infra-auditor scan --submit" &
  done
  
  # 배치 완료 대기
  wait
  
  # 5분 간격으로 Aggregator 서버 부하 분산
  sleep 300
done
```

### 캐싱 전략

**Redis 캐싱**:
```bash
# 자주 조회되는 대시보드 데이터 캐싱
redis-cli set "dashboard:summary:$(date +%Y%m%d)" "$(curl -s http://localhost:8080/api/dashboard)"
redis-cli expire "dashboard:summary:$(date +%Y%m%d)" 3600  # 1시간 TTL
```

### 데이터 아카이빙

```bash
#!/bin/bash
# archive-old-reports.sh

# 90일 이상 된 보고서는 압축 저장
find /var/lib/infra-auditor -name "*.json" -mtime +90 -exec gzip {} \;

# 1년 이상 된 데이터는 S3에 백업 후 로컬 삭제
find /var/lib/infra-auditor -name "*.json.gz" -mtime +365 \
  -exec aws s3 cp {} s3://company-infra-auditor-archive/ \; \
  -exec rm {} \;
```

## 7. 문제 해결

### 일반적인 문제들

**문제: 에이전트가 시스템 정보를 읽을 수 없음**
```bash
# 권한 확인
ls -la /proc/meminfo /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor

# SELinux 컨텍스트 확인
ls -Z /usr/local/bin/infra-auditor

# 해결
sudo setsebool -P domain_can_mmap_files on
```

**문제: Aggregator 서버 응답 지연**
```bash
# 데이터베이스 크기 확인
du -sh /var/lib/infra-auditor/

# 메모리 사용량 확인
ps aux | grep infra-auditor

# 해결: 오래된 데이터 정리
find /var/lib/infra-auditor -mtime +30 -delete
```

**문제: 보고서 전송 실패**
```bash
# 네트워크 연결 확인
curl -v https://infra-auditor.company.com/api/health

# DNS 확인
nslookup infra-auditor.company.com

# 인증서 확인
openssl s_client -connect infra-auditor.company.com:443 -servername infra-auditor.company.com
```

### 성능 튜닝

Aggregator 서버가 느려진다면:

1. **메모리 증설**: 동시 처리되는 보고서 수에 비례
2. **SSD 사용**: 데이터베이스 I/O 성능 향상
3. **네트워크 대역폭**: 대용량 보고서 전송을 위해
4. **로드밸런싱**: 여러 Aggregator 서버 운영

이런 배포 전략과 운영 노하우들은 실제 프로덕션 환경에서 수백 대의 서버를 관리하면서 얻은 경험입니다. 처음에는 간단하게 시작해서 필요에 따라 점진적으로 복잡한 기능들을 추가하는 것을 권장합니다.