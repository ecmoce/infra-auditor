// Package report는 시스템 점검 보고서 생성 기능을 제공합니다.
package report

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/ecmoce/infra-auditor/internal/collector"
	"github.com/ecmoce/infra-auditor/internal/rules"
	"github.com/ecmoce/infra-auditor/pkg/types"
)

// Generator는 보고서 생성기입니다.
type Generator struct {
	version string
	schema  string
	
	collectorManager *collector.Manager
	rulesEngine      *rules.Engine
}

// Options는 보고서 생성 옵션입니다.
type Options struct {
	TargetRole      types.Role
	Categories      []string
	Severities      []string
	RuleIDs         []string
	ExcludeRules    []string
	IncludePassed   bool
	CollectOnly     bool
}

// NewGenerator는 새 보고서 생성기를 생성합니다.
func NewGenerator(version, schema string) *Generator {
	return &Generator{
		version:          version,
		schema:           schema,
		collectorManager: collector.CreateDefaultManager(),
		rulesEngine:      rules.CreateDefaultEngine(),
	}
}

// Generate는 시스템 점검을 수행하고 보고서를 생성합니다.
func (g *Generator) Generate(options Options) (*types.AuditReport, error) {
	slog.Info("보고서 생성 시작", "target_role", options.TargetRole)
	
	start := time.Now()
	
	// 1. 시스템 정보 수집
	systemInfo, err := g.collectSystemInfo(options.TargetRole)
	if err != nil {
		return nil, fmt.Errorf("시스템 정보 수집 실패: %w", err)
	}
	
	// 2. 데이터 수집
	ctx := context.Background()
	collectorData, err := g.collectorManager.CollectAll(ctx, options.Categories)
	if err != nil {
		return nil, fmt.Errorf("데이터 수집 실패: %w", err)
	}
	
	// 3. 규칙 실행 (CollectOnly가 아닌 경우에만)
	var ruleResults []types.RuleResult
	if !options.CollectOnly {
		rulesOptions := rules.RunOptions{
			TargetRole:      options.TargetRole,
			Categories:      options.Categories,
			Severities:      rules.ParseSeveritySlice(options.Severities),
			RuleIDs:         options.RuleIDs,
			ExcludeRules:    options.ExcludeRules,
			IncludePassed:   options.IncludePassed,
		}
		
		ruleResults, err = g.rulesEngine.RunRules(ctx, collectorData, rulesOptions)
		if err != nil {
			return nil, fmt.Errorf("규칙 실행 실패: %w", err)
		}
	}
	
	// 4. 보고서 조립
	duration := time.Since(start)
	reportID := fmt.Sprintf("audit-%d", time.Now().Unix())
	
	report := &types.AuditReport{
		ReportID:      reportID,
		SystemInfo:    *systemInfo,
		CollectorData: *collectorData,
		RuleResults:   ruleResults,
		Summary:       g.generateSummary(ruleResults, duration),
		Metadata:      g.generateMetadata(options.TargetRole),
		GeneratedAt:   time.Now(),
	}
	
	slog.Info("보고서 생성 완료", 
		"report_id", reportID,
		"total_rules", report.Summary.TotalRules,
		"failed_rules", report.Summary.FailedRules,
		"duration_ms", duration.Milliseconds())
	
	return report, nil
}

// collectSystemInfo는 시스템 기본 정보를 수집합니다.
func (g *Generator) collectSystemInfo(detectedRole types.Role) (*types.SystemInfo, error) {
	hostname, _ := os.Hostname()
	
	systemInfo := &types.SystemInfo{
		Hostname:        hostname,
		OS:              "linux", // 현재는 리눅스만 지원
		DetectedRole:    detectedRole,
		Timestamp:       time.Now(),
		Environment:     make(map[string]string),
	}
	
	// 커널 버전 수집
	if data, err := os.ReadFile("/proc/version"); err == nil {
		systemInfo.Kernel = string(data)
	}
	
	// 아키텍처 정보
	if data, err := os.ReadFile("/proc/cpuinfo"); err == nil {
		// 간단한 아키텍처 추출 (실제로는 더 정교한 파싱 필요)
		if strings.Contains(string(data), "x86_64") {
			systemInfo.Architecture = "x86_64"
		} else if strings.Contains(string(data), "aarch64") {
			systemInfo.Architecture = "aarch64"
		} else {
			systemInfo.Architecture = "unknown"
		}
	}
	
	// CPU 코어 수
	if data, err := os.ReadFile("/proc/cpuinfo"); err == nil {
		cores := 0
		lines := strings.Split(string(data), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, "processor") {
				cores++
			}
		}
		systemInfo.CPUCores = cores
	}
	
	// 메모리 총량
	if data, err := os.ReadFile("/proc/meminfo"); err == nil {
		lines := strings.Split(string(data), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, "MemTotal:") {
				fields := strings.Fields(line)
				if len(fields) >= 2 {
					if memKB, err := strconv.ParseInt(fields[1], 10, 64); err == nil {
						systemInfo.MemoryTotal = memKB * 1024 // KB -> Bytes
					}
				}
				break
			}
		}
	}
	
	return systemInfo, nil
}

// generateSummary는 보고서 요약 정보를 생성합니다.
func (g *Generator) generateSummary(results []types.RuleResult, duration time.Duration) types.ReportSummary {
	summary := types.ReportSummary{
		TotalRules:      len(results),
		SeverityCount:   make(map[types.Severity]int),
		CategoryCount:   make(map[string]int),
		ExecutionTime:   float64(duration.Nanoseconds()) / 1e6, // 밀리초
	}
	
	for _, result := range results {
		// 상태별 카운트
		switch result.Status {
		case types.StatusPass:
			summary.PassedRules++
		case types.StatusFail:
			summary.FailedRules++
		case types.StatusSkip:
			summary.SkippedRules++
		case types.StatusError:
			summary.ErrorRules++
		}
		
		// 심각도별 카운트 (실패한 규칙만)
		if result.Status == types.StatusFail {
			summary.SeverityCount[result.Severity]++
		}
		
		// 카테고리별 카운트
		summary.CategoryCount[result.Category]++
	}
	
	// 컴플라이언스 점수 계산 (통과율)
	if summary.TotalRules > 0 {
		summary.ComplianceScore = float64(summary.PassedRules) / float64(summary.TotalRules) * 100
	}
	
	return summary
}

// generateMetadata는 보고서 메타데이터를 생성합니다.
func (g *Generator) generateMetadata(targetRole types.Role) types.ReportMetadata {
	return types.ReportMetadata{
		Version:        g.version,
		Schema:         g.schema,
		Generator:      "infra-auditor-go",
		TargetRole:     targetRole,
		RulesetVersion: "1.0.0",
		Tags:           []string{"performance", "tuning", "linux"},
		CustomFields:   make(map[string]interface{}),
	}
}

// LoadFromFile은 파일에서 보고서를 로드합니다.
func LoadFromFile(filePath string) (*types.AuditReport, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, err
	}
	
	var report types.AuditReport
	if err := json.Unmarshal(data, &report); err != nil {
		return nil, err
	}
	
	return &report, nil
}

// WriteToFile은 보고서를 파일에 저장합니다.
func WriteToFile(report *types.AuditReport, filePath, format string) error {
	var data []byte
	var err error
	
	switch format {
	case "json":
		data, err = json.MarshalIndent(report, "", "  ")
	case "yaml":
		// 간단한 구현을 위해 JSON으로 대체 (실제로는 yaml 패키지 사용)
		data, err = json.MarshalIndent(report, "", "  ")
	default:
		return fmt.Errorf("지원되지 않는 형식: %s", format)
	}
	
	if err != nil {
		return err
	}
	
	return os.WriteFile(filePath, data, 0644)
}

// WriteToStdout은 보고서를 표준 출력에 출력합니다.
func WriteToStdout(report *types.AuditReport, format string) error {
	var data []byte
	var err error
	
	switch format {
	case "json":
		data, err = json.MarshalIndent(report, "", "  ")
	case "yaml":
		data, err = json.MarshalIndent(report, "", "  ")
	case "table":
		// 테이블 형식으로 요약 출력
		fmt.Printf("=== Infrastructure Audit Report ===\n")
		fmt.Printf("Report ID: %s\n", report.ReportID)
		fmt.Printf("System: %s (%s)\n", report.SystemInfo.Hostname, report.SystemInfo.DetectedRole)
		fmt.Printf("Generated: %s\n\n", report.GeneratedAt.Format("2006-01-02 15:04:05"))
		
		fmt.Printf("=== Summary ===\n")
		fmt.Printf("Total Rules: %d\n", report.Summary.TotalRules)
		fmt.Printf("Passed: %d\n", report.Summary.PassedRules)
		fmt.Printf("Failed: %d\n", report.Summary.FailedRules)
		fmt.Printf("Skipped: %d\n", report.Summary.SkippedRules)
		fmt.Printf("Errors: %d\n", report.Summary.ErrorRules)
		fmt.Printf("Compliance Score: %.1f%%\n\n", report.Summary.ComplianceScore)
		
		if report.Summary.FailedRules > 0 {
			fmt.Printf("=== Failed Rules ===\n")
			for _, result := range report.RuleResults {
				if result.Status == types.StatusFail {
					fmt.Printf("- [%s] %s: %s\n", result.Severity, result.RuleID, result.Message)
				}
			}
		}
		
		return nil
	default:
		return fmt.Errorf("지원되지 않는 형식: %s", format)
	}
	
	if err != nil {
		return err
	}
	
	fmt.Print(string(data))
	return nil
}