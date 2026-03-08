package rules

import (
	"context"
	"strconv"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// Kernel 관련 규칙들을 등록합니다.
func registerKernelRules(engine *Engine) {
	// Shmmax 설정 확인
	engine.RegisterRule(&ShmmaxRule{
		BaseRule: NewBaseRule(
			"KER-001",
			"Shmmax 설정 확인",
			"kernel",
			types.SeverityMedium,
			"공유 메모리 세그먼트 최대 크기가 적절히 설정되어 있는지 확인합니다.",
			[]types.Role{types.RoleDatabase},
		),
	})
}

// ShmmaxRule은 shmmax 설정을 확인하는 규칙입니다.
type ShmmaxRule struct {
	*BaseRule
}

func (r *ShmmaxRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.Kernel == nil || data.Kernel.SysctlParams == nil {
		return r.CreateRuleResult(types.StatusSkip, "커널 sysctl 데이터가 없습니다", "", "", nil, nil)
	}
	
	sysctlParams := data.Kernel.SysctlParams
	
	shmmaxStr, exists := sysctlParams["kernel.shmmax"]
	if !exists {
		return r.CreateRuleResult(types.StatusError, "shmmax 정보를 가져올 수 없습니다", "", "", nil, nil)
	}
	
	shmmax, err := strconv.ParseInt(shmmaxStr, 10, 64)
	if err != nil {
		return r.CreateRuleResult(types.StatusError, "shmmax 값 파싱 실패", "", "", shmmaxStr, nil)
	}
	
	// 권장값: 전체 메모리의 50% 이상 (최소 1GB)
	recommendedMin := int64(1024 * 1024 * 1024) // 1GB
	
	if shmmax < recommendedMin {
		remediation := "echo 'kernel.shmmax = 1073741824' >> /etc/sysctl.conf && sysctl -p"
		
		return r.CreateRuleResult(
			types.StatusFail,
			"Shmmax 값이 너무 작습니다",
			"데이터베이스나 공유 메모리 사용 애플리케이션의 성능에 영향을 줄 수 있습니다",
			remediation,
			shmmax,
			recommendedMin,
		)
	}
	
	return r.CreateRuleResult(
		types.StatusPass,
		"Shmmax가 적절하게 설정되어 있습니다",
		"",
		"",
		shmmax,
		">= 1GB",
	)
}