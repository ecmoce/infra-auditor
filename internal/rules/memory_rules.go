package rules

import (
	"context"
	"encoding/json"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// Memory 관련 규칙들을 등록합니다.
func registerMemoryRules(engine *Engine) {
	// Swappiness 설정 확인
	engine.RegisterRule(&SwappinessRule{
		BaseRule: NewBaseRule(
			"MEM-001",
			"Swappiness 설정 확인",
			"memory",
			types.SeverityMedium,
			"vm.swappiness 값이 워크로드에 적합하게 설정되어 있는지 확인합니다.",
			nil, // 모든 역할에 적용
		),
	})
	
	// HugePages 설정 확인
	engine.RegisterRule(&HugePagesRule{
		BaseRule: NewBaseRule(
			"MEM-002",
			"HugePages 설정 확인",
			"memory",
			types.SeverityMedium,
			"데이터베이스나 메모리 집약적 애플리케이션을 위한 HugePages 설정을 확인합니다.",
			[]types.Role{types.RoleDatabase, types.RoleCompute},
		),
	})
	
	// 메모리 사용률 확인
	engine.RegisterRule(&MemoryUsageRule{
		BaseRule: NewBaseRule(
			"MEM-003",
			"메모리 사용률 확인",
			"memory",
			types.SeverityHigh,
			"시스템 메모리 사용률이 정상 범위인지 확인합니다.",
			nil, // 모든 역할에 적용
		),
	})
	
	// OOM Killer 발생 확인
	engine.RegisterRule(&OOMKillerRule{
		BaseRule: NewBaseRule(
			"MEM-004",
			"OOM Killer 발생 확인",
			"memory",
			types.SeverityCritical,
			"Out of Memory Killer가 발생했는지 확인합니다.",
			nil, // 모든 역할에 적용
		),
	})
}

// SwappinessRule은 swappiness 설정을 확인하는 규칙입니다.
type SwappinessRule struct {
	*BaseRule
}

func (r *SwappinessRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.Memory == nil {
		return r.CreateRuleResult(types.StatusSkip, "메모리 데이터가 없습니다", "", "", nil, nil)
	}
	
	swappiness := data.Memory.Swappiness
	
	// 워크로드별 권장 swappiness 값
	var recommendedValue int
	var message, details, remediation string
	
	// 일반적으로 서버 워크로드에는 낮은 swappiness가 권장됨
	if swappiness >= 60 {
		recommendedValue = 10
		message = "Swappiness 값이 너무 높습니다"
		details = "높은 swappiness는 불필요한 스왑 사용을 유발하여 성능을 저하시킬 수 있습니다"
		remediation = "echo 10 | sudo tee /proc/sys/vm/swappiness && echo 'vm.swappiness=10' >> /etc/sysctl.conf"
		
		return r.CreateRuleResult(
			types.StatusFail,
			message,
			details,
			remediation,
			swappiness,
			recommendedValue,
		)
	} else if swappiness >= 20 {
		recommendedValue = 10
		message = "Swappiness 값을 더 낮추는 것을 고려하세요"
		details = "데이터베이스나 성능 중시 워크로드에서는 더 낮은 값이 권장됩니다"
		remediation = "echo 10 | sudo tee /proc/sys/vm/swappiness && echo 'vm.swappiness=10' >> /etc/sysctl.conf"
		
		return r.CreateRuleResult(
			types.StatusFail,
			message,
			details,
			remediation,
			swappiness,
			recommendedValue,
		)
	}
	
	return r.CreateRuleResult(
		types.StatusPass,
		"Swappiness가 적절하게 설정되어 있습니다",
		"",
		"",
		swappiness,
		"1-10 (서버 워크로드에 권장)",
	)
}

// HugePagesRule은 HugePages 설정을 확인하는 규칙입니다.
type HugePagesRule struct {
	*BaseRule
}

func (r *HugePagesRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.Memory == nil {
		return r.CreateRuleResult(types.StatusSkip, "메모리 데이터가 없습니다", "", "", nil, nil)
	}
	
	hugePagesTotal := data.Memory.HugePagesTotal
	hugePagesSize := data.Memory.HugePagesSize // KB 단위
	
	if hugePagesSize == 0 {
		return r.CreateRuleResult(types.StatusSkip, "HugePages 정보가 없습니다", "", "", nil, nil)
	}
	
	// 전체 메모리 크기 확인
	var totalMemoryKB int64
	if data.Memory.MemInfo != nil {
		var memInfo map[string]interface{}
		if err := json.Unmarshal(data.Memory.MemInfo, &memInfo); err == nil {
			if memTotal, ok := memInfo["MemTotal"].(float64); ok {
				totalMemoryKB = int64(memTotal)
			}
		}
	}
	
	if totalMemoryKB == 0 {
		return r.CreateRuleResult(types.StatusError, "전체 메모리 정보를 가져올 수 없습니다", "", "", nil, nil)
	}
	
	// 대형 메모리 시스템 (32GB 이상)에서 HugePages 권장
	totalMemoryGB := totalMemoryKB / 1024 / 1024
	
	if totalMemoryGB >= 32 {
		if hugePagesTotal == 0 {
			remediation := strings.Join([]string{
				"# 전체 메모리의 50-75% 정도를 HugePages로 설정",
				"echo 8192 | sudo tee /proc/sys/vm/nr_hugepages",
				"echo 'vm.nr_hugepages=8192' >> /etc/sysctl.conf",
				"# 또는 부팅 시 설정: hugepages=8192 커널 매개변수 추가",
			}, "\n")
			
			return r.CreateRuleResult(
				types.StatusFail,
				"대용량 메모리 시스템에서 HugePages가 설정되지 않았습니다",
				"HugePages를 사용하면 TLB 미스를 줄여 메모리 집약적 애플리케이션의 성능을 향상시킬 수 있습니다",
				remediation,
				map[string]interface{}{
					"hugepages_total": hugePagesTotal,
					"hugepage_size_kb": hugePagesSize,
					"total_memory_gb": totalMemoryGB,
				},
				"설정 권장 (전체 메모리의 50-75%)",
			)
		}
		
		// HugePages가 설정되어 있지만 크기 확인
		hugePagesTotalMB := (hugePagesTotal * hugePagesSize) / 1024
		hugePagesPercentage := float64(hugePagesTotalMB) / float64(totalMemoryGB*1024) * 100
		
		if hugePagesPercentage < 25 {
			return r.CreateRuleResult(
				types.StatusFail,
				"HugePages 크기가 부족할 수 있습니다",
				"메모리 집약적 워크로드에는 전체 메모리의 50-75% 정도의 HugePages 설정이 권장됩니다",
				"vm.nr_hugepages 값을 증가시키세요",
				map[string]interface{}{
					"hugepages_total": hugePagesTotal,
					"hugepage_size_kb": hugePagesSize,
					"hugepages_percentage": hugePagesPercentage,
				},
				"전체 메모리의 50-75%",
			)
		}
	}
	
	return r.CreateRuleResult(
		types.StatusPass,
		"HugePages가 적절하게 설정되어 있습니다",
		"",
		"",
		map[string]interface{}{
			"hugepages_total": hugePagesTotal,
			"hugepage_size_kb": hugePagesSize,
			"total_memory_gb": totalMemoryGB,
		},
		"적절한 크기",
	)
}

// MemoryUsageRule은 메모리 사용률을 확인하는 규칙입니다.
type MemoryUsageRule struct {
	*BaseRule
}

func (r *MemoryUsageRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.Memory == nil || data.Memory.MemInfo == nil {
		return r.CreateRuleResult(types.StatusSkip, "메모리 데이터가 없습니다", "", "", nil, nil)
	}
	
	var memInfo map[string]interface{}
	if err := json.Unmarshal(data.Memory.MemInfo, &memInfo); err != nil {
		return r.CreateRuleResult(types.StatusError, "메모리 정보 파싱 실패", "", "", nil, nil)
	}
	
	var memTotal, memFree, memAvailable, buffers, cached float64
	
	if val, ok := memInfo["MemTotal"].(float64); ok {
		memTotal = val
	}
	if val, ok := memInfo["MemFree"].(float64); ok {
		memFree = val
	}
	if val, ok := memInfo["MemAvailable"].(float64); ok {
		memAvailable = val
	}
	if val, ok := memInfo["Buffers"].(float64); ok {
		buffers = val
	}
	if val, ok := memInfo["Cached"].(float64); ok {
		cached = val
	}
	
	if memTotal == 0 {
		return r.CreateRuleResult(types.StatusError, "메모리 총량 정보를 가져올 수 없습니다", "", "", nil, nil)
	}
	
	// 사용 가능한 메모리 계산 (MemAvailable을 우선 사용)
	var availableMemory float64
	if memAvailable > 0 {
		availableMemory = memAvailable
	} else {
		// MemAvailable이 없으면 근사치 계산
		availableMemory = memFree + buffers + cached
	}
	
	usedMemory := memTotal - availableMemory
	usagePercentage := (usedMemory / memTotal) * 100
	
	var status types.Status
	var message, details string
	
	if usagePercentage >= 95 {
		status = types.StatusFail
		message = "메모리 사용률이 매우 높습니다"
		details = "시스템이 메모리 부족 상태입니다. 즉시 조치가 필요합니다"
	} else if usagePercentage >= 85 {
		status = types.StatusFail
		message = "메모리 사용률이 높습니다"
		details = "메모리 부족으로 성능 저하가 발생할 수 있습니다"
	} else if usagePercentage >= 70 {
		status = types.StatusFail
		message = "메모리 사용률을 모니터링하세요"
		details = "메모리 사용률이 다소 높습니다"
	} else {
		status = types.StatusPass
		message = "메모리 사용률이 정상 범위입니다"
	}
	
	remediation := strings.Join([]string{
		"1. 불필요한 프로세스나 서비스 중지",
		"2. 메모리 사용량이 큰 애플리케이션 최적화",
		"3. 스왑 사용량 확인 및 조정",
		"4. 메모리 업그레이드 고려",
	}, "\n")
	
	return r.CreateRuleResult(
		status,
		message,
		details,
		remediation,
		map[string]interface{}{
			"total_mb":       int(memTotal / 1024),
			"used_mb":        int(usedMemory / 1024),
			"available_mb":   int(availableMemory / 1024),
			"usage_percent":  usagePercentage,
		},
		"< 70%",
	)
}

// OOMKillerRule은 OOM Killer 발생을 확인하는 규칙입니다.
type OOMKillerRule struct {
	*BaseRule
}

func (r *OOMKillerRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.Memory == nil {
		return r.CreateRuleResult(types.StatusSkip, "메모리 데이터가 없습니다", "", "", nil, nil)
	}
	
	oomKillCount := data.Memory.OOMKillCount
	
	if oomKillCount > 0 {
		remediation := strings.Join([]string{
			"1. dmesg | grep -i 'killed process' 로 OOM 발생 프로세스 확인",
			"2. 메모리 사용량 모니터링 강화",
			"3. 메모리 누수가 있는 애플리케이션 확인 및 수정",
			"4. 스왑 공간 증설 또는 메모리 업그레이드 고려",
			"5. cgroup 메모리 제한 설정 검토",
		}, "\n")
		
		var severity types.Severity
		var message, details string
		
		if oomKillCount >= 10 {
			severity = types.SeverityCritical
			message = "OOM Killer가 빈번하게 발생하고 있습니다"
			details = "시스템이 지속적으로 메모리 부족 상태에 있습니다. 즉시 조치가 필요합니다"
		} else {
			severity = types.SeverityHigh
			message = "OOM Killer가 발생했습니다"
			details = "메모리 부족으로 인해 프로세스가 강제 종료되었습니다"
		}
		
		return &types.RuleResult{
			RuleID:           r.id,
			RuleName:         r.name,
			Category:         r.category,
			Status:           types.StatusFail,
			Severity:         severity, // 동적으로 설정
			CurrentValue:     oomKillCount,
			RecommendedValue: 0,
			Message:          message,
			Details:          details,
			Remediation:      remediation,
		}
	}
	
	return r.CreateRuleResult(
		types.StatusPass,
		"OOM Killer가 발생하지 않았습니다",
		"",
		"",
		oomKillCount,
		0,
	)
}