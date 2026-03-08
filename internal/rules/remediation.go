package rules

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// Remediator는 자동 수정 스크립트 생성기입니다.
type Remediator struct{}

// RemediateOptions는 수정 옵션입니다.
type RemediateOptions struct {
	Severities  []string
	Categories  []string
	RuleIDs     []string
	DryRun      bool
	NoBackup    bool
}

// NewRemediator는 새 수정 스크립트 생성기를 생성합니다.
func NewRemediator() *Remediator {
	return &Remediator{}
}

// GenerateScript는 보고서를 기반으로 수정 스크립트를 생성합니다.
func (r *Remediator) GenerateScript(report *types.AuditReport, options RemediateOptions) (*types.RemediationScript, error) {
	scriptID := fmt.Sprintf("remediate-%d", time.Now().Unix())
	
	var targetRules []string
	var commands []types.Command
	var requiresReboot bool
	
	// 실패한 규칙들 필터링
	for _, result := range report.RuleResults {
		if result.Status != types.StatusFail {
			continue
		}
		
		// 옵션에 따른 필터링
		if !r.shouldIncludeRule(result, options) {
			continue
		}
		
		if result.Remediation == "" {
			continue
		}
		
		targetRules = append(targetRules, result.RuleID)
		
		// 수정 명령어 파싱 및 추가
		remediationCommands := r.parseRemediationCommands(result)
		commands = append(commands, remediationCommands...)
		
		// 재부팅이 필요한 규칙들 확인
		if r.requiresReboot(result.RuleID) {
			requiresReboot = true
		}
	}
	
	// 백업 작업 추가
	var backupActions []types.BackupAction
	if !options.NoBackup {
		backupActions = r.generateBackupActions(targetRules)
	}
	
	// 검증 명령어 생성
	verificationCommands := r.generateVerificationCommands(targetRules)
	
	// 롤백 명령어 생성
	rollbackCommands := r.generateRollbackCommands(targetRules)
	
	script := &types.RemediationScript{
		ScriptID:        scriptID,
		TargetRules:     targetRules,
		Commands:        commands,
		Prerequisites:   r.generatePrerequisites(),
		Risks:           r.generateRisks(),
		Backup:          backupActions,
		Verification:    verificationCommands,
		Rollback:        rollbackCommands,
		ExecutionTime:   float64(len(commands) * 5), // 명령어당 5초 예상
		RequiresReboot:  requiresReboot,
		GeneratedAt:     time.Now(),
	}
	
	return script, nil
}

// shouldIncludeRule은 규칙이 수정 대상에 포함되어야 하는지 확인합니다.
func (r *Remediator) shouldIncludeRule(result types.RuleResult, options RemediateOptions) bool {
	// 심각도 필터
	if len(options.Severities) > 0 {
		found := false
		for _, severity := range options.Severities {
			if string(result.Severity) == severity {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}
	
	// 카테고리 필터
	if len(options.Categories) > 0 {
		found := false
		for _, category := range options.Categories {
			if result.Category == category {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}
	
	// 규칙 ID 필터
	if len(options.RuleIDs) > 0 {
		found := false
		for _, ruleID := range options.RuleIDs {
			if result.RuleID == ruleID {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}
	
	return true
}

// parseRemediationCommands는 수정 명령어를 파싱합니다.
func (r *Remediator) parseRemediationCommands(result types.RuleResult) []types.Command {
	var commands []types.Command
	
	// 개행으로 분리된 여러 명령어 처리
	lines := strings.Split(result.Remediation, "\n")
	
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		
		command := types.Command{
			Description:  fmt.Sprintf("Fix for %s", result.RuleID),
			Command:      line,
			Timeout:      30, // 30초 기본 타임아웃
			RequiresSudo: strings.Contains(line, "sudo") || strings.Contains(line, "/etc/"),
		}
		
		commands = append(commands, command)
	}
	
	return commands
}

// requiresReboot는 규칙 수정 후 재부팅이 필요한지 확인합니다.
func (r *Remediator) requiresReboot(ruleID string) bool {
	// 커널 매개변수 관련 규칙들은 재부팅 권장
	rebootRules := []string{
		"KER-001", // shmmax
		"MEM-002", // hugepages
	}
	
	for _, rule := range rebootRules {
		if ruleID == rule {
			return true
		}
	}
	
	return false
}

// generateBackupActions는 백업 작업을 생성합니다.
func (r *Remediator) generateBackupActions(targetRules []string) []types.BackupAction {
	var actions []types.BackupAction
	
	timestamp := time.Now().Format("20060102-150405")
	
	// /etc/sysctl.conf 백업
	actions = append(actions, types.BackupAction{
		Type:        "file",
		Source:      "/etc/sysctl.conf",
		Destination: fmt.Sprintf("/tmp/sysctl.conf.backup.%s", timestamp),
		Description: "sysctl 설정 백업",
	})
	
	// 현재 커널 매개변수 백업
	actions = append(actions, types.BackupAction{
		Type:        "command",
		Command:     fmt.Sprintf("sysctl -a > /tmp/sysctl.current.%s", timestamp),
		Description: "현재 커널 매개변수 백업",
	})
	
	return actions
}

// generateVerificationCommands는 검증 명령어를 생성합니다.
func (r *Remediator) generateVerificationCommands(targetRules []string) []types.Command {
	var commands []types.Command
	
	// sysctl 설정 확인
	commands = append(commands, types.Command{
		Description: "sysctl 설정 확인",
		Command:     "sysctl -p",
		Timeout:     10,
	})
	
	// 서비스 상태 확인
	commands = append(commands, types.Command{
		Description: "시스템 서비스 상태 확인",
		Command:     "systemctl status",
		Timeout:     15,
		IgnoreErrors: true,
	})
	
	return commands
}

// generateRollbackCommands는 롤백 명령어를 생성합니다.
func (r *Remediator) generateRollbackCommands(targetRules []string) []types.Command {
	var commands []types.Command
	
	timestamp := time.Now().Format("20060102-150405")
	
	// 백업된 설정 복원
	commands = append(commands, types.Command{
		Description: "sysctl 설정 복원",
		Command:     fmt.Sprintf("cp /tmp/sysctl.conf.backup.%s /etc/sysctl.conf", timestamp),
		Timeout:     10,
		RequiresSudo: true,
	})
	
	commands = append(commands, types.Command{
		Description: "sysctl 설정 적용",
		Command:     "sysctl -p",
		Timeout:     10,
		RequiresSudo: true,
	})
	
	return commands
}

// generatePrerequisites는 사전 요구사항을 생성합니다.
func (r *Remediator) generatePrerequisites() []string {
	return []string{
		"root 권한 또는 sudo 권한 필요",
		"시스템 백업 완료 확인",
		"유지보수 시간대에 실행 권장",
		"충분한 디스크 공간 확보",
	}
}

// generateRisks는 위험 요소를 생성합니다.
func (r *Remediator) generateRisks() []string {
	return []string{
		"시스템 설정 변경으로 인한 서비스 중단 가능성",
		"일부 설정은 재부팅 후 적용됨",
		"백업 없이 실행 시 복구 불가능",
		"애플리케이션 호환성 문제 발생 가능",
	}
}

// WriteScriptToFile은 스크립트를 파일에 저장합니다.
func WriteScriptToFile(script *types.RemediationScript, filePath string) error {
	// JSON 형식으로 저장
	data, err := json.MarshalIndent(script, "", "  ")
	if err != nil {
		return err
	}
	
	return os.WriteFile(filePath, data, 0644)
}

// WriteScriptToStdout은 스크립트를 표준 출력에 출력합니다.
func WriteScriptToStdout(script *types.RemediationScript) error {
	fmt.Printf("=== Remediation Script ===\n")
	fmt.Printf("Script ID: %s\n", script.ScriptID)
	fmt.Printf("Target Rules: %d\n", len(script.TargetRules))
	fmt.Printf("Commands: %d\n", len(script.Commands))
	fmt.Printf("Requires Reboot: %t\n", script.RequiresReboot)
	fmt.Printf("Estimated Time: %.0f seconds\n\n", script.ExecutionTime)
	
	if len(script.Prerequisites) > 0 {
		fmt.Printf("=== Prerequisites ===\n")
		for _, prereq := range script.Prerequisites {
			fmt.Printf("- %s\n", prereq)
		}
		fmt.Printf("\n")
	}
	
	if len(script.Risks) > 0 {
		fmt.Printf("=== Risks ===\n")
		for _, risk := range script.Risks {
			fmt.Printf("- %s\n", risk)
		}
		fmt.Printf("\n")
	}
	
	if len(script.Backup) > 0 {
		fmt.Printf("=== Backup Actions ===\n")
		for _, backup := range script.Backup {
			fmt.Printf("- %s: %s\n", backup.Type, backup.Description)
		}
		fmt.Printf("\n")
	}
	
	fmt.Printf("=== Commands ===\n")
	for i, cmd := range script.Commands {
		fmt.Printf("%d. %s\n", i+1, cmd.Description)
		fmt.Printf("   Command: %s\n", cmd.Command)
		if cmd.RequiresSudo {
			fmt.Printf("   Requires: sudo\n")
		}
		fmt.Printf("\n")
	}
	
	return nil
}