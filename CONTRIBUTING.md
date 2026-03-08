# 기여 가이드

infra-auditor는 실무에서 바로 쓸 수 있는 도구가 되는 것을 목표로 합니다. 새로운 하드웨어, 소프트웨어, 최적화 기법이 나올 때마다 함께 발전해야 합니다. 여러분의 경험과 지식을 공유해주세요.

## 기여할 수 있는 것들

### 새로운 규칙 추가
- 최신 하드웨어에 대한 튜닝 규칙 (DDR5 메모리, PCIe 5.0 등)
- 새로운 소프트웨어 스택 최적화 (Kubernetes, Istio, Cilium 등)
- 클라우드 환경 특화 설정 (AWS Graviton, Google T2A 등)
- 보안 강화 규칙 (CIS benchmark, STIG 등)

### 새로운 수집기 추가
- GPU 정보 수집 (NVIDIA, AMD)
- 컨테이너 런타임 정보 (containerd, CRI-O)
- 네트워크 가상화 (SR-IOV, DPDK)
- 스토리지 상세 정보 (NVMe namespace, RAID 상태)

### 버그 수정
- 특정 환경에서의 오동작
- 성능 개선
- 에러 핸들링 강화

### 문서 개선
- 사용 사례 추가
- 실무 팁 공유
- 번역 (영어, 일본어 등)

## 개발 환경 설정

### 요구사항
- Go 1.19 이상
- Git
- Linux 환경 (WSL2도 가능)
- root 권한 (일부 시스템 정보 수집을 위해)

### 로컬 개발 환경

```bash
# 저장소 클론
git clone https://github.com/ecmoce/infra-auditor.git
cd infra-auditor

# 의존성 설치
go mod download

# 빌드
make build

# 테스트
make test

# 로컬에서 실행
sudo ./infra-auditor scan
```

### IDE 설정 권장사항

**VSCode**:
```json
// .vscode/settings.json
{
    "go.useLanguageServer": true,
    "go.toolsManagement.checkForUpdates": "local",
    "go.lintOnSave": "package",
    "go.lintTool": "golint",
    "go.formatTool": "gofmt"
}
```

**GoLand**: 기본 설정으로도 충분합니다.

## 새로운 Collector 추가하기

Collector는 시스템에서 정보를 수집하는 컴포넌트입니다. 실제 예시로 GPU 정보를 수집하는 Collector를 만들어보겠습니다.

### 1단계: Collector 인터페이스 구현

`internal/collector/gpu.go` 파일 생성:

```go
package collector

import (
    "fmt"
    "os/exec"
    "strconv"
    "strings"
)

// GPUCollector는 GPU 정보를 수집합니다
type GPUCollector struct {
    BaseCollector
}

// GPUInfo는 수집된 GPU 정보를 담는 구조체입니다
type GPUInfo struct {
    Present         bool     `json:"present"`
    Count           int      `json:"count"`
    Drivers         []string `json:"drivers"`
    Models          []string `json:"models"`
    MemoryTotal     []uint64 `json:"memory_total_mb"`
    PowerLimit      []uint64 `json:"power_limit_w"`
    Temperature     []int    `json:"temperature_c"`
    UtilizationGPU  []int    `json:"utilization_gpu_percent"`
    UtilizationMem  []int    `json:"utilization_memory_percent"`
}

// NewGPUCollector는 새로운 GPUCollector를 생성합니다
func NewGPUCollector() Collector {
    return &GPUCollector{
        BaseCollector: BaseCollector{name: "gpu"},
    }
}

// Name은 collector 이름을 반환합니다
func (c *GPUCollector) Name() string {
    return c.name
}

// Collect는 GPU 정보를 수집합니다
func (c *GPUCollector) Collect() (interface{}, error) {
    info := &GPUInfo{
        Present:         false,
        Count:           0,
        Drivers:         []string{},
        Models:          []string{},
        MemoryTotal:     []uint64{},
        PowerLimit:      []uint64{},
        Temperature:     []int{},
        UtilizationGPU:  []int{},
        UtilizationMem:  []int{},
    }

    // nvidia-smi가 있는지 확인
    if err := c.collectNVIDIA(info); err != nil {
        c.logDebug("NVIDIA GPU not found: %v", err)
    }

    // AMD GPU 확인도 추가 가능
    if err := c.collectAMD(info); err != nil {
        c.logDebug("AMD GPU not found: %v", err)
    }

    return info, nil
}

// collectNVIDIA는 NVIDIA GPU 정보를 수집합니다
func (c *GPUCollector) collectNVIDIA(info *GPUInfo) error {
    // nvidia-smi가 설치되어 있는지 확인
    cmd := exec.Command("nvidia-smi", "--query-gpu=count", "--format=csv,noheader,nounits")
    if err := cmd.Run(); err != nil {
        return fmt.Errorf("nvidia-smi not found: %w", err)
    }

    // GPU 개수 확인
    countCmd := exec.Command("nvidia-smi", "--query-gpu=count", "--format=csv,noheader,nounits")
    output, err := countCmd.Output()
    if err != nil {
        return fmt.Errorf("failed to get GPU count: %w", err)
    }

    count, err := strconv.Atoi(strings.TrimSpace(string(output)))
    if err != nil {
        return fmt.Errorf("failed to parse GPU count: %w", err)
    }

    if count == 0 {
        return fmt.Errorf("no NVIDIA GPUs found")
    }

    info.Present = true
    info.Count = count
    info.Drivers = append(info.Drivers, "nvidia")

    // 상세 정보 수집
    return c.collectNVIDIADetails(info)
}

// collectNVIDIADetails는 NVIDIA GPU의 상세 정보를 수집합니다
func (c *GPUCollector) collectNVIDIADetails(info *GPUInfo) error {
    // 여러 정보를 한 번에 수집
    cmd := exec.Command("nvidia-smi", 
        "--query-gpu=name,memory.total,power.limit,temperature.gpu,utilization.gpu,utilization.memory",
        "--format=csv,noheader,nounits")
    
    output, err := cmd.Output()
    if err != nil {
        return fmt.Errorf("failed to get GPU details: %w", err)
    }

    lines := strings.Split(strings.TrimSpace(string(output)), "\n")
    for _, line := range lines {
        fields := strings.Split(line, ", ")
        if len(fields) < 6 {
            continue
        }

        // 모델명
        info.Models = append(info.Models, fields[0])

        // 메모리 (MB)
        if memory, err := strconv.ParseUint(fields[1], 10, 64); err == nil {
            info.MemoryTotal = append(info.MemoryTotal, memory)
        }

        // 전력 제한 (W)
        if power, err := strconv.ParseUint(fields[2], 10, 64); err == nil {
            info.PowerLimit = append(info.PowerLimit, power)
        }

        // 온도 (C)
        if temp, err := strconv.Atoi(fields[3]); err == nil {
            info.Temperature = append(info.Temperature, temp)
        }

        // GPU 사용률 (%)
        if util, err := strconv.Atoi(fields[4]); err == nil {
            info.UtilizationGPU = append(info.UtilizationGPU, util)
        }

        // 메모리 사용률 (%)
        if util, err := strconv.Atoi(fields[5]); err == nil {
            info.UtilizationMem = append(info.UtilizationMem, util)
        }
    }

    return nil
}

// collectAMD는 AMD GPU 정보를 수집합니다 (향후 구현)
func (c *GPUCollector) collectAMD(info *GPUInfo) error {
    // rocm-smi 등을 사용한 AMD GPU 정보 수집
    return fmt.Errorf("AMD GPU detection not implemented yet")
}
```

### 2단계: Collector 등록

`internal/collector/collector.go`에 새로운 collector 추가:

```go
// GetCollectors는 모든 사용 가능한 collector들을 반환합니다
func GetCollectors() []Collector {
    return []Collector{
        NewCPUCollector(),
        NewMemoryCollector(),
        NewNetworkCollector(),
        NewStorageCollector(),
        NewKernelCollector(),
        NewServiceCollector(),
        NewDockerCollector(),
        NewBondingCollector(),
        NewOVSCollector(),
        NewSystemdCollector(),
        NewGPUCollector(),    // 새로 추가
    }
}
```

### 3단계: 테스트 작성

`internal/collector/gpu_test.go` 파일 생성:

```go
package collector

import (
    "testing"
)

func TestGPUCollector(t *testing.T) {
    collector := NewGPUCollector()
    
    // collector 이름 확인
    if collector.Name() != "gpu" {
        t.Errorf("Expected name 'gpu', got '%s'", collector.Name())
    }

    // 데이터 수집 테스트
    data, err := collector.Collect()
    if err != nil {
        t.Errorf("Collect() failed: %v", err)
    }

    gpuInfo, ok := data.(*GPUInfo)
    if !ok {
        t.Errorf("Expected *GPUInfo, got %T", data)
    }

    // 기본적인 필드 검증
    if gpuInfo == nil {
        t.Error("GPUInfo is nil")
    }

    // GPU가 있는 시스템에서만 추가 검증
    if gpuInfo.Present {
        if gpuInfo.Count == 0 {
            t.Error("GPU is present but count is 0")
        }
        if len(gpuInfo.Models) != gpuInfo.Count {
            t.Errorf("Models count (%d) doesn't match GPU count (%d)", 
                len(gpuInfo.Models), gpuInfo.Count)
        }
    }
}

func TestGPUCollectorNVIDIA(t *testing.T) {
    // NVIDIA GPU가 없는 환경에서도 오류 없이 동작하는지 테스트
    collector := &GPUCollector{
        BaseCollector: BaseCollector{name: "gpu"},
    }
    
    info := &GPUInfo{}
    err := collector.collectNVIDIA(info)
    
    // nvidia-smi가 없으면 에러가 발생해야 함
    if err == nil {
        // 실제로 NVIDIA GPU가 있는 경우
        if !info.Present {
            t.Error("NVIDIA GPU detected but Present is false")
        }
    } else {
        // nvidia-smi가 없는 경우는 정상
        t.Logf("NVIDIA GPU not found (expected): %v", err)
    }
}
```

### 4단계: 문서화

`docs/COLLECTORS.md`에 새로운 collector 정보 추가:

```markdown
## GPU Collector

GPU 정보를 수집합니다. NVIDIA와 AMD GPU를 지원합니다.

### 수집 정보

- GPU 존재 여부
- GPU 개수 및 모델명
- 드라이버 정보
- 메모리 크기
- 전력 제한
- 현재 온도
- GPU/메모리 사용률

### 요구사항

**NVIDIA GPU**:
- `nvidia-smi` 명령어 사용 가능
- NVIDIA 드라이버 설치됨

**AMD GPU**:
- `rocm-smi` 명령어 사용 가능 (향후 구현)
- ROCm 드라이버 설치됨

### 출력 예시

```json
{
  "present": true,
  "count": 2,
  "drivers": ["nvidia"],
  "models": ["Tesla V100-SXM2-32GB", "Tesla V100-SXM2-32GB"],
  "memory_total_mb": [32768, 32768],
  "power_limit_w": [300, 300],
  "temperature_c": [35, 38],
  "utilization_gpu_percent": [85, 92],
  "utilization_memory_percent": [70, 88]
}
```
```

## 새로운 규칙 추가하기

규칙은 수집된 데이터를 바탕으로 시스템 상태를 평가합니다. GPU 과열을 체크하는 규칙을 예시로 만들어보겠습니다.

### 1단계: 규칙 구현

`internal/rules/gpu_rules.go` 파일 생성:

```go
package rules

import (
    "fmt"
    "github.com/ecmoce/infra-auditor/pkg/types"
    "github.com/ecmoce/infra-auditor/internal/collector"
)

// GPUTemperatureRule는 GPU 온도를 체크하는 규칙입니다
type GPUTemperatureRule struct {
    BaseRule
}

// NewGPUTemperatureRule은 새로운 GPU 온도 규칙을 생성합니다
func NewGPUTemperatureRule() Rule {
    return &GPUTemperatureRule{
        BaseRule: BaseRule{
            id:          "gpu.temperature",
            name:        "GPU 온도 체크",
            description: "GPU가 과열되지 않았는지 확인합니다",
            category:    types.CategoryHardware,
            severity:    types.SeverityHigh,
        },
    }
}

// Applies는 이 규칙이 현재 시스템에 적용되는지 확인합니다
func (r *GPUTemperatureRule) Applies(role types.Role, data *types.CollectedData) bool {
    // GPU가 있는 시스템에만 적용
    gpuData, exists := data.Data["gpu"]
    if !exists {
        return false
    }

    gpuInfo, ok := gpuData.(*collector.GPUInfo)
    if !ok || !gpuInfo.Present {
        return false
    }

    // Compute 노드에는 반드시 적용, 다른 역할에는 선택적 적용
    if role == types.RoleCompute {
        return true
    }

    // GPU가 있으면 어떤 역할이든 적용
    return gpuInfo.Count > 0
}

// Check는 실제 규칙 검사를 수행합니다
func (r *GPUTemperatureRule) Check(data *types.CollectedData) *types.CheckResult {
    gpuData, exists := data.Data["gpu"]
    if !exists {
        return &types.CheckResult{
            Status:  types.StatusSkipped,
            Message: "GPU 정보를 찾을 수 없습니다",
        }
    }

    gpuInfo, ok := gpuData.(*collector.GPUInfo)
    if !ok {
        return &types.CheckResult{
            Status:  types.StatusError,
            Message: "GPU 데이터 타입이 올바르지 않습니다",
        }
    }

    if !gpuInfo.Present || len(gpuInfo.Temperature) == 0 {
        return &types.CheckResult{
            Status:  types.StatusSkipped,
            Message: "온도 정보를 사용할 수 없습니다",
        }
    }

    // 온도 임계값 설정
    const (
        warningTemp  = 80  // 80도 이상이면 경고
        criticalTemp = 90  // 90도 이상이면 위험
    )

    var hotGPUs []int
    var overheatedGPUs []int
    maxTemp := 0

    for i, temp := range gpuInfo.Temperature {
        if temp > maxTemp {
            maxTemp = temp
        }

        if temp >= criticalTemp {
            overheatedGPUs = append(overheatedGPUs, i)
        } else if temp >= warningTemp {
            hotGPUs = append(hotGPUs, i)
        }
    }

    // 결과 판정
    if len(overheatedGPUs) > 0 {
        return &types.CheckResult{
            Status:        types.StatusFailed,
            CurrentValue:  fmt.Sprintf("%d°C (GPU %v)", maxTemp, overheatedGPUs),
            ExpectedValue: fmt.Sprintf("< %d°C", criticalTemp),
            Message:       fmt.Sprintf("GPU %v가 과열 상태입니다 (%d°C)", overheatedGPUs, maxTemp),
            Remediation:   "냉각 시스템을 점검하거나 GPU 워크로드를 줄이세요",
        }
    }

    if len(hotGPUs) > 0 {
        return &types.CheckResult{
            Status:        types.StatusWarning,
            CurrentValue:  fmt.Sprintf("%d°C (GPU %v)", maxTemp, hotGPUs),
            ExpectedValue: fmt.Sprintf("< %d°C", warningTemp),
            Message:       fmt.Sprintf("GPU %v가 고온 상태입니다 (%d°C)", hotGPUs, maxTemp),
            Remediation:   "냉각 성능을 확인하세요",
        }
    }

    return &types.CheckResult{
        Status:        types.StatusPassed,
        CurrentValue:  fmt.Sprintf("%d°C", maxTemp),
        ExpectedValue: fmt.Sprintf("< %d°C", warningTemp),
        Message:       "모든 GPU 온도가 정상 범위입니다",
    }
}
```

### 2단계: 규칙 등록

`internal/rules/rules.go`에 새로운 규칙 추가:

```go
// GetAllRules는 모든 규칙을 반환합니다
func GetAllRules() []Rule {
    return []Rule{
        // 기존 규칙들...
        
        // GPU 관련 규칙들
        NewGPUTemperatureRule(),
        // NewGPUMemoryUsageRule(),  // 향후 추가 가능
        // NewGPUPowerUsageRule(),   // 향후 추가 가능
    }
}
```

### 3단계: 테스트 작성

`internal/rules/gpu_rules_test.go` 파일 생성:

```go
package rules

import (
    "testing"
    "github.com/ecmoce/infra-auditor/pkg/types"
    "github.com/ecmoce/infra-auditor/internal/collector"
)

func TestGPUTemperatureRule(t *testing.T) {
    rule := NewGPUTemperatureRule()

    // 규칙 기본 정보 확인
    if rule.ID() != "gpu.temperature" {
        t.Errorf("Expected ID 'gpu.temperature', got '%s'", rule.ID())
    }

    if rule.Category() != types.CategoryHardware {
        t.Errorf("Expected category Hardware, got %v", rule.Category())
    }

    if rule.Severity() != types.SeverityHigh {
        t.Errorf("Expected severity High, got %v", rule.Severity())
    }
}

func TestGPUTemperatureRuleApplies(t *testing.T) {
    rule := NewGPUTemperatureRule()

    tests := []struct {
        name     string
        role     types.Role
        gpuData  *collector.GPUInfo
        expected bool
    }{
        {
            name: "Compute role with GPU",
            role: types.RoleCompute,
            gpuData: &collector.GPUInfo{
                Present: true,
                Count:   1,
            },
            expected: true,
        },
        {
            name: "Storage role with GPU",
            role: types.RoleStorage,
            gpuData: &collector.GPUInfo{
                Present: true,
                Count:   1,
            },
            expected: true,
        },
        {
            name: "No GPU present",
            role: types.RoleCompute,
            gpuData: &collector.GPUInfo{
                Present: false,
                Count:   0,
            },
            expected: false,
        },
        {
            name:     "No GPU data",
            role:     types.RoleCompute,
            gpuData:  nil,
            expected: false,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            data := &types.CollectedData{
                Data: make(map[string]interface{}),
            }

            if tt.gpuData != nil {
                data.Data["gpu"] = tt.gpuData
            }

            result := rule.Applies(tt.role, data)
            if result != tt.expected {
                t.Errorf("Expected %v, got %v", tt.expected, result)
            }
        })
    }
}

func TestGPUTemperatureRuleCheck(t *testing.T) {
    rule := NewGPUTemperatureRule()

    tests := []struct {
        name     string
        gpuData  *collector.GPUInfo
        expected types.CheckStatus
    }{
        {
            name: "Normal temperature",
            gpuData: &collector.GPUInfo{
                Present:     true,
                Count:       2,
                Temperature: []int{65, 70},
            },
            expected: types.StatusPassed,
        },
        {
            name: "High temperature warning",
            gpuData: &collector.GPUInfo{
                Present:     true,
                Count:       2,
                Temperature: []int{85, 75},
            },
            expected: types.StatusWarning,
        },
        {
            name: "Critical temperature",
            gpuData: &collector.GPUInfo{
                Present:     true,
                Count:       1,
                Temperature: []int{95},
            },
            expected: types.StatusFailed,
        },
        {
            name: "No temperature data",
            gpuData: &collector.GPUInfo{
                Present:     true,
                Count:       1,
                Temperature: []int{},
            },
            expected: types.StatusSkipped,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            data := &types.CollectedData{
                Data: map[string]interface{}{
                    "gpu": tt.gpuData,
                },
            }

            result := rule.Check(data)
            if result.Status != tt.expected {
                t.Errorf("Expected status %v, got %v", tt.expected, result.Status)
            }
        })
    }
}
```

### 4단계: 역할별 규칙 매핑

`internal/rules/role_rules.go`에 역할별 규칙 매핑 추가:

```go
// GetRulesForRole은 특정 역할에 적용할 규칙들을 반환합니다
func GetRulesForRole(role types.Role) []Rule {
    allRules := GetAllRules()
    var applicableRules []Rule

    for _, rule := range allRules {
        // Applies 메서드는 실제 데이터가 필요하므로
        // 여기서는 역할별 기본 매핑만 수행
        switch role {
        case types.RoleCompute:
            // Compute 노드에는 모든 하드웨어 규칙 적용
            if rule.Category() == types.CategoryHardware ||
               rule.Category() == types.CategoryVirtualization ||
               rule.ID() == "gpu.temperature" {
                applicableRules = append(applicableRules, rule)
            }
            
        case types.RoleStorage:
            // Storage 노드에는 스토리지와 일부 하드웨어 규칙 적용
            if rule.Category() == types.CategoryStorage ||
               rule.Category() == types.CategoryHardware {
                applicableRules = append(applicableRules, rule)
            }
            
        // 다른 역할들...
        }
    }

    return applicableRules
}
```

## 테스트 작성 가이드

### 단위 테스트 원칙

1. **독립성**: 각 테스트는 독립적으로 실행 가능해야 합니다
2. **재현성**: 같은 조건에서 항상 같은 결과가 나와야 합니다  
3. **명확성**: 테스트 이름만 보고도 무엇을 테스트하는지 알 수 있어야 합니다
4. **완전성**: 정상 케이스, 에러 케이스, 엣지 케이스를 모두 커버해야 합니다

### 테스트 실행

```bash
# 모든 테스트 실행
make test

# 특정 패키지 테스트
go test ./internal/collector

# 커버리지와 함께 실행
go test -cover ./...

# 벤치마크 테스트
go test -bench=. ./internal/rules

# 상세 출력
go test -v ./internal/collector/gpu_test.go
```

### 목(Mock) 사용

외부 의존성이 있는 코드는 목을 사용해서 테스트합니다:

```go
// mockable_command.go
type CommandExecutor interface {
    Execute(name string, args ...string) ([]byte, error)
}

type RealCommandExecutor struct{}

func (e *RealCommandExecutor) Execute(name string, args ...string) ([]byte, error) {
    cmd := exec.Command(name, args...)
    return cmd.Output()
}

// 테스트에서 사용할 목 구현
type MockCommandExecutor struct {
    outputs map[string][]byte
    errors  map[string]error
}

func (m *MockCommandExecutor) Execute(name string, args ...string) ([]byte, error) {
    key := name + " " + strings.Join(args, " ")
    if err, exists := m.errors[key]; exists {
        return nil, err
    }
    if output, exists := m.outputs[key]; exists {
        return output, nil
    }
    return nil, fmt.Errorf("mock not configured for: %s", key)
}
```

## Pull Request 프로세스

### 1단계: 이슈 확인

기능 추가나 버그 수정 전에 GitHub 이슈를 확인하거나 새로 생성하세요:

```markdown
## 이슈 제목: GPU 온도 모니터링 규칙 추가

### 동기
NVIDIA GPU를 사용하는 Compute 노드에서 GPU 과열로 인한 성능 저하가 발생하고 있습니다. 
GPU 온도를 모니터링하여 문제를 조기에 발견할 수 있는 규칙이 필요합니다.

### 제안사항
- GPU 온도를 수집하는 GPUCollector 추가
- 온도 임계값을 체크하는 GPUTemperatureRule 추가
- 80도 이상 경고, 90도 이상 위험으로 분류

### 구현 계획
1. GPUCollector 구현 (nvidia-smi 사용)
2. GPUTemperatureRule 구현
3. 테스트 코드 작성
4. 문서 업데이트
```

### 2단계: 브랜치 생성

```bash
# feature 브랜치 생성
git checkout -b feature/gpu-temperature-monitoring

# 또는 bugfix 브랜치
git checkout -b bugfix/memory-collector-overflow
```

### 3단계: 개발 및 테스트

```bash
# 코드 작성 후 테스트
make test

# 린트 체크
make lint

# 빌드 확인
make build

# 로컬에서 동작 테스트
sudo ./infra-auditor scan --categories hardware
```

### 4단계: 커밋 메시지

명확하고 일관된 커밋 메시지를 작성하세요:

```bash
# 좋은 예시
git commit -m "feat: Add GPU temperature monitoring

- Implement GPUCollector to gather temperature data via nvidia-smi
- Add GPUTemperatureRule with 80°C warning, 90°C critical thresholds  
- Include comprehensive tests for both collector and rule
- Update documentation for new hardware monitoring capability

Fixes #123"

# 나쁜 예시
git commit -m "gpu stuff"
git commit -m "fix bug"
```

### 5단계: Pull Request 생성

PR 템플릿에 따라 상세한 설명을 작성하세요:

```markdown
## 변경 사항
- GPU 온도 수집을 위한 GPUCollector 추가
- 과열 상태를 감지하는 GPUTemperatureRule 추가
- nvidia-smi 명령어를 통한 NVIDIA GPU 지원

## 테스트
- [x] 단위 테스트 작성 및 통과
- [x] GPU가 있는 환경에서 테스트
- [x] GPU가 없는 환경에서도 오류 없이 동작 확인
- [x] 각종 온도 시나리오 테스트 (정상, 경고, 위험)

## 체크리스트
- [x] 코드가 프로젝트 스타일 가이드를 따름
- [x] 자체 코드 리뷰 완료
- [x] 새로운 기능에 대한 테스트 추가
- [x] 문서 업데이트 완료
- [x] 변경사항이 기존 기능에 영향을 주지 않음

## 스크린샷
```json
{
  "rule_id": "gpu.temperature",
  "status": "warning", 
  "current_value": "85°C (GPU [0])",
  "expected_value": "< 80°C",
  "message": "GPU [0]가 고온 상태입니다 (85°C)"
}
```

Closes #123
```

### 6단계: 코드 리뷰

PR이 생성되면 코드 리뷰가 진행됩니다:

1. **자동 체크**: CI가 테스트, 빌드, 린트를 자동 실행합니다
2. **동료 리뷰**: 다른 개발자들이 코드를 검토합니다
3. **피드백 반영**: 리뷰 의견을 반영해서 코드를 수정합니다
4. **승인**: 모든 체크를 통과하면 merge됩니다

### 7단계: 머지 후 정리

```bash
# 머지 후 로컬 브랜치 정리
git checkout main
git pull origin main
git branch -d feature/gpu-temperature-monitoring
```

## 스타일 가이드

### Go 코드 스타일

프로젝트는 표준 Go 스타일을 따릅니다:

```bash
# 포맷팅
gofmt -w .

# import 정리
goimports -w .

# 린트
golangci-lint run
```

**중요한 규칙들**:

1. **에러 처리**: 모든 에러는 적절히 처리하거나 상위로 전파
2. **변수명**: 축약보다는 명확한 이름 사용
3. **패키지명**: 짧고 명확하게
4. **주석**: 공개 함수/구조체는 반드시 주석 추가

### 문서 스타일

1. **한국어 우선**: 기본 문서는 한국어로 작성
2. **실용성**: 이론보다는 실제 사용법 중심
3. **예시 포함**: 코드 예시와 실행 결과 포함
4. **단계별 설명**: 복잡한 과정은 단계별로 나누어 설명

## 문제 해결

### 자주 발생하는 문제들

**문제: 테스트가 root 권한 없이 실패**
```bash
# 해결: 특정 테스트만 실행하거나 mock 사용
go test -v ./internal/rules  # 규칙 테스트는 실제 데이터 불필요
sudo go test ./internal/collector  # 수집기 테스트는 root 권한 필요
```

**문제: 크로스 컴파일 에러**
```bash
# 해결: CGO 비활성화
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build
```

**문제: 의존성 관리**
```bash
# 해결: go mod 명령어 사용
go mod tidy  # 불필요한 의존성 정리
go mod verify  # 의존성 검증
go mod download  # 의존성 다운로드
```

### 도움 요청

막히는 부분이 있으면 언제든 도움을 요청하세요:

1. **GitHub 이슈**: 기술적인 질문이나 버그 리포트
2. **Discord**: 실시간 질의응답 (초대 링크는 README 참조)
3. **이메일**: maintainer에게 직접 연락

기여해주시는 모든 분들께 감사드립니다. 여러분의 경험과 아이디어가 infra-auditor를 더 나은 도구로 만들어갑니다!