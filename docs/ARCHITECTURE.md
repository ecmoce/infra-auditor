# infra-auditor 아키텍처 설계

## 왜 Go로 다시 만들었는가?

처음에는 Python으로 만들었습니다. 빠르게 프로토타입을 만들기에는 Python이 좋았지만, 실제 운영 환경에서 문제가 생기기 시작했습니다.

### Python 버전의 한계

**의존성 지옥**: 서버마다 Python 버전이 달랐습니다. CentOS 7은 Python 2.7, Ubuntu는 3.8, 새로운 Rocky Linux는 3.11이었죠. pip 패키지들도 버전 충돌이 자주 발생했습니다.

**느린 시작 시간**: import 시간만 3-4초가 걸렸습니다. cron으로 1분마다 체크하려고 하니까 비효율적이었죠.

**배포 복잡성**: virtualenv 설정하고, 의존성 설치하고, systemd 서비스 등록하고... 한 대면 몰라도 수백 대에 배포하기에는 너무 번거로웠습니다.

### Go 선택 이유

**단일 바이너리**: 정적 링크로 빌드하면 의존성이 전혀 없는 하나의 실행 파일이 나옵니다. 어떤 리눅스 배포판에든 그냥 복사해서 실행하면 됩니다.

**빠른 시작**: Go 프로그램은 즉시 시작됩니다. 0.1초 안에 점검을 시작할 수 있어서 cron job으로 쓰기에 완벽합니다.

**메모리 효율성**: Python 버전은 기본적으로 50-100MB RAM을 쓰고 시작했습니다. Go 버전은 5-10MB면 충분합니다.

**동시성**: 여러 수집기를 병렬로 실행해도 goroutine이 가볍게 처리합니다. 점검 시간이 절반으로 줄었습니다.

**컴파일 타임 검증**: 런타임 에러가 크게 줄었습니다. 특히 필드명 오타 같은 실수들이 컴파일 단계에서 잡힙니다.

## 단일 바이너리 설계 철학

하나의 바이너리로 Agent와 Aggregator 기능을 모두 제공합니다. 이게 처음에는 이상해 보일 수 있지만, 실제로는 매우 실용적입니다.

```bash
# Agent 모드로 실행 (각 서버에서)
./infra-auditor scan

# Aggregator 모드로 실행 (중앙 서버에서)  
./infra-auditor serve

# 유틸리티 기능들
./infra-auditor drift
./infra-auditor remediate
```

### 장점

**배포 간소화**: 파일 하나만 복사하면 됩니다. 버전 관리도 쉽고, 롤백도 파일 교체만 하면 끝입니다.

**일관성 보장**: Agent와 Aggregator가 같은 바이너리에서 나오니까 JSON 스키마나 API 호환성 문제가 없습니다.

**메모리 공유**: 규칙 엔진이나 타입 정의 같은 코드가 공유됩니다. 실제로 컴파일된 바이너리 크기가 6.6MB밖에 안 됩니다.

**개발 편의성**: 하나의 Go 모듈에서 모든 기능을 관리할 수 있어서 테스트와 디버깅이 훨씬 쉽습니다.

## 코어 파이프라인: Collector → Rules → Report

infra-auditor의 핵심은 간단한 3단계 파이프라인입니다.

### 1단계: Collector (데이터 수집)

```go
// 11개의 전문화된 수집기들이 병렬로 실행됩니다
collectors := []Collector{
    &CPUCollector{},
    &MemoryCollector{},
    &NetworkCollector{},
    &StorageCollector{},
    &KernelCollector{},
    &ServiceCollector{},
    &DockerCollector{},
    &BondingCollector{},
    &OVSCollector{},
    &SystemdCollector{},
    &HardwareCollector{},
}
```

각 수집기는 `/proc`, `/sys` 파일시스템에서 정보를 읽어오거나 시스템 명령어를 실행합니다. 에러가 발생하면 해당 수집기만 건너뛰고 나머지는 계속 진행합니다.

**예시: MemoryCollector**
```bash
/proc/meminfo          # 전체 메모리 정보
/proc/sys/vm/*         # 가상 메모리 설정
/sys/kernel/mm/        # 메모리 관리 파라미터
```

수집된 데이터는 구조체로 정리됩니다:
```go
type MemoryInfo struct {
    Total           uint64
    Available       uint64
    SwapTotal       uint64
    Swappiness      int
    DirtyRatio      int
    HugepagesTotal  int
    // ...
}
```

### 2단계: Rules Engine (규칙 평가)

수집된 데이터를 바탕으로 92개 이상의 규칙을 평가합니다. 규칙은 카테고리별, 역할별로 구조화되어 있습니다.

```go
type Rule interface {
    ID() string
    Name() string
    Description() string
    Category() Category
    Severity() Severity
    Applies(role Role, data *CollectedData) bool
    Check(data *CollectedData) *CheckResult
}
```

**역할별 규칙 필터링**: Compute 서버에는 가상화 관련 규칙이, Storage 서버에는 I/O 최적화 규칙이 적용됩니다. 관계없는 규칙은 아예 실행하지 않습니다.

**조건부 적용**: 하드웨어나 소프트웨어 환경에 따라 규칙을 다르게 적용합니다. 예를 들어 SSD가 없으면 SSD 관련 규칙은 건너뜁니다.

**권장값 계산**: 단순히 고정된 값을 체크하는 게 아니라, 시스템 상황에 맞게 권장값을 계산합니다. RAM 크기가 1TB면 min_free_kbytes도 그에 맞게 조정됩니다.

### 3단계: Report Generation (보고서 생성)

평가 결과를 JSON 형태의 표준화된 보고서로 만듭니다.

```json
{
  "metadata": {
    "server_id": "web-01.prod.company.com",
    "timestamp": "2026-03-08T13:41:00Z",
    "auditor_version": "2.0.0-go",
    "detected_role": "compute"
  },
  "summary": {
    "total_rules": 45,
    "failed_rules": 8,
    "compliance_score": 82.2
  },
  "results": [
    {
      "rule_id": "cpu.governor",
      "status": "failed",
      "severity": "high",
      "current_value": "powersave",
      "expected_value": "performance",
      "message": "CPU 성능이 제한될 수 있습니다",
      "remediation": "echo 'performance' > /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"
    }
  ]
}
```

보고서는 여러 용도로 활용됩니다:
- 즉시 화면 출력
- 파일 저장
- Aggregator 서버로 전송
- 드리프트 분석 입력
- 자동 수정 스크립트 생성 입력

## Aggregator 서버 아키텍처

중앙 집중식 관리를 위한 HTTP 서버입니다. 복잡한 데이터베이스 대신 파일 기반 저장소를 사용해서 단순성을 유지합니다.

### HTTP 서버 설계

```go
// Graceful shutdown 지원하는 HTTP 서버
server := &http.Server{
    Addr:         fmt.Sprintf("%s:%d", config.Host, config.Port),
    Handler:      router,
    ReadTimeout:  30 * time.Second,
    WriteTimeout: 30 * time.Second,
}

// API 라우팅
router.POST("/api/reports", handleReportSubmission)
router.GET("/api/reports", handleReportList)
router.GET("/api/reports/:server_id", handleServerReports)
router.GET("/api/dashboard", handleDashboard)
router.GET("/dashboard", serveDashboard)
```

### 데이터 저장 방식

복잡한 관계형 데이터베이스 대신 파일 기반 저장소를 선택했습니다. 이유는:

**단순성**: SQL 스키마 관리, 마이그레이션, 백업/복구가 훨씬 간단합니다.

**가벼움**: SQLite조차 없앴습니다. 바이너리만 있으면 모든 기능을 사용할 수 있습니다.

**투명성**: 저장된 데이터를 직접 들여다보기 쉽습니다. 디버깅이나 데이터 분석 시 유용합니다.

```
data/
├── servers/
│   ├── web-01.prod.company.com.json      # 서버별 최신 보고서
│   ├── db-01.prod.company.com.json
│   └── ...
├── history/
│   ├── 2026-03-08/                       # 날짜별 보관
│   │   ├── web-01.prod.company.com.json
│   │   └── ...
│   └── ...
└── dashboard.json                        # 대시보드용 집계 데이터
```

### 드리프트 분석 엔진

설정 변경을 추적하는 것은 대규모 인프라에서 매우 중요합니다. 누가, 언제, 무엇을 바꿨는지 알 수 없으면 문제 해결이 어렵습니다.

```go
type DriftAnalyzer struct {
    // 이전 보고서와 현재 보고서를 비교
    // 변경된 설정들을 분석하고 영향도를 계산
}

type DriftResult struct {
    ServerID      string
    TimeRange     TimeRange
    Changes       []ConfigChange
    NewIssues     []Rule
    ResolvedIssues []Rule
    DriftScore    float64  // 0-100, 높을수록 많이 변함
}
```

드리프트 점수는 변경된 설정의 중요도와 개수를 종합해서 계산합니다. 점수가 높으면 집중 관리가 필요한 서버라는 뜻입니다.

## 확장 포인트

새로운 기능을 추가하기 쉽도록 확장 포인트를 제공합니다.

### 새 Collector 추가하기

```go
// 1. Collector 인터페이스 구현
type MyCollector struct{}

func (c *MyCollector) Name() string { return "my-collector" }
func (c *MyCollector) Collect() (interface{}, error) {
    // 데이터 수집 로직
}

// 2. 등록
collectors = append(collectors, &MyCollector{})
```

### 새 규칙 추가하기

```go
// 1. Rule 인터페이스 구현
type MyRule struct{}

func (r *MyRule) ID() string { return "mycat.mycheck" }
func (r *MyRule) Applies(role Role, data *CollectedData) bool {
    // 적용 조건 확인
}
func (r *MyRule) Check(data *CollectedData) *CheckResult {
    // 규칙 평가 로직
}

// 2. 등록
rules = append(rules, &MyRule{})
```

### 새 출력 형식 추가하기

```go
// 1. Formatter 인터페이스 구현
type MyFormatter struct{}

func (f *MyFormatter) Format(report *Report) ([]byte, error) {
    // 포맷팅 로직
}

// 2. 등록
formatters["my-format"] = &MyFormatter{}
```

## 성능 최적화

Go의 장점을 활용한 성능 최적화들:

### 동시성

```go
// 수집기들을 병렬 실행
var wg sync.WaitGroup
results := make(chan CollectorResult, len(collectors))

for _, collector := range collectors {
    wg.Add(1)
    go func(c Collector) {
        defer wg.Done()
        data, err := c.Collect()
        results <- CollectorResult{Name: c.Name(), Data: data, Error: err}
    }(collector)
}

go func() {
    wg.Wait()
    close(results)
}()
```

수집 시간이 절반으로 줄었습니다. CPU 코어가 많은 서버에서는 더 큰 효과를 볼 수 있습니다.

### 메모리 풀링

```go
// JSON 인코더 풀링으로 GC 압박 감소
var encoderPool = sync.Pool{
    New: func() interface{} {
        return json.NewEncoder(nil)
    },
}
```

### 조건부 실행

```go
// 규칙 적용 가능성을 미리 체크해서 불필요한 계산 방지
func (r *Rule) quickCheck(role Role, data *CollectedData) bool {
    if !r.Applies(role, data) {
        return false  // 비싼 Check() 호출하지 않음
    }
    return true
}
```

## 보안 고려사항

시스템 정보 수집 도구이다 보니 보안에 신경을 많이 썼습니다.

### 읽기 전용 설계

기본적으로 infra-auditor는 시스템 상태를 읽기만 합니다. 어떤 설정도 자동으로 변경하지 않습니다. 수정은 사용자가 생성된 스크립트를 검토한 후 수동으로 실행해야 합니다.

### 권한 최소화

root 권한이 필요한 최소한의 파일들만 접근합니다:
- `/proc`, `/sys` 파일시스템 (읽기 전용)
- 일부 시스템 명령어 (`lscpu`, `lsblk` 등)

### 네트워크 통신 보안

Aggregator와의 통신은 HTTPS를 사용하고, API 키 기반 인증을 지원합니다.

```go
// TLS 설정
tlsConfig := &tls.Config{
    MinVersion: tls.VersionTLS12,
    CipherSuites: []uint16{
        tls.TLS_AES_256_GCM_SHA384,
        tls.TLS_CHACHA20_POLY1305_SHA256,
    },
}
```

## 실제 배포에서 고려사항

### 크로스 컴파일

다양한 아키텍처 지원을 위해 크로스 컴파일을 활용합니다:

```bash
# Linux AMD64 (가장 일반적)
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build

# Linux ARM64 (최신 서버, Graviton 등)
CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build
```

`CGO_ENABLED=0`으로 완전한 정적 링크 바이너리를 만듭니다.

### 배포 전략

**푸시 방식**: Ansible, SaltStack 등으로 바이너리를 배포
**풀 방식**: 공유 NFS나 웹 서버에서 다운로드
**컨테이너화**: Docker 이미지로 패키징

### 모니터링 연동

Aggregator는 Prometheus metrics를 노출합니다:

```go
// 메트릭 예시
compliance_score_gauge.WithLabelValues(serverID, role).Set(score)
rule_failures_counter.WithLabelValues(ruleID).Inc()
scan_duration_histogram.Observe(duration.Seconds())
```

### 로그 관리

로그는 구조화된 형태로 출력되어 중앙 로깅 시스템과 연동하기 쉽습니다:

```go
slog.Info("점검 완료",
    "server_id", serverID,
    "role", role,
    "compliance_score", score,
    "duration_ms", duration.Milliseconds())
```

## 향후 계획

이 아키텍처는 확장 가능하도록 설계했습니다. 앞으로 추가될 수 있는 기능들:

- **머신러닝 기반 이상 탐지**: 정상 패턴 학습으로 예외 상황 감지
- **예측 분석**: 트렌드 분석으로 문제 발생 예측
- **자동 수정**: 안전한 자동 수정 기능 (opt-in)
- **클라우드 연동**: AWS, GCP, Azure 모니터링 시스템과 연동

하지만 핵심은 단순함을 유지하는 것입니다. 복잡한 기능보다는 실용성과 안정성을 우선시합니다.