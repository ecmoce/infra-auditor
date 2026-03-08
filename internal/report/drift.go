package report

import (
	"encoding/json"
	"fmt"
	"os"
	"time"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// DriftAnalyzer는 설정 드리프트를 분석합니다.
type DriftAnalyzer struct{}

// NewDriftAnalyzer는 새 드리프트 분석기를 생성합니다.
func NewDriftAnalyzer() *DriftAnalyzer {
	return &DriftAnalyzer{}
}

// Analyze는 두 보고서를 비교하여 드리프트를 분석합니다.
func (da *DriftAnalyzer) Analyze(previousReport, currentReport *types.AuditReport) (*types.DriftReport, error) {
	reportID := fmt.Sprintf("drift-%d", time.Now().Unix())
	
	// 이전 보고서 결과를 맵으로 변환
	prevResults := make(map[string]types.RuleResult)
	for _, result := range previousReport.RuleResults {
		prevResults[result.RuleID] = result
	}
	
	var changes []types.DriftChange
	var newIssues, resolvedIssues, statusChanges, valueChanges int
	
	// 현재 보고서의 각 결과와 이전 결과 비교
	for _, currentResult := range currentReport.RuleResults {
		if prevResult, exists := prevResults[currentResult.RuleID]; exists {
			// 기존 규칙의 변경사항 확인
			if change := da.compareResults(prevResult, currentResult); change != nil {
				changes = append(changes, *change)
				
				switch change.ChangeType {
				case "status_change":
					statusChanges++
					if currentResult.Status == types.StatusFail && prevResult.Status != types.StatusFail {
						newIssues++
					} else if currentResult.Status != types.StatusFail && prevResult.Status == types.StatusFail {
						resolvedIssues++
					}
				case "value_change":
					valueChanges++
				}
			}
		} else {
			// 새로운 규칙
			if currentResult.Status == types.StatusFail {
				change := types.DriftChange{
					RuleID:         currentResult.RuleID,
					ChangeType:     "new_rule",
					CurrentStatus:  currentResult.Status,
					CurrentValue:   currentResult.CurrentValue,
					Impact:         currentResult.Severity,
					Description:    "새로운 규칙이 추가되고 실패했습니다",
				}
				changes = append(changes, change)
				newIssues++
			}
		}
	}
	
	// 제거된 규칙 확인
	currentResults := make(map[string]bool)
	for _, result := range currentReport.RuleResults {
		currentResults[result.RuleID] = true
	}
	
	for _, prevResult := range previousReport.RuleResults {
		if !currentResults[prevResult.RuleID] {
			change := types.DriftChange{
				RuleID:        prevResult.RuleID,
				ChangeType:    "removed_rule",
				PreviousStatus: prevResult.Status,
				PreviousValue: prevResult.CurrentValue,
				Impact:        types.SeverityLow,
				Description:   "규칙이 제거되었습니다",
			}
			changes = append(changes, change)
		}
	}
	
	// 드리프트 점수 계산 (0-100, 높을수록 안정)
	driftScore := 100.0
	if len(changes) > 0 {
		// 변경사항이 많을수록 점수 감소
		driftScore = 100.0 - float64(len(changes)*5)
		if driftScore < 0 {
			driftScore = 0
		}
	}
	
	// 영향도별 카운트
	impactCount := make(map[types.Severity]int)
	for _, change := range changes {
		impactCount[change.Impact]++
	}
	
	summary := types.DriftSummary{
		TotalChanges:   len(changes),
		StatusChanges:  statusChanges,
		ValueChanges:   valueChanges,
		NewIssues:      newIssues,
		ResolvedIssues: resolvedIssues,
		ImpactCount:    impactCount,
		DriftScore:     driftScore,
	}
	
	driftReport := &types.DriftReport{
		ReportID:       reportID,
		PreviousReport: previousReport.ReportID,
		CurrentReport:  currentReport.ReportID,
		Changes:        changes,
		Summary:        summary,
		GeneratedAt:    time.Now(),
	}
	
	return driftReport, nil
}

// compareResults는 두 결과를 비교하여 변경사항을 찾습니다.
func (da *DriftAnalyzer) compareResults(prev, current types.RuleResult) *types.DriftChange {
	// 상태 변경 확인
	if prev.Status != current.Status {
		var impact types.Severity
		if current.Status == types.StatusFail {
			impact = current.Severity
		} else {
			impact = types.SeverityLow
		}
		
		return &types.DriftChange{
			RuleID:         current.RuleID,
			ChangeType:     "status_change",
			PreviousStatus: prev.Status,
			CurrentStatus:  current.Status,
			PreviousValue:  prev.CurrentValue,
			CurrentValue:   current.CurrentValue,
			Impact:         impact,
			Description:    fmt.Sprintf("상태가 %s에서 %s로 변경되었습니다", prev.Status, current.Status),
		}
	}
	
	// 값 변경 확인 (상태는 같지만 값이 다른 경우)
	if !da.valuesEqual(prev.CurrentValue, current.CurrentValue) {
		return &types.DriftChange{
			RuleID:         current.RuleID,
			ChangeType:     "value_change",
			PreviousStatus: prev.Status,
			CurrentStatus:  current.Status,
			PreviousValue:  prev.CurrentValue,
			CurrentValue:   current.CurrentValue,
			Impact:         types.SeverityLow,
			Description:    "설정 값이 변경되었습니다",
		}
	}
	
	return nil
}

// valuesEqual은 두 값이 같은지 비교합니다.
func (da *DriftAnalyzer) valuesEqual(a, b interface{}) bool {
	// 간단한 비교 구현 (실제로는 더 정교한 비교 필요)
	aBytes, err1 := json.Marshal(a)
	bBytes, err2 := json.Marshal(b)
	
	if err1 != nil || err2 != nil {
		return false
	}
	
	return string(aBytes) == string(bBytes)
}

// WriteDriftToFile은 드리프트 보고서를 파일에 저장합니다.
func WriteDriftToFile(report *types.DriftReport, filePath, format string) error {
	var data []byte
	var err error
	
	switch format {
	case "json":
		data, err = json.MarshalIndent(report, "", "  ")
	case "yaml":
		data, err = json.MarshalIndent(report, "", "  ")
	default:
		return fmt.Errorf("지원되지 않는 형식: %s", format)
	}
	
	if err != nil {
		return err
	}
	
	return os.WriteFile(filePath, data, 0644)
}

// WriteDriftToStdout은 드리프트 보고서를 표준 출력에 출력합니다.
func WriteDriftToStdout(report *types.DriftReport, format string) error {
	switch format {
	case "json":
		data, err := json.MarshalIndent(report, "", "  ")
		if err != nil {
			return err
		}
		fmt.Print(string(data))
		
	case "yaml":
		data, err := json.MarshalIndent(report, "", "  ")
		if err != nil {
			return err
		}
		fmt.Print(string(data))
		
	case "table":
		fmt.Printf("=== Configuration Drift Report ===\n")
		fmt.Printf("Report ID: %s\n", report.ReportID)
		fmt.Printf("Previous: %s\n", report.PreviousReport)
		fmt.Printf("Current: %s\n", report.CurrentReport)
		fmt.Printf("Generated: %s\n\n", report.GeneratedAt.Format("2006-01-02 15:04:05"))
		
		fmt.Printf("=== Summary ===\n")
		fmt.Printf("Total Changes: %d\n", report.Summary.TotalChanges)
		fmt.Printf("Status Changes: %d\n", report.Summary.StatusChanges)
		fmt.Printf("Value Changes: %d\n", report.Summary.ValueChanges)
		fmt.Printf("New Issues: %d\n", report.Summary.NewIssues)
		fmt.Printf("Resolved Issues: %d\n", report.Summary.ResolvedIssues)
		fmt.Printf("Drift Score: %.1f/100\n\n", report.Summary.DriftScore)
		
		if len(report.Changes) > 0 {
			fmt.Printf("=== Changes ===\n")
			for _, change := range report.Changes {
				fmt.Printf("- [%s] %s (%s): %s\n", 
					change.Impact, 
					change.RuleID, 
					change.ChangeType, 
					change.Description)
			}
		}
		
	default:
		return fmt.Errorf("지원되지 않는 형식: %s", format)
	}
	
	return nil
}