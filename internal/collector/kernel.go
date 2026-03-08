package collector

import (
	"context"
	"encoding/json"
	"log/slog"
	"os"
	"os/exec"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// KernelCollector는 커널 관련 정보를 수집합니다.
type KernelCollector struct {
	*BaseCollector
}

// NewKernelCollector는 새 커널 수집기를 생성합니다.
func NewKernelCollector() *KernelCollector {
	return &KernelCollector{
		BaseCollector: NewBaseCollector("kernel", "kernel"),
	}
}

// Collect는 커널 관련 데이터를 수집합니다.
func (k *KernelCollector) Collect(ctx context.Context) (interface{}, error) {
	slog.Debug("커널 데이터 수집 시작")
	
	data := &types.KernelData{
		SysctlParams: make(map[string]string),
	}
	
	// 1. Sysctl 매개변수
	if sysctlParams, err := k.collectSysctlParams(); err != nil {
		slog.Warn("sysctl 매개변수 수집 실패", "error", err)
	} else {
		data.SysctlParams = sysctlParams
	}
	
	// 2. 커널 모듈
	if modules, err := k.collectModules(); err != nil {
		slog.Debug("커널 모듈 수집 실패", "error", err)
	} else {
		data.Modules = modules
	}
	
	// 3. 커널 버전
	if version, err := k.collectVersion(); err != nil {
		slog.Debug("커널 버전 수집 실패", "error", err)
	} else {
		data.Version = version
	}
	
	// 4. 커널 명령행
	if cmdline, err := k.collectCommandLine(); err != nil {
		slog.Debug("커널 명령행 수집 실패", "error", err)
	} else {
		data.CommandLine = cmdline
	}
	
	// 5. 로드된 모듈 목록
	if loadedModules, err := k.collectLoadedModules(); err != nil {
		slog.Debug("로드된 모듈 목록 수집 실패", "error", err)
	} else {
		data.LoadedModules = loadedModules
	}
	
	slog.Debug("커널 데이터 수집 완료")
	return data, nil
}

// IsAvailable은 커널 수집기가 사용 가능한지 확인합니다.
func (k *KernelCollector) IsAvailable() bool {
	_, err := os.Stat("/proc/version")
	return err == nil
}

// collectSysctlParams는 중요한 sysctl 매개변수를 수집합니다.
func (k *KernelCollector) collectSysctlParams() (map[string]string, error) {
	params := make(map[string]string)
	
	// 중요한 커널 매개변수 목록
	importantParams := []string{
		"kernel.shmmax",
		"kernel.shmall",
		"kernel.shmmni",
		"kernel.sem",
		"fs.file-max",
		"fs.aio-max-nr",
		"net.core.somaxconn",
		"net.core.rmem_default",
		"net.core.rmem_max",
		"net.core.wmem_default",
		"net.core.wmem_max",
		"net.ipv4.tcp_rmem",
		"net.ipv4.tcp_wmem",
		"net.ipv4.tcp_fin_timeout",
		"net.ipv4.tcp_keepalive_time",
		"net.ipv4.tcp_max_syn_backlog",
		"vm.swappiness",
		"vm.dirty_ratio",
		"vm.dirty_background_ratio",
		"vm.zone_reclaim_mode",
	}
	
	for _, param := range importantParams {
		cmd := exec.Command("sysctl", "-n", param)
		if output, err := cmd.Output(); err == nil {
			params[param] = strings.TrimSpace(string(output))
		}
	}
	
	return params, nil
}

// collectModules는 커널 모듈 정보를 수집합니다.
func (k *KernelCollector) collectModules() (json.RawMessage, error) {
	data, err := os.ReadFile("/proc/modules")
	if err != nil {
		return nil, err
	}
	
	var modules []map[string]string
	
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		fields := strings.Fields(line)
		if len(fields) >= 6 {
			module := map[string]string{
				"name":        fields[0],
				"size":        fields[1],
				"used_count":  fields[2],
				"used_by":     fields[3],
				"state":       fields[4],
				"address":     fields[5],
			}
			modules = append(modules, module)
		}
	}
	
	return json.Marshal(modules)
}

// collectVersion는 커널 버전을 수집합니다.
func (k *KernelCollector) collectVersion() (string, error) {
	data, err := os.ReadFile("/proc/version")
	if err != nil {
		return "", err
	}
	
	return strings.TrimSpace(string(data)), nil
}

// collectCommandLine는 커널 부트 명령행을 수집합니다.
func (k *KernelCollector) collectCommandLine() (string, error) {
	data, err := os.ReadFile("/proc/cmdline")
	if err != nil {
		return "", err
	}
	
	return strings.TrimSpace(string(data)), nil
}

// collectLoadedModules는 현재 로드된 모듈 목록을 수집합니다.
func (k *KernelCollector) collectLoadedModules() ([]string, error) {
	cmd := exec.Command("lsmod")
	output, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	
	var modules []string
	lines := strings.Split(string(output), "\n")
	
	// 첫 번째 줄(헤더) 스킵
	for _, line := range lines[1:] {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		fields := strings.Fields(line)
		if len(fields) > 0 {
			modules = append(modules, fields[0])
		}
	}
	
	return modules, nil
}