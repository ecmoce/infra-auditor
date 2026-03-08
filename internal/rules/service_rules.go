package rules

import (
	"context"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// Service 관련 규칙들을 등록합니다.
func registerServiceRules(engine *Engine) {
	// 실행 중인 서비스 개수 확인
	engine.RegisterRule(&ServiceCountRule{
		BaseRule: NewBaseRule(
			"SVC-001",
			"실행 중인 서비스 개수 확인",
			"service",
			types.SeverityLow,
			"불필요한 서비스가 너무 많이 실행되고 있는지 확인합니다.",
			nil, // 모든 역할에 적용
		),
	})
}

// ServiceCountRule은 실행 중인 서비스 개수를 확인하는 규칙입니다.
type ServiceCountRule struct {
	*BaseRule
}

func (r *ServiceCountRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.Services == nil {
		return r.CreateRuleResult(types.StatusSkip, "서비스 데이터가 없습니다", "", "", nil, nil)
	}
	
	serviceCount := len(data.Services.RunningServices)
	
	// 일반적으로 서버에서 50개 이상의 서비스가 실행되면 검토 필요
	if serviceCount > 50 {
		remediation := strings.Join([]string{
			"systemctl list-units --type=service --state=running",
			"불필요한 서비스들을 확인하고 비활성화:",
			"sudo systemctl disable SERVICE_NAME",
			"sudo systemctl stop SERVICE_NAME",
		}, "\n")
		
		return r.CreateRuleResult(
			types.StatusFail,
			"실행 중인 서비스가 많습니다",
			"불필요한 서비스들이 시스템 리소스를 사용할 수 있습니다",
			remediation,
			serviceCount,
			"< 50",
		)
	}
	
	return r.CreateRuleResult(
		types.StatusPass,
		"실행 중인 서비스 개수가 적절합니다",
		"",
		"",
		serviceCount,
		"적정 수준",
	)
}