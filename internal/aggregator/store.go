// package aggregator의 데이터 저장소를 제공합니다.
package aggregator

import (
	"encoding/json"
	"fmt"
	"io/fs"
	"log/slog"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// Store는 보고서를 파일 시스템에 저장하고 관리합니다.
type Store struct {
	dataDir string
}

// ReportSummary는 보고서 요약 정보입니다.
type ReportSummary struct {
	ID           string    `json:"id"`
	Hostname     string    `json:"hostname"`
	Role         string    `json:"role"`
	Timestamp    time.Time `json:"timestamp"`
	TotalRules   int       `json:"total_rules"`
	FailedRules  int       `json:"failed_rules"`
	SuccessRate  float64   `json:"success_rate"`
	FilePath     string    `json:"file_path"`
}

// Stats는 저장소 통계 정보입니다.
type Stats struct {
	TotalReports     int                      `json:"total_reports"`
	TotalHosts       int                      `json:"total_hosts"`
	RecentReports    int                      `json:"recent_reports_24h"`
	HostDistribution map[string]int           `json:"host_distribution"`
	RoleDistribution map[string]int           `json:"role_distribution"`
	LastUpdated      time.Time                `json:"last_updated"`
}

// NewStore는 새로운 스토어를 생성합니다.
func NewStore(dataDir string) (*Store, error) {
	// 절대 경로로 변환
	absPath, err := filepath.Abs(dataDir)
	if err != nil {
		return nil, fmt.Errorf("절대 경로 변환 실패: %w", err)
	}

	// 디렉토리가 파일이면 상위 디렉토리를 데이터 디렉토리로 사용
	if strings.HasSuffix(absPath, ".db") {
		absPath = filepath.Dir(absPath)
	}

	// 데이터 디렉토리 생성
	reportsDir := filepath.Join(absPath, "reports")
	if err := os.MkdirAll(reportsDir, 0755); err != nil {
		return nil, fmt.Errorf("디렉토리 생성 실패: %w", err)
	}

	slog.Info("스토어 초기화 완료", "data_dir", absPath)

	return &Store{
		dataDir: absPath,
	}, nil
}

// SaveReport는 보고서를 저장하고 ID를 반환합니다.
func (s *Store) SaveReport(report *types.Report) (string, error) {
	// 보고서 ID 생성 (타임스탬프 기반)
	id := fmt.Sprintf("%s_%s_%d", 
		report.SystemInfo.Hostname,
		strings.ReplaceAll(string(report.SystemInfo.DetectedRole), " ", "_"),
		time.Now().Unix())
	report.ReportID = id

	// 파일 경로 생성
	filename := fmt.Sprintf("%s.json", id)
	filepath := filepath.Join(s.dataDir, "reports", filename)

	// JSON으로 저장
	file, err := os.Create(filepath)
	if err != nil {
		return "", fmt.Errorf("파일 생성 실패: %w", err)
	}
	defer file.Close()

	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(report); err != nil {
		return "", fmt.Errorf("보고서 인코딩 실패: %w", err)
	}

	slog.Debug("보고서 저장 완료", "id", id, "path", filepath)
	return id, nil
}

// GetReport는 특정 ID의 보고서를 반환합니다.
func (s *Store) GetReport(id string) (*types.Report, error) {
	filepath := filepath.Join(s.dataDir, "reports", id+".json")
	
	file, err := os.Open(filepath)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("report not found")
		}
		return nil, fmt.Errorf("파일 열기 실패: %w", err)
	}
	defer file.Close()

	var report types.Report
	if err := json.NewDecoder(file).Decode(&report); err != nil {
		return nil, fmt.Errorf("보고서 디코딩 실패: %w", err)
	}

	return &report, nil
}

// GetReports는 보고서 목록을 반환합니다.
func (s *Store) GetReports(hostname, role string, limit int) ([]*ReportSummary, error) {
	reportsDir := filepath.Join(s.dataDir, "reports")
	
	var summaries []*ReportSummary
	
	err := filepath.WalkDir(reportsDir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		
		if d.IsDir() || !strings.HasSuffix(path, ".json") {
			return nil
		}

		summary, err := s.getReportSummary(path)
		if err != nil {
			slog.Warn("보고서 요약 생성 실패", "path", path, "error", err)
			return nil // 에러 무시하고 계속
		}

		// 필터링
		if hostname != "" && summary.Hostname != hostname {
			return nil
		}
		if role != "" && summary.Role != role {
			return nil
		}

		summaries = append(summaries, summary)
		return nil
	})

	if err != nil {
		return nil, fmt.Errorf("디렉토리 스캔 실패: %w", err)
	}

	// 타임스탬프 기준 내림차순 정렬
	sort.Slice(summaries, func(i, j int) bool {
		return summaries[i].Timestamp.After(summaries[j].Timestamp)
	})

	// 제한 적용
	if limit > 0 && len(summaries) > limit {
		summaries = summaries[:limit]
	}

	return summaries, nil
}

// getReportSummary는 파일에서 보고서 요약을 생성합니다.
func (s *Store) getReportSummary(filepath string) (*ReportSummary, error) {
	file, err := os.Open(filepath)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	var report types.Report
	if err := json.NewDecoder(file).Decode(&report); err != nil {
		return nil, err
	}

	// 실패한 규칙 수 계산
	failedRules := 0
	for _, result := range report.RuleResults {
		if result.Status == types.StatusFail {
			failedRules++
		}
	}

	totalRules := len(report.RuleResults)
	successRate := 0.0
	if totalRules > 0 {
		successRate = float64(totalRules-failedRules) / float64(totalRules) * 100
	}

	return &ReportSummary{
		ID:          report.ReportID,
		Hostname:    report.SystemInfo.Hostname,
		Role:        string(report.SystemInfo.DetectedRole),
		Timestamp:   report.GeneratedAt,
		TotalRules:  totalRules,
		FailedRules: failedRules,
		SuccessRate: successRate,
		FilePath:    filepath,
	}, nil
}

// GetStats는 저장소 통계를 반환합니다.
func (s *Store) GetStats() (*Stats, error) {
	summaries, err := s.GetReports("", "", 0) // 모든 보고서
	if err != nil {
		return nil, err
	}

	stats := &Stats{
		TotalReports:     len(summaries),
		HostDistribution: make(map[string]int),
		RoleDistribution: make(map[string]int),
		LastUpdated:      time.Now(),
	}

	// 호스트 목록
	hosts := make(map[string]bool)
	recentTime := time.Now().Add(-24 * time.Hour)

	for _, summary := range summaries {
		// 호스트 카운트
		hosts[summary.Hostname] = true
		stats.HostDistribution[summary.Hostname]++

		// 역할 카운트
		stats.RoleDistribution[summary.Role]++

		// 최근 24시간 보고서
		if summary.Timestamp.After(recentTime) {
			stats.RecentReports++
		}
	}

	stats.TotalHosts = len(hosts)

	return stats, nil
}

// DeleteReport는 보고서를 삭제합니다.
func (s *Store) DeleteReport(id string) error {
	filepath := filepath.Join(s.dataDir, "reports", id+".json")
	
	if err := os.Remove(filepath); err != nil {
		if os.IsNotExist(err) {
			return fmt.Errorf("report not found")
		}
		return fmt.Errorf("파일 삭제 실패: %w", err)
	}

	slog.Info("보고서 삭제 완료", "id", id)
	return nil
}

// Close는 스토어를 정리합니다.
func (s *Store) Close() error {
	slog.Info("스토어 종료", "data_dir", s.dataDir)
	return nil
}

// Cleanup은 오래된 보고서를 정리합니다.
func (s *Store) Cleanup(retentionDays int) error {
	if retentionDays <= 0 {
		return nil
	}

	cutoffTime := time.Now().AddDate(0, 0, -retentionDays)
	reportsDir := filepath.Join(s.dataDir, "reports")
	
	deleted := 0
	err := filepath.WalkDir(reportsDir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		
		if d.IsDir() || !strings.HasSuffix(path, ".json") {
			return nil
		}

		info, err := d.Info()
		if err != nil {
			return nil
		}

		if info.ModTime().Before(cutoffTime) {
			if err := os.Remove(path); err != nil {
				slog.Warn("파일 삭제 실패", "path", path, "error", err)
			} else {
				deleted++
				slog.Debug("오래된 보고서 삭제", "path", path)
			}
		}

		return nil
	})

	if err != nil {
		return fmt.Errorf("정리 작업 실패: %w", err)
	}

	if deleted > 0 {
		slog.Info("오래된 보고서 정리 완료", 
			"deleted_count", deleted, 
			"retention_days", retentionDays)
	}

	return nil
}