# infra-auditor 언어 선택 분석 보고서

**작성일:** 2026-03-08  
**목적:** Python 기반 infra-auditor의 언어 재선정을 위한 기술 분석

## 1. 배경 및 현재 상황

### 1.1 Python의 한계점

현재 Python 기반 infra-auditor는 다음과 같은 운영 환경 문제를 겪고 있습니다:

- **버전 파편화**: CentOS 7 (Python 3.6), Ubuntu 22.04 (Python 3.10), Rocky 9 (Python 3.9) 등 서버마다 상이한 버전
- **종속성 오염**: pip 패키지 설치 시 기존 시스템 패키지와 충돌 위험
- **격리 실행 한계**: Docker 없는 환경에서 virtualenv도 Python 버전에 의존
- **배포 복잡성**: 각 서버에 Python 런타임 및 패키지 설치 필요

### 1.2 요구사항 정의

| 요구사항 | 중요도 | 설명 |
|---------|--------|------|
| Zero dependency | 30% | 서버에 아무것도 설치하지 않고 바이너리 하나로 실행 |
| CentOS 7 glibc 2.17 호환 | 20% | 레거시 시스템 지원 |
| 크로스 컴파일 | 15% | macOS ARM → Linux x86_64/ARM64 빌드 |
| 시스템 파싱 생태계 | 15% | /proc, /sys, sysctl 파싱 라이브러리 |
| 팀 접근성 | 10% | 학습 곡선 및 유지보수성 |
| 빌드/개발 속도 | 10% | 개발 생산성 |

## 2. 언어별 심층 분석

### 2.1 Go (Golang)

#### ✅ 장점
- **Static Binary**: `CGO_ENABLED=0`로 완전 정적 바이너리 생성
- **Cross Compilation**: `GOOS=linux GOARCH=amd64 go build` 한 줄로 해결
- **풍부한 생태계**: 
  - `github.com/prometheus/procfs` - /proc 파싱의 표준
  - `github.com/shirou/gopsutil` - 크로스 플랫폼 시스템 정보
  - 표준 라이브러리로 JSON, HTTP, exec 모두 지원
- **glibc 호환성**: glibc 2.17 이상에서 문제없이 실행
- **빠른 컴파일**: 대규모 프로젝트도 초 단위 빌드
- **실증된 사례**: Prometheus, Telegraf, Consul, Nomad 등 인프라 도구의 표준

#### ⚠️ 단점
- **바이너리 크기**: 10-15MB (최소화해도 5MB 이상)
- **메모리 사용량**: GC로 인한 메모리 오버헤드
- **런타임 의존성**: CGO 사용 시 glibc 동적 링크 필요

#### 구체적 구현 방법
```bash
# 정적 바이너리 빌드 (CGO 없음)
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o infra-auditor

# CGO 필요 시 musl 정적 링크
CGO_ENABLED=1 GOOS=linux GOARCH=amd64 CC="zig cc -target x86_64-linux-musl" go build
```

### 2.2 Rust

#### ✅ 장점
- **완전 정적 바이너리**: musl 타겟으로 glibc 종속성 완전 제거
- **메모리 안전성**: 컴파일 타임 메모리 안전성 보장
- **성능**: C 수준의 실행 성능
- **바이너리 크기**: opt-level="z"로 최적화 시 Go보다 작음
- **크로스 컴파일**: cargo-cross로 안정적 지원

#### ⚠️ 단점
- **학습 곡선**: 소유권 개념, 라이프타임 등 복잡한 개념
- **컴파일 시간**: Go 대비 5-10배 느린 빌드 속도
- **생태계**: 시스템 파싱 라이브러리가 Go 대비 제한적
- **개발 속도**: 러닝 커브로 인한 초기 개발 지연

#### 구체적 구현 방법
```bash
# musl 정적 바이너리
cargo build --release --target x86_64-unknown-linux-musl
# 또는 cargo-zigbuild로 glibc 2.17 타겟
cargo zigbuild --release --target x86_64-unknown-linux-gnu.2.17
```

### 2.3 C/C++

#### ✅ 장점
- **최소 바이너리 크기**: 1-2MB 수준
- **최고 성능**: 네이티브 머신 코드
- **glibc 호환성**: 직접 glibc 버전 제어 가능
- **무제한 제어**: 시스템 저수준 접근

#### ⚠️ 단점
- **메모리 안전성**: 수동 메모리 관리로 인한 버그 위험
- **개발 생산성**: 메모리 관리, 문자열 처리 등 보일러플레이트 코드
- **크로스 컴파일**: 복잡한 툴체인 설정 필요
- **JSON 처리**: 서드파티 라이브러리 필요

### 2.4 Zig

#### ✅ 장점
- **"Better C"**: C의 성능 + 모던 언어 기능
- **뛰어난 크로스 컴파일**: `zig cc`로 C/Go CGO 크로스 컴파일까지 지원
- **작은 바이너리**: C 수준
- **glibc 버전 제어**: `zig cc -target x86_64-linux-gnu.2.17` 명시적 지원

#### ⚠️ 단점
- **신생 언어**: 아직 1.0 미출시 (0.11.0)
- **제한적 생태계**: 시스템 모니터링 라이브러리 부족
- **팀 접근성**: 학습 자료 및 경험자 부족
- **안정성**: API 변경 가능성

### 2.5 Shell Script

#### ✅ 장점
- **Zero dependency**: bash 4.x는 모든 리눅스에 기본 설치
- **즉시 실행**: 컴파일 불필요
- **높은 접근성**: 모든 시스템 관리자가 이해 가능

#### ⚠️ 단점
- **복잡한 로직 한계**: 조건부 처리, 데이터 구조 처리 어려움
- **JSON 생성**: jq 의존성 또는 복잡한 문자열 조합
- **에러 처리**: 제한적인 예외 처리
- **유지보수**: 대규모 로직에서 가독성 저하

## 3. 실제 인프라 도구 사례 분석

### 3.1 Go 생태계
- **Prometheus ecosystem**: node_exporter, alertmanager - "인프라 모니터링의 표준"
- **HashiCorp stack**: Consul, Nomad, Terraform - "단순성과 안정성 우선"
- **Telegraf** (InfluxData): "다양한 입력 소스 지원"

**선택 이유**: 빠른 개발, 크로스 플랫폼, 단일 바이너리 배포

### 3.2 다른 언어들
- **osquery** (C++): "최고 성능 필요, 복잡한 쿼리 엔진"
- **Lynis** (Shell): "간단한 보안 체크, 스크립트 접근성"
- **Ansible** (Python): 현재와 같은 문제 (버전 파편화, 의존성 지옥)

### 3.3 패턴 분석
최근 인프라 도구들이 Go를 선택하는 이유:
1. **운영 편의성**: 단일 바이너리로 배포 복잡성 해결
2. **개발 속도**: 빠른 프로토타이핑과 안정적 배포
3. **생태계**: 검증된 시스템 파싱 라이브러리
4. **팀 확장성**: 러닝 커브가 낮아 신규 개발자 투입 용이

## 4. 언어별 종합 평가

| 항목 | Go | Rust | C | Zig | Shell |
|------|----|----|----|----|-------|
| **Static Binary (30%)** | 9/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| **glibc 2.17 호환 (20%)** | 9/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| **크로스 컴파일 (15%)** | 10/10 | 8/10 | 6/10 | 10/10 | 10/10 |
| **시스템 파싱 생태계 (15%)** | 10/10 | 7/10 | 6/10 | 5/10 | 5/10 |
| **팀 접근성 (10%)** | 9/10 | 6/10 | 7/10 | 5/10 | 9/10 |
| **빌드/개발 속도 (10%)** | 9/10 | 6/10 | 6/10 | 8/10 | 10/10 |
| **가중 평균** | **9.2** | **8.2** | **7.6** | **7.8** | **8.5** |

## 5. 최종 권고사항

### 🏆 **선택: Go (Golang)**

#### 선택 근거
1. **운영 요구사항 완벽 충족**: CGO_ENABLED=0로 완전 정적 바이너리
2. **검증된 인프라 생태계**: Prometheus, Telegraf 등과 동일한 선택
3. **개발 생산성**: 빠른 컴파일, 간단한 문법, 풍부한 표준 라이브러리
4. **크로스 플랫폼 우수성**: macOS ARM → Linux x86_64 원클릭 빌드
5. **팀 확장성**: 기존 Python 팀이 비교적 쉽게 학습 가능

#### 비즈니스 임팩트
- **즉시 효과**: 서버별 Python 환경 차이 문제 완전 해결
- **운영 비용 절감**: 패키지 설치, 환경 관리 불필요
- **확장성**: 수천 대 서버 동시 실행 가능
- **유지보수성**: 업계 표준 도구와 동일한 기술 스택

## 6. Go 기반 프로젝트 구조 설계

### 6.1 디렉토리 구조
```
infra-auditor/
├── cmd/
│   └── infra-auditor/
│       └── main.go              # 엔트리포인트
├── internal/
│   ├── audit/
│   │   ├── cpu.go              # CPU 튜닝 점검
│   │   ├── memory.go           # 메모리 튜닝 점검
│   │   ├── network.go          # 네트워크 튜닝 점검
│   │   └── storage.go          # 스토리지 튜닝 점검
│   ├── collector/
│   │   ├── procfs.go           # /proc 파일시스템 수집
│   │   ├── sysfs.go            # /sys 파일시스템 수집
│   │   └── sysctl.go           # sysctl 파라미터 수집
│   ├── reporter/
│   │   ├── json.go             # JSON 리포트 생성
│   │   └── html.go             # HTML 리포트 생성
│   └── config/
│       └── rules.go            # 점검 규칙 정의
├── pkg/
│   └── system/                 # 재사용 가능한 시스템 유틸리티
├── go.mod
├── go.sum
├── Makefile
└── README.md
```

### 6.2 주요 라이브러리
```go
// go.mod 예상 의존성
module github.com/yourorg/infra-auditor

go 1.21

require (
    github.com/prometheus/procfs v0.12.0    // /proc 파싱
    github.com/shirou/gopsutil/v3 v3.23.9   // 시스템 정보
    github.com/spf13/cobra v1.7.0           // CLI 프레임워크
    gopkg.in/yaml.v3 v3.0.1                 // 설정 파일
)
```

### 6.3 핵심 구현 예시
```go
// internal/collector/procfs.go
package collector

import (
    "github.com/prometheus/procfs"
)

func CollectMemInfo() (*procfs.Meminfo, error) {
    fs, err := procfs.NewDefaultFS()
    if err != nil {
        return nil, err
    }
    return fs.Meminfo()
}

// internal/audit/memory.go
package audit

func AuditSwappiness(meminfo *procfs.Meminfo) AuditResult {
    // Python의 swappiness 점검 로직을 Go로 변환
    // vm.swappiness 값 확인 및 권고사항 생성
}
```

## 7. 빌드 파이프라인 설계

### 7.1 Makefile
```makefile
# Makefile
GOOS_TARGETS = linux
GOARCH_TARGETS = amd64 arm64
OUTPUT_DIR = dist

.PHONY: build build-all clean

build:
	CGO_ENABLED=0 go build -ldflags="-s -w" -o infra-auditor ./cmd/infra-auditor

build-all:
	@for os in $(GOOS_TARGETS); do \
		for arch in $(GOARCH_TARGETS); do \
			echo "Building $$os/$$arch..."; \
			CGO_ENABLED=0 GOOS=$$os GOARCH=$$arch go build \
				-ldflags="-s -w" \
				-o $(OUTPUT_DIR)/infra-auditor-$$os-$$arch \
				./cmd/infra-auditor; \
		done \
	done

test:
	go test ./...

clean:
	rm -rf $(OUTPUT_DIR)
	rm -f infra-auditor
```

### 7.2 CI/CD (GitHub Actions 예시)
```yaml
# .github/workflows/build.yml
name: Build and Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-go@v4
        with:
          go-version: '1.21'
      
      - name: Build for all platforms
        run: make build-all
      
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: dist/*
```

## 8. 마이그레이션 계획

### 8.1 Phase 1: 기반 구조 구축 (2주)
- Go 프로젝트 초기화 및 디렉토리 구조 생성
- 핵심 시스템 정보 수집 모듈 개발
  - `/proc/meminfo`, `/proc/cpuinfo` 파싱
  - `sysctl` 파라미터 수집
- 기본 CLI 인터페이스 구현

### 8.2 Phase 2: 점검 로직 이식 (3주)
- Python 코드의 점검 규칙을 Go로 변환
  - CPU 튜닝 점검 (governor, scaling, affinity)
  - 메모리 튜닝 점검 (swappiness, hugepages, oom)
  - 네트워크 튜닝 점검 (buffer sizes, congestion control)
  - 스토리지 튜닝 점검 (I/O scheduler, read-ahead)
- 유닛 테스트 작성

### 8.3 Phase 3: 리포팅 및 검증 (2주)
- JSON/HTML 리포트 생성 기능
- 기존 Python 버전과 결과 비교 검증
- 성능 벤치마크 및 최적화
- 문서화 완성

### 8.4 Phase 4: 프로덕션 배포 (1주)
- 선별된 서버군에서 파일럿 테스트
- 기존 Python 버전과 병렬 실행 검증
- 전체 서버군 롤아웃
- Python 버전 단계적 제거

## 9. 리스크 및 대응방안

### 9.1 기술 리스크
| 리스크 | 확률 | 영향 | 대응방안 |
|--------|------|------|----------|
| Go 학습곡선으로 인한 일정 지연 | 중 | 중 | 사전 Go 스터디, 간단한 POC 먼저 진행 |
| 기존 Python 로직 변환 누락 | 중 | 고 | 체계적 기능 매핑, 단위 테스트 커버리지 90%+ |
| 성능 이슈 발생 | 낮 | 중 | 벤치마크 기반 성능 검증, 프로파일링 도구 활용 |

### 9.2 운영 리스크
| 리스크 | 확률 | 영향 | 대응방안 |
|--------|------|------|----------|
| 새 버전 버그로 인한 오탐/미탐 | 중 | 고 | 기존 버전과 병렬 실행으로 검증 |
| 바이너리 호환성 문제 | 낮 | 중 | 다양한 환경에서 사전 테스트 |

## 10. 결론

**Go**는 infra-auditor의 모든 기술적 요구사항을 충족하는 최적의 선택입니다:

1. **Zero dependency 달성**: 완전 정적 바이너리로 Python 의존성 문제 근본 해결
2. **검증된 선택**: Prometheus, Telegraf 등 동일 도메인의 성공 사례
3. **실용적 접근**: 완벽함보다는 운영 환경의 실질적 문제 해결에 집중
4. **확장 가능성**: 향후 기능 확장 시에도 풍부한 생태계 활용 가능

이 선택으로 **서버 환경 의존성 문제를 완전히 해결**하고, **운영 복잡성을 대폭 줄이며**, **확장성 있는 아키텍처**를 확보할 수 있습니다.

---

**다음 단계**: Go 기반 POC(Proof of Concept) 개발을 통한 기술 검증 진행