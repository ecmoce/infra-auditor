package collector

import (
	"context"
	"encoding/json"
	"log/slog"
	"os/exec"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// SystemDCollector는 SystemD 관련 정보를 수집합니다.
type SystemDCollector struct {
	*BaseCollector
}

// NewSystemDCollector는 새 SystemD 수집기를 생성합니다.
func NewSystemDCollector() *SystemDCollector {
	return &SystemDCollector{
		BaseCollector: NewBaseCollector("systemd", "systemd"),
	}
}

// Collect는 SystemD 관련 데이터를 수집합니다.
func (s *SystemDCollector) Collect(ctx context.Context) (interface{}, error) {
	slog.Debug("SystemD 데이터 수집 시작")
	
	data := &types.SystemDData{}
	
	// 유닛 목록
	if units, err := s.collectUnits(); err != nil {
		slog.Debug("유닛 정보 수집 실패", "error", err)
	} else {
		data.Units = units
	}
	
	// 실패한 유닛들
	if failedUnits, err := s.collectFailedUnits(); err != nil {
		slog.Debug("실패한 유닛 수집 실패", "error", err)
	} else {
		data.FailedUnits = failedUnits
	}
	
	// 시스템 상태
	if systemState, err := s.collectSystemState(); err != nil {
		slog.Debug("시스템 상태 수집 실패", "error", err)
	} else {
		data.SystemState = systemState
	}
	
	slog.Debug("SystemD 데이터 수집 완료")
	return data, nil
}

// IsAvailable은 SystemD 수집기가 사용 가능한지 확인합니다.
func (s *SystemDCollector) IsAvailable() bool {
	_, err := exec.LookPath("systemctl")
	return err == nil
}

// collectUnits는 SystemD 유닛 정보를 수집합니다.
func (s *SystemDCollector) collectUnits() (json.RawMessage, error) {
	cmd := exec.Command("systemctl", "list-units", "--all", "--no-pager", "--output=json")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	
	return json.RawMessage(output), nil
}

// collectFailedUnits는 실패한 유닛들을 수집합니다.
func (s *SystemDCollector) collectFailedUnits() ([]string, error) {
	cmd := exec.Command("systemctl", "list-units", "--failed", "--no-pager", "--no-legend")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	
	var failedUnits []string
	lines := strings.Split(string(output), "\n")
	
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		fields := strings.Fields(line)
		if len(fields) > 0 {
			failedUnits = append(failedUnits, fields[0])
		}
	}
	
	return failedUnits, nil
}

// collectSystemState는 시스템 상태를 수집합니다.
func (s *SystemDCollector) collectSystemState() (string, error) {
	cmd := exec.Command("systemctl", "is-system-running")
	output, err := cmd.Output()
	if err != nil {
		// systemctl is-system-running은 degraded 상태에서도 exit code 1을 반환할 수 있음
		return strings.TrimSpace(string(output)), nil
	}
	
	return strings.TrimSpace(string(output)), nil
}