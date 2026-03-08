package rules

import (
	"context"
	"encoding/json"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// CPU 관련 규칙들을 등록합니다.
func registerCPURules(engine *Engine) {
	// CPU Governor 설정 확인
	engine.RegisterRule(&CPUGovernorRule{
		BaseRule: NewBaseRule(
			"CPU-001",
			"CPU Governor 설정 확인",
			"cpu",
			types.SeverityMedium,
			"CPU 거버너가 성능에 적합하게 설정되어 있는지 확인합니다.",
			[]types.Role{types.RoleCompute, types.RoleDatabase},
		),
	})
	
	// CPU 스케일링 드라이버 확인
	engine.RegisterRule(&CPUScalingDriverRule{
		BaseRule: NewBaseRule(
			"CPU-002",
			"CPU 스케일링 드라이버 확인",
			"cpu",
			types.SeverityLow,
			"CPU 스케일링 드라이버가 올바르게 설정되어 있는지 확인합니다.",
			[]types.Role{types.RoleCompute, types.RoleDatabase},
		),
	})
	
	// CPU 로드 애버리지 확인
	engine.RegisterRule(&CPULoadAverageRule{
		BaseRule: NewBaseRule(
			"CPU-003",
			"CPU 로드 애버리지 확인",
			"cpu",
			types.SeverityHigh,
			"시스템 로드 애버리지가 정상 범위인지 확인합니다.",
			nil, // 모든 역할에 적용
		),
	})
	
	// Turbo Boost 설정 확인
	engine.RegisterRule(&TurboBoostRule{
		BaseRule: NewBaseRule(
			"CPU-004",
			"Turbo Boost 설정 확인",
			"cpu",
			types.SeverityMedium,
			"Intel Turbo Boost 또는 AMD Boost가 적절히 설정되어 있는지 확인합니다.",
			[]types.Role{types.RoleCompute, types.RoleDatabase},
		),
	})
}

// CPUGovernorRule은 CPU 거버너 설정을 확인하는 규칙입니다.
type CPUGovernorRule struct {
	*BaseRule
}

func (r *CPUGovernorRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.CPU == nil {
		return r.CreateRuleResult(types.StatusSkip, "CPU 데이터가 없습니다", "", "", nil, nil)
	}
	
	currentGovernor := data.CPU.Governor
	if currentGovernor == "" {
		return r.CreateRuleResult(types.StatusError, "CPU 거버너 정보를 가져올 수 없습니다", "", "", nil, nil)
	}
	
	// 성능 우선 거버너 확인
	preferredGovernors := []string{"performance", "schedutil"}
	isOptimal := false
	
	for _, preferred := range preferredGovernors {
		if currentGovernor == preferred {
			isOptimal = true
			break
		}
	}
	
	if isOptimal {
		return r.CreateRuleResult(
			types.StatusPass,
			"CPU 거버너가 성능에 적합하게 설정되어 있습니다",
			"",
			"",
			currentGovernor,
			"performance 또는 schedutil",
		)
	}
	
	remediation := "echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"
	
	return r.CreateRuleResult(
		types.StatusFail,
		"CPU 거버너가 성능 최적화되지 않았습니다",
		"현재 거버너가 powersave나 기타 절전 모드로 설정되어 성능이 제한될 수 있습니다",
		remediation,
		currentGovernor,
		"performance",
	)
}

// CPUScalingDriverRule은 CPU 스케일링 드라이버를 확인하는 규칙입니다.
type CPUScalingDriverRule struct {
	*BaseRule
}

func (r *CPUScalingDriverRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.CPU == nil {
		return r.CreateRuleResult(types.StatusSkip, "CPU 데이터가 없습니다", "", "", nil, nil)
	}
	
	currentDriver := data.CPU.ScalingDriver
	if currentDriver == "" {
		return r.CreateRuleResult(types.StatusError, "CPU 스케일링 드라이버 정보를 가져올 수 없습니다", "", "", nil, nil)
	}
	
	// Intel 또는 AMD 네이티브 드라이버 확인
	preferredDrivers := []string{"intel_pstate", "intel_cpufreq", "amd-pstate", "acpi-cpufreq"}
	isOptimal := false
	
	for _, preferred := range preferredDrivers {
		if currentDriver == preferred {
			isOptimal = true
			break
		}
	}
	
	if isOptimal {
		return r.CreateRuleResult(
			types.StatusPass,
			"CPU 스케일링 드라이버가 최적으로 설정되어 있습니다",
			"",
			"",
			currentDriver,
			preferredDrivers,
		)
	}
	
	return r.CreateRuleResult(
		types.StatusFail,
		"CPU 스케일링 드라이버를 확인하세요",
		"현재 드라이버가 최적이 아닐 수 있습니다",
		"BIOS에서 CPU 전력 관리 설정을 확인하거나 intel_pstate 커널 매개변수를 조정하세요",
		currentDriver,
		"intel_pstate, intel_cpufreq, amd-pstate, 또는 acpi-cpufreq",
	)
}

// CPULoadAverageRule은 CPU 로드 애버리지를 확인하는 규칙입니다.
type CPULoadAverageRule struct {
	*BaseRule
}

func (r *CPULoadAverageRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.CPU == nil {
		return r.CreateRuleResult(types.StatusSkip, "CPU 데이터가 없습니다", "", "", nil, nil)
	}
	
	loadAvg := data.CPU.LoadAverage
	
	// CPU 코어 수 확인
	var cpuCount int
	if data.CPU.CPUInfo != nil {
		var cpuInfo map[string]interface{}
		if err := json.Unmarshal(data.CPU.CPUInfo, &cpuInfo); err == nil {
			if count, ok := cpuInfo["count"].(float64); ok {
				cpuCount = int(count)
			}
		}
	}
	
	if cpuCount == 0 {
		cpuCount = 1 // 최소값
	}
	
	// 1분 로드 애버리지 확인
	load1min := loadAvg[0]
	loadPerCore := load1min / float64(cpuCount)
	
	var status types.Status
	var message, details string
	
	if loadPerCore <= 0.7 {
		status = types.StatusPass
		message = "CPU 로드 애버리지가 정상 범위입니다"
	} else if loadPerCore <= 1.0 {
		status = types.StatusFail
		message = "CPU 로드 애버리지가 높습니다"
		details = "시스템 부하가 높아 성능에 영향을 줄 수 있습니다"
	} else {
		status = types.StatusFail
		message = "CPU 로드 애버리지가 매우 높습니다"
		details = "시스템이 과부하 상태입니다. 즉시 조치가 필요합니다"
	}
	
	remediation := "top 또는 htop으로 CPU 사용량이 높은 프로세스를 확인하고 최적화하거나 하드웨어 업그레이드를 고려하세요"
	
	return r.CreateRuleResult(
		status,
		message,
		details,
		remediation,
		map[string]interface{}{
			"load_1min":       load1min,
			"load_5min":       loadAvg[1],
			"load_15min":      loadAvg[2],
			"cpu_cores":       cpuCount,
			"load_per_core":   loadPerCore,
		},
		"< 0.7 (per core)",
	)
}

// TurboBoostRule은 Turbo Boost 설정을 확인하는 규칙입니다.
type TurboBoostRule struct {
	*BaseRule
}

func (r *TurboBoostRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.CPU == nil || data.CPU.PowerManagement == nil {
		return r.CreateRuleResult(types.StatusSkip, "CPU 전력 관리 데이터가 없습니다", "", "", nil, nil)
	}
	
	powerMgmt := data.CPU.PowerManagement
	turboBoost, exists := powerMgmt["turbo_boost"]
	
	if !exists {
		return r.CreateRuleResult(types.StatusSkip, "Turbo Boost 정보가 없습니다", "", "", nil, nil)
	}
	
	turboBoostMap, ok := turboBoost.(map[string]interface{})
	if !ok {
		return r.CreateRuleResult(types.StatusError, "Turbo Boost 정보 형식이 올바르지 않습니다", "", "", nil, nil)
	}
	
	var isEnabled bool
	var currentSetting string
	
	// Intel Turbo Boost 확인
	if intelTurboEnabled, exists := turboBoostMap["intel_turbo_enabled"]; exists {
		if enabled, ok := intelTurboEnabled.(bool); ok {
			isEnabled = enabled
			currentSetting = "Intel Turbo Boost: "
			if enabled {
				currentSetting += "enabled"
			} else {
				currentSetting += "disabled"
			}
		}
	}
	
	// AMD Boost 확인
	if boostEnabled, exists := turboBoostMap["boost_enabled"]; exists {
		if enabled, ok := boostEnabled.(bool); ok {
			isEnabled = enabled
			currentSetting = "AMD Boost: "
			if enabled {
				currentSetting += "enabled"
			} else {
				currentSetting += "disabled"
			}
		}
	}
	
	if currentSetting == "" {
		return r.CreateRuleResult(types.StatusSkip, "Turbo Boost 상태를 확인할 수 없습니다", "", "", nil, nil)
	}
	
	if isEnabled {
		return r.CreateRuleResult(
			types.StatusPass,
			"Turbo Boost가 활성화되어 있습니다",
			"",
			"",
			currentSetting,
			"enabled",
		)
	}
	
	remediation := strings.Join([]string{
		"Intel의 경우: echo 0 | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo",
		"AMD의 경우: echo 1 | sudo tee /sys/devices/system/cpu/cpufreq/boost",
		"또는 BIOS에서 Turbo Boost 설정을 확인하세요",
	}, "\n")
	
	return r.CreateRuleResult(
		types.StatusFail,
		"Turbo Boost가 비활성화되어 있습니다",
		"CPU 성능이 제한되어 워크로드 처리 속도가 저하될 수 있습니다",
		remediation,
		currentSetting,
		"enabled",
	)
}