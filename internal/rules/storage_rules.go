package rules

import (
	"context"
	"fmt"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// Storage 관련 규칙들을 등록합니다.
func registerStorageRules(engine *Engine) {
	// I/O 스케줄러 확인
	engine.RegisterRule(&IOSchedulerRule{
		BaseRule: NewBaseRule(
			"STO-001",
			"I/O 스케줄러 확인",
			"storage",
			types.SeverityMedium,
			"디스크 I/O 스케줄러가 워크로드에 적합하게 설정되어 있는지 확인합니다.",
			[]types.Role{types.RoleStorage, types.RoleDatabase},
		),
	})
}

// IOSchedulerRule은 I/O 스케줄러를 확인하는 규칙입니다.
type IOSchedulerRule struct {
	*BaseRule
}

func (r *IOSchedulerRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.Storage == nil || data.Storage.IOScheduler == nil {
		return r.CreateRuleResult(types.StatusSkip, "스토리지 I/O 스케줄러 데이터가 없습니다", "", "", nil, nil)
	}
	
	schedulers := data.Storage.IOScheduler
	issues := []string{}
	recommendations := map[string]string{}
	
	for device, scheduler := range schedulers {
		var preferredSchedulers []string
		
		// SSD/NVMe는 noop 또는 none, HDD는 deadline 또는 mq-deadline
		if strings.Contains(device, "nvme") || strings.Contains(device, "ssd") {
			preferredSchedulers = []string{"none", "noop"}
		} else {
			preferredSchedulers = []string{"mq-deadline", "deadline"}
		}
		
		isOptimal := false
		for _, preferred := range preferredSchedulers {
			if scheduler == preferred {
				isOptimal = true
				break
			}
		}
		
		if !isOptimal {
			issues = append(issues, fmt.Sprintf("%s: %s", device, scheduler))
			recommendations[device] = strings.Join(preferredSchedulers, " 또는 ")
		}
	}
	
	if len(issues) > 0 {
		remediation := "echo mq-deadline | sudo tee /sys/block/DEV/queue/scheduler\n" +
			"# 영구 설정을 위해 /etc/udev/rules.d/60-ioschedulers.rules 파일 생성"
		
		return r.CreateRuleResult(
			types.StatusFail,
			"I/O 스케줄러가 최적화되지 않았습니다",
			strings.Join(issues, ", "),
			remediation,
			schedulers,
			recommendations,
		)
	}
	
	return r.CreateRuleResult(
		types.StatusPass,
		"I/O 스케줄러가 적절하게 설정되어 있습니다",
		"",
		"",
		schedulers,
		"워크로드에 맞는 스케줄러",
	)
}