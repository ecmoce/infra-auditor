// Package rules는 시스템 점검 규칙 엔진을 제공합니다.
package rules

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// Rule은 개별 점검 규칙 인터페이스입니다.
type Rule interface {
	// ID는 규칙의 고유 식별자를 반환합니다.
	ID() string
	
	// Name은 규칙의 이름을 반환합니다.
	Name() string
	
	// Category는 규칙의 카테고리를 반환합니다.
	Category() string
	
	// Severity는 규칙의 심각도를 반환합니다.
	Severity() types.Severity
	
	// Description은 규칙의 설명을 반환합니다.
	Description() string
	
	// Check는 규칙을 실행하고 결과를 반환합니다.
	Check(ctx context.Context, data *types.CollectorData) *types.RuleResult
	
	// IsApplicable은 현재 시스템에 해당 규칙이 적용 가능한지 확인합니다.
	IsApplicable(role types.Role) bool
}

// BaseRule은 공통 규칙 기능을 제공하는 기본 구조체입니다.
type BaseRule struct {
	id          string
	name        string
	category    string
	severity    types.Severity
	description string
	roles       []types.Role // 적용 가능한 역할들
}

// NewBaseRule은 새 기본 규칙을 생성합니다.
func NewBaseRule(id, name, category string, severity types.Severity, description string, roles []types.Role) *BaseRule {
	return &BaseRule{
		id:          id,
		name:        name,
		category:    category,
		severity:    severity,
		description: description,
		roles:       roles,
	}
}

// ID는 규칙의 고유 식별자를 반환합니다.
func (br *BaseRule) ID() string {
	return br.id
}

// Name은 규칙의 이름을 반환합니다.
func (br *BaseRule) Name() string {
	return br.name
}

// Category는 규칙의 카테고리를 반환합니다.
func (br *BaseRule) Category() string {
	return br.category
}

// Severity는 규칙의 심각도를 반환합니다.
func (br *BaseRule) Severity() types.Severity {
	return br.severity
}

// Description은 규칙의 설명을 반환합니다.
func (br *BaseRule) Description() string {
	return br.description
}

// IsApplicable은 현재 시스템에 해당 규칙이 적용 가능한지 확인합니다.
func (br *BaseRule) IsApplicable(role types.Role) bool {
	// 역할이 지정되지 않았으면 모든 역할에 적용
	if len(br.roles) == 0 {
		return true
	}
	
	for _, r := range br.roles {
		if r == role {
			return true
		}
	}
	
	return false
}

// CreateRuleResult는 규칙 결과를 생성하는 헬퍼 함수입니다.
func (br *BaseRule) CreateRuleResult(status types.Status, message, details, remediation string, currentValue, recommendedValue interface{}) *types.RuleResult {
	return &types.RuleResult{
		RuleID:           br.id,
		RuleName:         br.name,
		Category:         br.category,
		Status:           status,
		Severity:         br.severity,
		CurrentValue:     currentValue,
		RecommendedValue: recommendedValue,
		Message:          message,
		Details:          details,
		Remediation:      remediation,
		ExecutionTime:    0, // 엔진에서 측정
	}
}

// Engine은 규칙 실행 엔진입니다.
type Engine struct {
	rules map[string]Rule
}

// NewEngine은 새 규칙 엔진을 생성합니다.
func NewEngine() *Engine {
	return &Engine{
		rules: make(map[string]Rule),
	}
}

// RegisterRule은 규칙을 등록합니다.
func (e *Engine) RegisterRule(rule Rule) {
	e.rules[rule.ID()] = rule
	slog.Debug("규칙 등록됨", "id", rule.ID(), "name", rule.Name(), "category", rule.Category())
}

// RunRules는 등록된 모든 규칙을 실행합니다.
func (e *Engine) RunRules(ctx context.Context, data *types.CollectorData, options RunOptions) ([]types.RuleResult, error) {
	slog.Info("규칙 실행 시작", "total_rules", len(e.rules))
	
	var results []types.RuleResult
	
	for ruleID, rule := range e.rules {
		// 규칙 필터링
		if !e.shouldRunRule(rule, options) {
			slog.Debug("규칙 스킵", "id", ruleID, "reason", "filtered")
			continue
		}
		
		// 역할 적용 가능성 확인
		if !rule.IsApplicable(options.TargetRole) {
			slog.Debug("규칙 스킵", "id", ruleID, "reason", "not_applicable", "role", options.TargetRole)
			continue
		}
		
		start := time.Now()
		
		// 규칙 실행
		result := rule.Check(ctx, data)
		if result == nil {
			slog.Warn("규칙 결과가 nil", "id", ruleID)
			continue
		}
		
		// 실행 시간 측정
		duration := time.Since(start)
		result.ExecutionTime = float64(duration.Nanoseconds()) / 1e6 // 밀리초로 변환
		
		slog.Debug("규칙 실행 완료", 
			"id", ruleID, 
			"status", result.Status,
			"duration_ms", result.ExecutionTime)
		
		// 통과한 규칙 포함 여부 확인
		if result.Status == types.StatusPass && !options.IncludePassed {
			continue
		}
		
		results = append(results, *result)
	}
	
	slog.Info("규칙 실행 완료", "executed_rules", len(results))
	return results, nil
}

// shouldRunRule은 규칙을 실행해야 하는지 확인합니다.
func (e *Engine) shouldRunRule(rule Rule, options RunOptions) bool {
	// 카테고리 필터
	if len(options.Categories) > 0 && !contains(options.Categories, rule.Category()) {
		return false
	}
	
	// 심각도 필터
	if len(options.Severities) > 0 && !containsSeverity(options.Severities, rule.Severity()) {
		return false
	}
	
	// 규칙 ID 필터 (포함)
	if len(options.RuleIDs) > 0 && !contains(options.RuleIDs, rule.ID()) {
		return false
	}
	
	// 규칙 ID 필터 (제외)
	if len(options.ExcludeRules) > 0 && contains(options.ExcludeRules, rule.ID()) {
		return false
	}
	
	return true
}

// RunOptions는 규칙 실행 옵션입니다.
type RunOptions struct {
	TargetRole      types.Role
	Categories      []string
	Severities      []types.Severity
	RuleIDs         []string
	ExcludeRules    []string
	IncludePassed   bool
}

// GetRule은 지정된 ID의 규칙을 반환합니다.
func (e *Engine) GetRule(id string) (Rule, bool) {
	rule, exists := e.rules[id]
	return rule, exists
}

// ListRules는 등록된 모든 규칙 목록을 반환합니다.
func (e *Engine) ListRules() map[string]Rule {
	result := make(map[string]Rule)
	for id, rule := range e.rules {
		result[id] = rule
	}
	return result
}

// GetRulesByCategory는 카테고리별 규칙 목록을 반환합니다.
func (e *Engine) GetRulesByCategory(category string) []Rule {
	var rules []Rule
	for _, rule := range e.rules {
		if rule.Category() == category {
			rules = append(rules, rule)
		}
	}
	return rules
}

// CreateDefaultEngine은 기본 규칙들이 등록된 엔진을 생성합니다.
func CreateDefaultEngine() *Engine {
	engine := NewEngine()
	
	// 모든 기본 규칙 등록
	registerCPURules(engine)
	registerMemoryRules(engine)
	registerNetworkRules(engine)
	registerStorageRules(engine)
	registerKernelRules(engine)
	registerServiceRules(engine)
	
	return engine
}

// 헬퍼 함수들

// contains는 슬라이스에 특정 문자열이 포함되어 있는지 확인합니다.
func contains(slice []string, item string) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}

// containsSeverity는 심각도 슬라이스에 특정 심각도가 포함되어 있는지 확인합니다.
func containsSeverity(slice []types.Severity, item types.Severity) bool {
	for _, s := range slice {
		if s == item {
			return true
		}
	}
	return false
}

// ParseSeveritySlice는 문자열 슬라이스를 Severity 슬라이스로 변환합니다.
func ParseSeveritySlice(severities []string) []types.Severity {
	var result []types.Severity
	for _, s := range severities {
		result = append(result, types.Severity(s))
	}
	return result
}

// ValidateRuleResult는 규칙 결과를 검증합니다.
func ValidateRuleResult(result *types.RuleResult) error {
	if result == nil {
		return fmt.Errorf("규칙 결과가 nil입니다")
	}
	
	if result.RuleID == "" {
		return fmt.Errorf("규칙 ID가 비어있습니다")
	}
	
	if result.RuleName == "" {
		return fmt.Errorf("규칙 이름이 비어있습니다")
	}
	
	validStatuses := map[types.Status]bool{
		types.StatusPass:    true,
		types.StatusFail:    true,
		types.StatusSkip:    true,
		types.StatusError:   true,
		types.StatusUnknown: true,
	}
	
	if !validStatuses[result.Status] {
		return fmt.Errorf("유효하지 않은 상태: %s", result.Status)
	}
	
	return nil
}