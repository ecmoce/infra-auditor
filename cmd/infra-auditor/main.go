// infra-auditor는 리눅스 인프라 튜닝 상태를 자동으로 점검하는 도구입니다.
package main

import (
	"fmt"
	"log/slog"
	"os"
	"runtime"

	"github.com/ecmoce/infra-auditor/internal/aggregator"
	"github.com/ecmoce/infra-auditor/internal/detector"
	"github.com/ecmoce/infra-auditor/internal/report"
	"github.com/ecmoce/infra-auditor/internal/rules"
	"github.com/ecmoce/infra-auditor/pkg/types"
	"github.com/spf13/cobra"
)

const (
	version = "2.0.0-go"
	schema  = "1.0.0"
)

var (
	verbose bool
	quiet   bool
)

func main() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}

var rootCmd = &cobra.Command{
	Use:     "infra-auditor",
	Short:   "리눅스 인프라 튜닝 상태 자동 점검 도구",
	Long: `infra-auditor는 리눅스 서버의 성능 튜닝 상태를 자동으로 점검하고 
개선 권장사항을 제공하는 도구입니다.

CPU, 메모리, 네트워크, 스토리지, 커널 파라미터 등 92개 이상의 
규칙을 통해 종합적인 시스템 분석을 수행합니다.`,
	Version: version,
	PersistentPreRun: func(cmd *cobra.Command, args []string) {
		setupLogging()
		
		// 리눅스가 아닌 환경에서 경고
		if runtime.GOOS != "linux" {
			slog.Warn("이 도구는 리눅스 환경에서 설계되었습니다", 
				"current_os", runtime.GOOS)
		}
	},
}

var scanCmd = &cobra.Command{
	Use:   "scan",
	Short: "시스템 점검 실행",
	Long: `시스템을 점검하고 결과 보고서를 생성합니다.
	
서버 역할을 자동 감지하거나 --role 플래그로 명시적으로 지정할 수 있습니다.`,
	Example: `  # 자동 역할 감지로 점검
  infra-auditor scan

  # 특정 역할로 점검
  infra-auditor scan --role compute

  # JSON 보고서 저장
  infra-auditor scan --output report.json

  # 특정 카테고리만 점검
  infra-auditor scan --categories cpu,memory

  # 심각도별 필터링
  infra-auditor scan --severity critical,high`,
	RunE: runScan,
}

var serveCmd = &cobra.Command{
	Use:   "serve",
	Short: "Aggregator 서버 실행",
	Long: `여러 에이전트로부터 보고서를 수집하고 관리하는 
중앙 집중식 서버를 실행합니다.

웹 대시보드, REST API, 드리프트 분석 등의 기능을 제공합니다.`,
	Example: `  # 기본 포트(8080)로 서버 실행
  infra-auditor serve

  # 커스텀 포트로 실행
  infra-auditor serve --port 9090

  # 데이터베이스 설정
  infra-auditor serve --db-path ./reports.db`,
	RunE: runServe,
}

var driftCmd = &cobra.Command{
	Use:   "drift",
	Short: "설정 드리프트 분석",
	Long: `이전 보고서와 현재 보고서를 비교하여 
설정 변경사항을 분석합니다.`,
	Example: `  # 두 보고서 비교
  infra-auditor drift --previous report1.json --current report2.json

  # 드리프트 보고서 저장
  infra-auditor drift --previous old.json --current new.json --output drift.json`,
	RunE: runDrift,
}

var remediateCmd = &cobra.Command{
	Use:   "remediate",
	Short: "자동 수정 스크립트 생성",
	Long: `점검 결과를 기반으로 자동 수정 스크립트를 생성합니다.
스크립트는 백업, 검증, 롤백 기능을 포함합니다.`,
	Example: `  # 모든 이슈에 대한 수정 스크립트 생성
  infra-auditor remediate --input report.json

  # 중요도별 필터링
  infra-auditor remediate --input report.json --severity critical

  # 스크립트 파일 저장
  infra-auditor remediate --input report.json --output fix.sh`,
	RunE: runRemediate,
}

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "버전 정보 출력",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Printf("infra-auditor %s\n", version)
		fmt.Printf("Schema: %s\n", schema)
		fmt.Printf("Go: %s\n", runtime.Version())
		fmt.Printf("OS/Arch: %s/%s\n", runtime.GOOS, runtime.GOARCH)
	},
}

func init() {
	// Global flags
	rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "v", false, 
		"상세 로그 출력")
	rootCmd.PersistentFlags().BoolVarP(&quiet, "quiet", "q", false, 
		"오류만 출력")

	// Scan command flags
	scanCmd.Flags().StringP("role", "r", "auto", 
		"서버 역할 (auto, compute, controller, network, storage, database, web)")
	scanCmd.Flags().StringP("output", "o", "", 
		"출력 파일 경로 (기본값: 표준출력)")
	scanCmd.Flags().StringSliceP("categories", "c", nil, 
		"점검할 카테고리 목록 (cpu,memory,network,storage,kernel,service)")
	scanCmd.Flags().StringSliceP("severity", "s", nil,
		"포함할 심각도 (critical,high,medium,low,info)")
	scanCmd.Flags().StringSliceP("rules", "", nil,
		"특정 규칙만 실행 (규칙 ID 목록)")
	scanCmd.Flags().StringSliceP("exclude-rules", "", nil,
		"제외할 규칙 목록 (규칙 ID 목록)")
	scanCmd.Flags().Bool("include-passed", false,
		"통과한 규칙도 보고서에 포함")
	scanCmd.Flags().Bool("collect-only", false,
		"데이터 수집만 수행 (규칙 실행 안함)")
	scanCmd.Flags().StringP("format", "f", "json",
		"출력 형식 (json, yaml, table)")

	// Serve command flags
	serveCmd.Flags().IntP("port", "p", 8080, 
		"서버 포트")
	serveCmd.Flags().StringP("host", "H", "0.0.0.0", 
		"서버 바인드 주소")
	serveCmd.Flags().StringP("db-path", "", "./infra-auditor.db", 
		"데이터베이스 파일 경로")
	serveCmd.Flags().StringP("config", "", "", 
		"설정 파일 경로")
	serveCmd.Flags().Bool("enable-ui", true,
		"웹 UI 활성화")

	// Drift command flags
	driftCmd.Flags().StringP("previous", "", "", 
		"이전 보고서 파일 경로 (필수)")
	driftCmd.Flags().StringP("current", "", "", 
		"현재 보고서 파일 경로 (필수)")
	driftCmd.Flags().StringP("output", "o", "", 
		"출력 파일 경로 (기본값: 표준출력)")
	driftCmd.Flags().StringP("format", "f", "json",
		"출력 형식 (json, yaml, table)")
	driftCmd.MarkFlagRequired("previous")
	driftCmd.MarkFlagRequired("current")

	// Remediate command flags
	remediateCmd.Flags().StringP("input", "i", "", 
		"입력 보고서 파일 경로 (필수)")
	remediateCmd.Flags().StringP("output", "o", "", 
		"출력 스크립트 파일 경로 (기본값: 표준출력)")
	remediateCmd.Flags().StringSliceP("severity", "s", nil,
		"수정할 심각도 (critical,high,medium,low)")
	remediateCmd.Flags().StringSliceP("categories", "c", nil,
		"수정할 카테고리")
	remediateCmd.Flags().StringSliceP("rules", "", nil,
		"수정할 규칙 ID 목록")
	remediateCmd.Flags().Bool("dry-run", false,
		"실제 실행 없이 스크립트만 생성")
	remediateCmd.Flags().Bool("no-backup", false,
		"백업 생략")
	remediateCmd.MarkFlagRequired("input")

	// Add subcommands
	rootCmd.AddCommand(scanCmd)
	rootCmd.AddCommand(serveCmd)
	rootCmd.AddCommand(driftCmd)
	rootCmd.AddCommand(remediateCmd)
	rootCmd.AddCommand(versionCmd)
}

func setupLogging() {
	var level slog.Level
	
	switch {
	case quiet:
		level = slog.LevelError
	case verbose:
		level = slog.LevelDebug
	default:
		level = slog.LevelInfo
	}

	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{
		Level: level,
	}))
	slog.SetDefault(logger)
}

func runScan(cmd *cobra.Command, args []string) error {
	slog.Info("시스템 점검 시작")
	
	// 플래그 파싱
	roleStr, _ := cmd.Flags().GetString("role")
	outputPath, _ := cmd.Flags().GetString("output")
	categories, _ := cmd.Flags().GetStringSlice("categories")
	severities, _ := cmd.Flags().GetStringSlice("severity")
	ruleIDs, _ := cmd.Flags().GetStringSlice("rules")
	excludeRules, _ := cmd.Flags().GetStringSlice("exclude-rules")
	includePassed, _ := cmd.Flags().GetBool("include-passed")
	collectOnly, _ := cmd.Flags().GetBool("collect-only")
	format, _ := cmd.Flags().GetString("format")

	// 역할 결정
	var targetRole types.Role
	if roleStr == "auto" {
		detectedRole, err := detector.DetectRole()
		if err != nil {
			slog.Warn("역할 자동 감지 실패, compute로 설정", "error", err)
			targetRole = types.RoleCompute
		} else {
			targetRole = detectedRole
			slog.Info("서버 역할 감지됨", "role", targetRole)
		}
	} else {
		targetRole = types.Role(roleStr)
	}

	// 보고서 생성
	reportGenerator := report.NewGenerator(version, schema)
	auditReport, err := reportGenerator.Generate(report.Options{
		TargetRole:      targetRole,
		Categories:      categories,
		Severities:      severities,
		RuleIDs:         ruleIDs,
		ExcludeRules:    excludeRules,
		IncludePassed:   includePassed,
		CollectOnly:     collectOnly,
	})
	if err != nil {
		return fmt.Errorf("보고서 생성 실패: %w", err)
	}

	slog.Info("점검 완료", 
		"total_rules", auditReport.Summary.TotalRules,
		"failed_rules", auditReport.Summary.FailedRules,
		"compliance_score", auditReport.Summary.ComplianceScore)

	// 출력
	if outputPath != "" {
		return report.WriteToFile(auditReport, outputPath, format)
	} else {
		return report.WriteToStdout(auditReport, format)
	}
}

func runServe(cmd *cobra.Command, args []string) error {
	port, _ := cmd.Flags().GetInt("port")
	host, _ := cmd.Flags().GetString("host")
	dbPath, _ := cmd.Flags().GetString("db-path")
	configPath, _ := cmd.Flags().GetString("config")
	enableUI, _ := cmd.Flags().GetBool("enable-ui")

	slog.Info("Aggregator 서버 시작", 
		"host", host, 
		"port", port,
		"database", dbPath,
		"ui_enabled", enableUI)

	server, err := aggregator.NewServer(aggregator.Config{
		Host:     host,
		Port:     port,
		DBPath:   dbPath,
		Config:   configPath,
		EnableUI: enableUI,
	})
	if err != nil {
		return fmt.Errorf("서버 초기화 실패: %w", err)
	}

	return server.Start()
}

func runDrift(cmd *cobra.Command, args []string) error {
	previousPath, _ := cmd.Flags().GetString("previous")
	currentPath, _ := cmd.Flags().GetString("current")
	outputPath, _ := cmd.Flags().GetString("output")
	format, _ := cmd.Flags().GetString("format")

	slog.Info("드리프트 분석 시작", 
		"previous", previousPath, 
		"current", currentPath)

	// 보고서 로드
	previousReport, err := report.LoadFromFile(previousPath)
	if err != nil {
		return fmt.Errorf("이전 보고서 로드 실패: %w", err)
	}

	currentReport, err := report.LoadFromFile(currentPath)
	if err != nil {
		return fmt.Errorf("현재 보고서 로드 실패: %w", err)
	}

	// 드리프트 분석
	driftAnalyzer := report.NewDriftAnalyzer()
	driftReport, err := driftAnalyzer.Analyze(previousReport, currentReport)
	if err != nil {
		return fmt.Errorf("드리프트 분석 실패: %w", err)
	}

	slog.Info("드리프트 분석 완료", 
		"total_changes", driftReport.Summary.TotalChanges,
		"new_issues", driftReport.Summary.NewIssues,
		"resolved_issues", driftReport.Summary.ResolvedIssues,
		"drift_score", driftReport.Summary.DriftScore)

	// 출력
	if outputPath != "" {
		return report.WriteDriftToFile(driftReport, outputPath, format)
	} else {
		return report.WriteDriftToStdout(driftReport, format)
	}
}

func runRemediate(cmd *cobra.Command, args []string) error {
	inputPath, _ := cmd.Flags().GetString("input")
	outputPath, _ := cmd.Flags().GetString("output")
	severities, _ := cmd.Flags().GetStringSlice("severity")
	categories, _ := cmd.Flags().GetStringSlice("categories")
	ruleIDs, _ := cmd.Flags().GetStringSlice("rules")
	dryRun, _ := cmd.Flags().GetBool("dry-run")
	noBackup, _ := cmd.Flags().GetBool("no-backup")

	slog.Info("자동 수정 스크립트 생성 시작", "input", inputPath)

	// 보고서 로드
	auditReport, err := report.LoadFromFile(inputPath)
	if err != nil {
		return fmt.Errorf("보고서 로드 실패: %w", err)
	}

	// 수정 스크립트 생성
	remediator := rules.NewRemediator()
	script, err := remediator.GenerateScript(auditReport, rules.RemediateOptions{
		Severities:  severities,
		Categories:  categories,
		RuleIDs:     ruleIDs,
		DryRun:      dryRun,
		NoBackup:    noBackup,
	})
	if err != nil {
		return fmt.Errorf("수정 스크립트 생성 실패: %w", err)
	}

	slog.Info("수정 스크립트 생성 완료", 
		"target_rules_count", len(script.TargetRules),
		"commands_count", len(script.Commands),
		"requires_reboot", script.RequiresReboot)

	// 출력
	if outputPath != "" {
		return rules.WriteScriptToFile(script, outputPath)
	} else {
		return rules.WriteScriptToStdout(script)
	}
}