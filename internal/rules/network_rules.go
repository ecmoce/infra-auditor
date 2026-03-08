package rules

import (
	"context"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// Network 관련 규칙들을 등록합니다.
func registerNetworkRules(engine *Engine) {
	// TCP 버퍼 크기 확인
	engine.RegisterRule(&TCPBufferRule{
		BaseRule: NewBaseRule(
			"NET-001",
			"TCP 버퍼 크기 확인",
			"network",
			types.SeverityMedium,
			"TCP 송수신 버퍼 크기가 적절하게 설정되어 있는지 확인합니다.",
			nil, // 모든 역할에 적용
		),
	})
	
	// TCP Congestion Control 확인
	engine.RegisterRule(&TCPCongestionControlRule{
		BaseRule: NewBaseRule(
			"NET-002",
			"TCP Congestion Control 확인",
			"network",
			types.SeverityMedium,
			"TCP 혼잡 제어 알고리즘이 최적으로 설정되어 있는지 확인합니다.",
			[]types.Role{types.RoleNetwork, types.RoleWeb},
		),
	})
}

// TCPBufferRule은 TCP 버퍼 크기를 확인하는 규칙입니다.
type TCPBufferRule struct {
	*BaseRule
}

func (r *TCPBufferRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.Network == nil || data.Network.BufferSizes == nil {
		return r.CreateRuleResult(types.StatusSkip, "네트워크 버퍼 데이터가 없습니다", "", "", nil, nil)
	}
	
	bufferSizes := data.Network.BufferSizes
	
	// 권장 버퍼 크기 (바이트)
	recommendedRmemDefault := 262144 // 256KB
	recommendedWmemDefault := 262144 // 256KB
	recommendedRmemMax := 16777216    // 16MB
	recommendedWmemMax := 16777216    // 16MB
	
	issues := []string{}
	
	if rmemDefault, exists := bufferSizes["rmem_default"]; exists {
		if rmemDefault < recommendedRmemDefault {
			issues = append(issues, "rmem_default가 권장값보다 낮습니다")
		}
	}
	
	if wmemDefault, exists := bufferSizes["wmem_default"]; exists {
		if wmemDefault < recommendedWmemDefault {
			issues = append(issues, "wmem_default가 권장값보다 낮습니다")
		}
	}
	
	if rmemMax, exists := bufferSizes["rmem_max"]; exists {
		if rmemMax < recommendedRmemMax {
			issues = append(issues, "rmem_max가 권장값보다 낮습니다")
		}
	}
	
	if wmemMax, exists := bufferSizes["wmem_max"]; exists {
		if wmemMax < recommendedWmemMax {
			issues = append(issues, "wmem_max가 권장값보다 낮습니다")
		}
	}
	
	if len(issues) > 0 {
		remediation := strings.Join([]string{
			"echo 'net.core.rmem_default = 262144' >> /etc/sysctl.conf",
			"echo 'net.core.wmem_default = 262144' >> /etc/sysctl.conf", 
			"echo 'net.core.rmem_max = 16777216' >> /etc/sysctl.conf",
			"echo 'net.core.wmem_max = 16777216' >> /etc/sysctl.conf",
			"sysctl -p",
		}, "\n")
		
		return r.CreateRuleResult(
			types.StatusFail,
			"TCP 버퍼 크기가 최적화되지 않았습니다",
			strings.Join(issues, ", "),
			remediation,
			bufferSizes,
			map[string]int{
				"rmem_default": recommendedRmemDefault,
				"wmem_default": recommendedWmemDefault,
				"rmem_max":     recommendedRmemMax,
				"wmem_max":     recommendedWmemMax,
			},
		)
	}
	
	return r.CreateRuleResult(
		types.StatusPass,
		"TCP 버퍼 크기가 적절하게 설정되어 있습니다",
		"",
		"",
		bufferSizes,
		"권장값 이상",
	)
}

// TCPCongestionControlRule은 TCP 혼잡 제어를 확인하는 규칙입니다.
type TCPCongestionControlRule struct {
	*BaseRule
}

func (r *TCPCongestionControlRule) Check(ctx context.Context, data *types.CollectorData) *types.RuleResult {
	if data.Network == nil || data.Network.TCPSettings == nil {
		return r.CreateRuleResult(types.StatusSkip, "TCP 설정 데이터가 없습니다", "", "", nil, nil)
	}
	
	tcpSettings := data.Network.TCPSettings
	
	congestionControl, exists := tcpSettings["tcp_congestion_control"]
	if !exists {
		return r.CreateRuleResult(types.StatusError, "TCP congestion control 정보를 가져올 수 없습니다", "", "", nil, nil)
	}
	
	currentAlgorithm := ""
	if cc, ok := congestionControl.(string); ok {
		currentAlgorithm = cc
	}
	
	// 현대적이고 효율적인 혼잡 제어 알고리즘
	preferredAlgorithms := []string{"bbr", "cubic", "htcp"}
	
	for _, preferred := range preferredAlgorithms {
		if currentAlgorithm == preferred {
			return r.CreateRuleResult(
				types.StatusPass,
				"TCP 혼잡 제어 알고리즘이 최적으로 설정되어 있습니다",
				"",
				"",
				currentAlgorithm,
				preferredAlgorithms,
			)
		}
	}
	
	remediation := strings.Join([]string{
		"# BBR 사용 (권장, 높은 대역폭-지연 환경에 최적)",
		"echo 'net.ipv4.tcp_congestion_control = bbr' >> /etc/sysctl.conf",
		"sysctl -p",
		"# 또는 CUBIC 사용 (기본값, 안정적)",
		"echo 'net.ipv4.tcp_congestion_control = cubic' >> /etc/sysctl.conf",
	}, "\n")
	
	return r.CreateRuleResult(
		types.StatusFail,
		"TCP 혼잡 제어 알고리즘을 최적화하세요",
		"현재 알고리즘이 최신 네트워크 환경에 최적이 아닐 수 있습니다",
		remediation,
		currentAlgorithm,
		"bbr, cubic, 또는 htcp",
	)
}