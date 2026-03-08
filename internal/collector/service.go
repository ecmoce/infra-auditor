package collector

import (
	"context"
	"log/slog"
	"os/exec"
	"strconv"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// ServiceCollector는 서비스 관련 정보를 수집합니다.
type ServiceCollector struct {
	*BaseCollector
}

// NewServiceCollector는 새 서비스 수집기를 생성합니다.
func NewServiceCollector() *ServiceCollector {
	return &ServiceCollector{
		BaseCollector: NewBaseCollector("service", "service"),
	}
}

// Collect는 서비스 관련 데이터를 수집합니다.
func (s *ServiceCollector) Collect(ctx context.Context) (interface{}, error) {
	slog.Debug("서비스 데이터 수집 시작")
	
	data := &types.ServiceData{}
	
	// 실행 중인 서비스
	if runningServices, err := s.collectRunningServices(); err != nil {
		slog.Debug("실행 중인 서비스 수집 실패", "error", err)
	} else {
		data.RunningServices = runningServices
	}
	
	// 리스닝 포트
	if listeningPorts, err := s.collectListeningPorts(); err != nil {
		slog.Debug("리스닝 포트 수집 실패", "error", err)
	} else {
		data.ListeningPorts = listeningPorts
	}
	
	// 프로세스 개수
	if processCount, err := s.collectProcessCount(); err != nil {
		slog.Debug("프로세스 개수 수집 실패", "error", err)
	} else {
		data.ProcessCount = processCount
	}
	
	slog.Debug("서비스 데이터 수집 완료")
	return data, nil
}

// IsAvailable은 서비스 수집기가 사용 가능한지 확인합니다.
func (s *ServiceCollector) IsAvailable() bool {
	_, err := exec.LookPath("systemctl")
	return err == nil
}

// collectRunningServices는 실행 중인 서비스를 수집합니다.
func (s *ServiceCollector) collectRunningServices() ([]types.ServiceInfo, error) {
	cmd := exec.Command("systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--no-legend", "--plain")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	
	var services []types.ServiceInfo
	lines := strings.Split(string(output), "\n")
	
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		fields := strings.Fields(line)
		if len(fields) >= 4 {
			serviceName := fields[0]
			status := fields[2]
			
			service := types.ServiceInfo{
				Name:   serviceName,
				Status: status,
			}
			
			services = append(services, service)
		}
	}
	
	return services, nil
}

// collectListeningPorts는 리스닝 포트를 수집합니다.
func (s *ServiceCollector) collectListeningPorts() ([]types.PortInfo, error) {
	cmd := exec.Command("ss", "-tlnp")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	
	var ports []types.PortInfo
	lines := strings.Split(string(output), "\n")
	
	for _, line := range lines {
		if !strings.Contains(line, "LISTEN") {
			continue
		}
		
		fields := strings.Fields(line)
		if len(fields) < 4 {
			continue
		}
		
		address := fields[3]
		if colonIdx := strings.LastIndex(address, ":"); colonIdx != -1 {
			portStr := address[colonIdx+1:]
			if port, err := strconv.Atoi(portStr); err == nil {
				portInfo := types.PortInfo{
					Port:     port,
					Protocol: strings.ToLower(fields[0]),
					State:    "LISTEN",
					Address:  address,
				}
				
				// 프로세스 정보 파싱
				if len(fields) >= 6 {
					processInfo := fields[5]
					if strings.Contains(processInfo, ",") {
						parts := strings.Split(processInfo, ",")
						if len(parts) >= 2 {
							if pid, err := strconv.Atoi(parts[1]); err == nil {
								portInfo.PID = pid
							}
							portInfo.ProcessName = parts[0]
						}
					}
				}
				
				ports = append(ports, portInfo)
			}
		}
	}
	
	return ports, nil
}

// collectProcessCount는 실행 중인 프로세스 개수를 수집합니다.
func (s *ServiceCollector) collectProcessCount() (int, error) {
	cmd := exec.Command("ps", "aux")
	output, err := cmd.Output()
	if err != nil {
		return 0, err
	}
	
	lines := strings.Split(string(output), "\n")
	// 헤더 제외하고 카운트
	count := len(lines) - 2 // 헤더와 마지막 빈 줄 제외
	if count < 0 {
		count = 0
	}
	
	return count, nil
}