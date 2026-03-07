# infra-auditor

OS 튜닝 점검 에이전트 — 서버 역할별 OS 설정을 자동으로 점검하고 최적화 권장사항을 제공합니다.

## 아키텍처

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
│   Agent      │────▶│   Aggregator    │◀────│   Frontend   │
│  (각 서버)   │     │  (FastAPI)      │     │  (React)     │
└─────────────┘     └─────────────────┘     └──────────────┘
```

- **Agent**: 시스템 정보 수집, 규칙 평가, JSON 리포트 생성
- **Aggregator**: 리포트 수신/저장, REST API, 대시보드 데이터 제공
- **Frontend**: React + TypeScript + Tailwind CSS 웹 대시보드

## 지원 환경

| OS | 버전 | 상태 |
|---|---|---|
| Ubuntu | 22.04, 24.04 | ✅ |
| CentOS | 7 | ✅ |
| Rocky Linux | 9 | ✅ |

## 빠른 시작

### 설치 (개발)

```bash
# Python 패키지
pip install -e ".[dev,server]"

# Frontend
cd frontend && npm ci
```

### Agent 실행

```bash
# 전체 스캔 (역할 자동 감지)
infra-auditor scan

# 역할 지정 + 파일 저장
infra-auditor scan --role compute -o report.json

# 요약 출력
infra-auditor scan --format summary
```

### Aggregator 실행

```bash
# 서버 시작 (기본 포트 8443)
infra-auditor-server

# 환경변수로 설정
INFRA_AUDITOR_PORT=9000 infra-auditor-server
```

### Frontend 실행 (개발)

```bash
cd frontend
npm run dev
# → http://localhost:5173
```

## Docker

### 전체 스택 실행

```bash
# 빌드 & 실행
docker compose up -d

# 확인
# - Frontend: http://localhost:3000
# - API:      http://localhost:8443/api/v1/health
# - Docs:     http://localhost:8443/docs

# 중지
docker compose down -v
```

### 통합 테스트

```bash
# Docker 환경에서 전체 통합 테스트 실행
make docker-test
```

이 명령은:
1. 모든 컨테이너 빌드 (aggregator, frontend, 4개 OS agent)
2. 각 OS에서 Agent 실행 → 리포트 생성 → Aggregator 전송
3. API 응답 검증 (health, dashboard, compliance, reports)
4. Frontend 접근성 확인
5. 완료 후 정리

### 개별 이미지 빌드

```bash
# Aggregator
docker build -f Dockerfile.aggregator -t infra-auditor-aggregator .

# Frontend
docker build -f Dockerfile.frontend -t infra-auditor-frontend .

# Agent (OS별)
docker build -f Dockerfile.agent --build-arg BASE_IMAGE=ubuntu:22.04 -t agent-ubuntu22 .
docker build -f Dockerfile.agent --build-arg BASE_IMAGE=rockylinux:9 -t agent-rocky9 .
```

## API

| Endpoint | Method | 설명 |
|---|---|---|
| `/api/v1/health` | GET | 서비스 상태 |
| `/api/v1/reports` | POST | 리포트 제출 |
| `/api/v1/reports` | GET | 리포트 목록 |
| `/api/v1/reports/{server_id}` | GET | 서버별 리포트 |
| `/api/v1/dashboard` | GET | 대시보드 요약 |
| `/api/v1/compliance` | GET | 컴플라이언스 현황 |

## 개발

```bash
# 테스트
make test

# 린트
make lint

# 벤치마크
make benchmark

# 전체 정리
make clean
```

## CI/CD

GitHub Actions로 자동화:
- **Python 테스트**: pytest + coverage (Python 3.10, 3.12)
- **Frontend 빌드**: TypeScript 컴파일 + Vite 빌드
- **Docker 빌드**: 이미지 빌드 검증
- **릴리즈**: `v*` 태그 push 시 GitHub Release 자동 생성

## 라이선스

MIT
