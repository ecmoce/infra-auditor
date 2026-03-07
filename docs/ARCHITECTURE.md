# Infra-Auditor 아키텍처 설계

## 1. 시스템 개요

### 목적
온프레미스 AWS-like 클라우드 환경에서 수천 대 서버의 OS 튜닝 상태를 자동으로 점검하고, 역할별 최적화 권장사항을 제공하는 통합 모니터링 시스템

### 환경
- **지역**: 4개 지역 분산 배포
- **규모**: 수천 대 서버
- **역할**: Control, Compute, Network, Storage-Ceph, Storage-S3
- **OS**: CentOS 7, Ubuntu 22.04/24.04, Rocky Linux 9

## 2. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                              Aggregator                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   FastAPI       │  │    Database     │  │   Web UI        │  │
│  │   Server        │  │   (SQLite/      │  │   Dashboard     │  │
│  │                 │  │   PostgreSQL)   │  │                 │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────┬───────────────────────────────────────────┘
                          │ HTTPS/JSON Reports
                          │
    ┌─────────────────────────────────────────────────────────────────┐
    │                        Agents                                   │
    │ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
    │ │ Control │ │ Compute │ │ Network │ │ Ceph    │ │ S3      │ │
    │ │ Agent   │ │ Agent   │ │ Agent   │ │ Agent   │ │ Agent   │ │
    │ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │
    └─────────────────────────────────────────────────────────────────┘
```

## 3. 컴포넌트별 상세 설계

### 3.1 Agent (각 서버에 배포)

#### 구조
```python
infra-auditor/agent/
├── __init__.py
├── cli.py                 # CLI 진입점
├── config.py             # 설정 관리 (역할 자동 감지)
├── report.py             # 리포트 생성 엔진
├── collectors/           # OS 정보 수집기
│   ├── __init__.py
│   ├── base.py          # 기본 수집기 클래스
│   ├── hardware.py      # 하드웨어 정보 수집
│   ├── kernel.py        # 커널 파라미터 수집
│   ├── network.py       # 네트워크 설정 수집
│   ├── memory.py        # 메모리 설정 수집
│   ├── storage.py       # 스토리지 설정 수집
│   └── process.py       # 프로세스/서비스 수집
├── rules/               # 역할별 튜닝 규칙
│   ├── __init__.py
│   ├── base_rule.py     # 기본 규칙 클래스
│   ├── control.py       # Control 역할 규칙
│   ├── compute.py       # Compute 역할 규칙
│   ├── network.py       # Network 역할 규칙
│   ├── storage_ceph.py  # Ceph 역할 규칙
│   └── storage_s3.py    # S3 역할 규칙
└── utils/
    ├── __init__.py
    ├── system.py        # 시스템 유틸리티
    └── role_detector.py # 역할 자동 감지
```

#### 기능
1. **역할 자동 감지**
   - 실행 중인 프로세스 분석 (kvm, ceph-osd, haproxy 등)
   - 설치된 패키지 확인
   - 네트워크 포트 바인딩 상태 확인
   - 수동 설정 파일 지원

2. **데이터 수집**
   - CPU: governor, C-states, NUMA topology, CPU affinity
   - Memory: hugepages, swappiness, dirty ratios
   - Network: ring buffer, MTU, TCP parameters, bonding
   - Storage: I/O scheduler, readahead, mount options
   - Kernel: sysctl parameters, limits, security settings

3. **규칙 엔진**
   - 역할별 권장값과 현재값 비교
   - 심각도 레벨링 (critical/warning/info)
   - 컨텍스트 기반 권장사항 생성

4. **리포트 생성**
   - JSON 형태 표준화 리포트
   - 압축 및 전송 최적화
   - 에러 핸들링 및 부분 실패 대응

#### 배포 방식
```bash
# 패키지 설치 (Python 3.8+ 지원)
pip install infra-auditor

# 에이전트 실행
infra-auditor scan --role auto --output /tmp/report.json
infra-auditor scan --role compute --config /etc/infra-auditor.yml
infra-auditor submit --server https://aggregator.internal:8443
```

### 3.2 Aggregator Server

#### 구조
```python
infra-auditor/server/
├── __init__.py
├── main.py               # FastAPI 앱 진입점
├── aggregator.py         # 메인 집계 서비스
├── config.py             # 서버 설정
├── api/                  # API 엔드포인트
│   ├── __init__.py
│   ├── reports.py        # 리포트 수집 API
│   ├── dashboard.py      # 대시보드 API
│   └── admin.py          # 관리 API
├── models/               # 데이터 모델
│   ├── __init__.py
│   ├── server.py         # 서버 모델
│   ├── report.py         # 리포트 모델
│   └── compliance.py     # 컴플라이언스 모델
├── db/                   # 데이터베이스
│   ├── __init__.py
│   ├── connection.py     # DB 연결 관리
│   └── migrations/       # 스키마 마이그레이션
└── utils/
    ├── __init__.py
    ├── security.py       # 인증/암호화
    └── analytics.py      # 분석 엔진
```

#### 기능
1. **데이터 수집**
   - RESTful API를 통한 에이전트 리포트 수집
   - 배치 업로드 지원 (여러 서버 동시 전송)
   - 압축 해제 및 검증

2. **데이터 저장**
   - 시계열 데이터 저장 (compliance 변화 추적)
   - 메타데이터 인덱싱 (지역, 역할, OS별)
   - 데이터 압축 및 아카이빙

3. **분석 엔진**
   - 지역별/역할별 집계 분석
   - 이상치 탐지 (같은 역할 내 다른 설정)
   - 트렌드 분석 (설정 drift 감지)

4. **API 제공**
   - Dashboard용 API
   - 외부 시스템 연동 API
   - 관리 API (서버 관리, 규칙 업데이트)

### 3.3 Web Dashboard

#### 기능
1. **토폴로지 뷰**
   - 지역별 서버 맵 시각화
   - 역할별 color coding
   - 실시간 compliance 상태

2. **Compliance Heatmap**
   - 역할별 compliance 점수 히트맵
   - 클릭 시 상세 드릴다운
   - 필터링 (지역, OS, 시간범위)

3. **Drift Detection**
   - 이전 스캔 대비 변경사항 하이라이팅
   - 변경 히스토리 타임라인
   - 변경 원인 분석 힌트

4. **Remediation 도구**
   - 원클릭 remediation 스크립트 생성
   - Ansible playbook 자동 생성
   - 배치 적용 도구

5. **이상치 탐지**
   - 같은 역할 내 다른 설정 서버 하이라이팅
   - 표준화 권장사항 제시
   - 예외 승인 워크플로우

## 4. 통신 프로토콜

### 4.1 Agent → Aggregator
```
Protocol: HTTPS POST
Endpoint: /api/v1/reports
Content-Type: application/json
Authentication: API Key + TLS Client Certificate

Request Body:
{
  "server_id": "unique-server-identifier",
  "timestamp": "2024-03-07T07:48:00Z",
  "report": { ... } // 리포트 스키마 참조
}

Response:
{
  "status": "accepted",
  "report_id": "uuid",
  "next_scan_recommended": "2024-03-08T07:48:00Z"
}
```

### 4.2 Pull 방식 지원
```
Agent가 주기적으로 Aggregator에 체크인:
GET /api/v1/tasks/{server_id}

Response:
{
  "tasks": [
    {
      "task_id": "uuid",
      "type": "scan",
      "parameters": {
        "focus_areas": ["network", "storage"],
        "priority": "high"
      }
    }
  ]
}
```

## 5. 확장성 설계

### 5.1 수평 확장
- Aggregator: 로드밸런서 뒤 여러 인스턴스
- 데이터베이스: 샤딩/복제 지원
- 캐싱: Redis 클러스터 활용

### 5.2 성능 최적화
- 비동기 처리: 리포트 수집과 분석 분리
- 배치 처리: 시간대별 배치 집계
- 캐싱: 자주 조회되는 데이터 캐싱

## 6. 보안 설계

### 6.1 전송 보안
- TLS 1.3 필수
- 상호 인증 (클라이언트 인증서)
- API Key 기반 인증

### 6.2 데이터 보안
- 민감한 정보 마스킹
- 역할 기반 접근 제어 (RBAC)
- 감사 로깅

## 7. 운영 고려사항

### 7.1 배포 전략
- Docker 컨테이너 기반 배포
- Kubernetes 지원
- 롤링 업데이트

### 7.2 모니터링
- Prometheus 메트릭 노출
- 헬스체크 엔드포인트
- 로그 집계 (ELK 스택)

### 7.3 백업 및 복구
- 데이터베이스 정기 백업
- 설정 파일 버전 관리
- 재해 복구 절차

## 8. 개발 로드맵

### Phase 1: MVP (2-3개월)
- Agent 기본 수집 기능
- Aggregator 기본 API
- 간단한 웹 대시보드

### Phase 2: 고도화 (1-2개월)
- 고급 분석 기능
- Remediation 도구
- 성능 최적화

### Phase 3: 운영화 (1개월)
- 모니터링 완성
- 문서화
- 프로덕션 배포

이 아키텍처는 확장 가능하고 유지보수가 용이하도록 설계되었으며, 대규모 인프라 환경에서의 운영을 고려한 실용적인 접근 방식을 제공합니다.