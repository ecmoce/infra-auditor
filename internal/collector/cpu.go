package collector

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// CPUCollector는 CPU 관련 정보를 수집합니다.
type CPUCollector struct {
	*BaseCollector
}

// NewCPUCollector는 새 CPU 수집기를 생성합니다.
func NewCPUCollector() *CPUCollector {
	return &CPUCollector{
		BaseCollector: NewBaseCollector("cpu", "cpu"),
	}
}

// Collect는 CPU 관련 데이터를 수집합니다.
func (c *CPUCollector) Collect(ctx context.Context) (interface{}, error) {
	slog.Debug("CPU 데이터 수집 시작")
	
	data := &types.CPUData{}
	
	// 1. /proc/cpuinfo 수집
	if cpuInfo, err := c.collectCPUInfo(); err != nil {
		slog.Warn("cpuinfo 수집 실패", "error", err)
	} else {
		data.CPUInfo = cpuInfo
	}
	
	// 2. CPU 거버너 정보
	if governor, err := c.collectGovernor(); err != nil {
		slog.Debug("governor 수집 실패", "error", err)
	} else {
		data.Governor = governor
	}
	
	// 3. CPU 스케일링 드라이버
	if scalingDriver, err := c.collectScalingDriver(); err != nil {
		slog.Debug("scaling driver 수집 실패", "error", err)
	} else {
		data.ScalingDriver = scalingDriver
	}
	
	// 4. CPU 주파수 정보
	if minFreq, maxFreq, currentFreq, err := c.collectFrequencies(); err != nil {
		slog.Debug("주파수 정보 수집 실패", "error", err)
	} else {
		data.MinFreq = minFreq
		data.MaxFreq = maxFreq
		data.CurrentFreq = currentFreq
	}
	
	// 5. CPU 친화도 정보
	if affinity, err := c.collectAffinity(); err != nil {
		slog.Debug("affinity 정보 수집 실패", "error", err)
	} else {
		data.Affinity = affinity
	}
	
	// 6. 로드 애버리지
	if loadAvg, err := c.collectLoadAverage(); err != nil {
		slog.Debug("load average 수집 실패", "error", err)
	} else {
		data.LoadAverage = loadAvg
	}
	
	// 7. CPU 사용률
	if usage, err := c.collectUsage(); err != nil {
		slog.Debug("CPU 사용률 수집 실패", "error", err)
	} else {
		data.Usage = usage
	}
	
	// 8. 열 상태
	if thermalState, err := c.collectThermalState(); err != nil {
		slog.Debug("thermal state 수집 실패", "error", err)
	} else {
		data.ThermalState = thermalState
	}
	
	// 9. 전력 관리 정보
	if powerMgmt, err := c.collectPowerManagement(); err != nil {
		slog.Debug("power management 수집 실패", "error", err)
	} else {
		data.PowerManagement = powerMgmt
	}
	
	slog.Debug("CPU 데이터 수집 완료")
	return data, nil
}

// IsAvailable은 CPU 수집기가 사용 가능한지 확인합니다.
func (c *CPUCollector) IsAvailable() bool {
	_, err := os.Stat("/proc/cpuinfo")
	return err == nil
}

// collectCPUInfo는 /proc/cpuinfo 내용을 수집합니다.
func (c *CPUCollector) collectCPUInfo() (json.RawMessage, error) {
	data, err := os.ReadFile("/proc/cpuinfo")
	if err != nil {
		return nil, err
	}
	
	// CPU 정보를 파싱하여 구조화된 데이터로 변환
	cpuInfo := make(map[string]interface{})
	processors := []map[string]string{}
	currentProcessor := make(map[string]string)
	
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			if len(currentProcessor) > 0 {
				processors = append(processors, currentProcessor)
				currentProcessor = make(map[string]string)
			}
			continue
		}
		
		parts := strings.SplitN(line, ":", 2)
		if len(parts) == 2 {
			key := strings.TrimSpace(parts[0])
			value := strings.TrimSpace(parts[1])
			currentProcessor[key] = value
		}
	}
	
	// 마지막 프로세서 추가
	if len(currentProcessor) > 0 {
		processors = append(processors, currentProcessor)
	}
	
	cpuInfo["processors"] = processors
	cpuInfo["count"] = len(processors)
	
	return json.Marshal(cpuInfo)
}

// collectGovernor는 CPU 거버너 정보를 수집합니다.
func (c *CPUCollector) collectGovernor() (string, error) {
	governorPath := "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
	data, err := os.ReadFile(governorPath)
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(data)), nil
}

// collectScalingDriver는 CPU 스케일링 드라이버 정보를 수집합니다.
func (c *CPUCollector) collectScalingDriver() (string, error) {
	driverPath := "/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver"
	data, err := os.ReadFile(driverPath)
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(data)), nil
}

// collectFrequencies는 CPU 주파수 정보를 수집합니다.
func (c *CPUCollector) collectFrequencies() (int64, int64, int64, error) {
	var minFreq, maxFreq, currentFreq int64
	
	// 최소 주파수
	if data, err := os.ReadFile("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq"); err == nil {
		if freq, err := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64); err == nil {
			minFreq = freq
		}
	}
	
	// 최대 주파수
	if data, err := os.ReadFile("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"); err == nil {
		if freq, err := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64); err == nil {
			maxFreq = freq
		}
	}
	
	// 현재 주파수
	if data, err := os.ReadFile("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"); err == nil {
		if freq, err := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64); err == nil {
			currentFreq = freq
		}
	}
	
	return minFreq, maxFreq, currentFreq, nil
}

// collectAffinity는 프로세스별 CPU 친화도 정보를 수집합니다.
func (c *CPUCollector) collectAffinity() (map[string]string, error) {
	affinity := make(map[string]string)
	
	// 주요 시스템 프로세스의 CPU 친화도 확인
	processes := []string{"kthreadd", "migration", "rcu_", "ksoftirqd"}
	
	for _, processPattern := range processes {
		cmd := exec.Command("pgrep", "-f", processPattern)
		output, err := cmd.Output()
		if err != nil {
			continue
		}
		
		pids := strings.Fields(strings.TrimSpace(string(output)))
		for _, pidStr := range pids {
			if pid, err := strconv.Atoi(pidStr); err == nil {
				if affinityMask, err := c.getProcessAffinity(pid); err == nil {
					affinity[fmt.Sprintf("%s_%d", processPattern, pid)] = affinityMask
				}
			}
		}
	}
	
	return affinity, nil
}

// getProcessAffinity는 특정 프로세스의 CPU 친화도를 가져옵니다.
func (c *CPUCollector) getProcessAffinity(pid int) (string, error) {
	cmd := exec.Command("taskset", "-p", strconv.Itoa(pid))
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	
	// 출력 파싱: "pid 1234's current affinity mask: f"
	lines := strings.Split(string(output), "\n")
	for _, line := range lines {
		if strings.Contains(line, "affinity mask:") {
			parts := strings.Split(line, ":")
			if len(parts) > 1 {
				return strings.TrimSpace(parts[1]), nil
			}
		}
	}
	
	return "", fmt.Errorf("affinity mask not found")
}

// collectLoadAverage는 시스템 로드 애버리지를 수집합니다.
func (c *CPUCollector) collectLoadAverage() ([3]float64, error) {
	var loadAvg [3]float64
	
	data, err := os.ReadFile("/proc/loadavg")
	if err != nil {
		return loadAvg, err
	}
	
	fields := strings.Fields(string(data))
	if len(fields) < 3 {
		return loadAvg, fmt.Errorf("invalid loadavg format")
	}
	
	for i := 0; i < 3; i++ {
		if load, err := strconv.ParseFloat(fields[i], 64); err == nil {
			loadAvg[i] = load
		}
	}
	
	return loadAvg, nil
}

// collectUsage는 CPU 사용률을 수집합니다.
func (c *CPUCollector) collectUsage() (map[string]float64, error) {
	usage := make(map[string]float64)
	
	data, err := os.ReadFile("/proc/stat")
	if err != nil {
		return nil, err
	}
	
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		if strings.HasPrefix(line, "cpu") {
			fields := strings.Fields(line)
			if len(fields) < 8 {
				continue
			}
			
			cpuName := fields[0]
			var total, idle int64
			
			for i := 1; i < len(fields); i++ {
				if val, err := strconv.ParseInt(fields[i], 10, 64); err == nil {
					total += val
					if i == 4 { // idle time is the 4th field (0-indexed)
						idle = val
					}
				}
			}
			
			if total > 0 {
				usagePercent := float64(total-idle) / float64(total) * 100
				usage[cpuName] = usagePercent
			}
		}
	}
	
	return usage, nil
}

// collectThermalState는 CPU 열 상태를 수집합니다.
func (c *CPUCollector) collectThermalState() (string, error) {
	// 열 상태 확인 (thermal zone이 있는 경우)
	thermalZones, err := filepath.Glob("/sys/class/thermal/thermal_zone*/temp")
	if err != nil || len(thermalZones) == 0 {
		return "unknown", nil
	}
	
	var maxTemp int64 = 0
	
	for _, zonePath := range thermalZones {
		if data, err := os.ReadFile(zonePath); err == nil {
			if temp, err := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64); err == nil {
				if temp > maxTemp {
					maxTemp = temp
				}
			}
		}
	}
	
	// 온도를 섭씨로 변환 (밀리도 단위에서)
	tempC := maxTemp / 1000
	
	switch {
	case tempC > 80:
		return "critical", nil
	case tempC > 70:
		return "hot", nil
	case tempC > 60:
		return "warm", nil
	default:
		return "normal", nil
	}
}

// collectPowerManagement는 전력 관리 정보를 수집합니다.
func (c *CPUCollector) collectPowerManagement() (map[string]interface{}, error) {
	powerMgmt := make(map[string]interface{})
	
	// CPU 절전 상태 (C-states)
	if cstates, err := c.collectCStates(); err == nil {
		powerMgmt["c_states"] = cstates
	}
	
	// P-states 정보
	if pstates, err := c.collectPStates(); err == nil {
		powerMgmt["p_states"] = pstates
	}
	
	// Turbo boost 상태
	if turboBoost, err := c.collectTurboBoost(); err == nil {
		powerMgmt["turbo_boost"] = turboBoost
	}
	
	return powerMgmt, nil
}

// collectCStates는 CPU C-states 정보를 수집합니다.
func (c *CPUCollector) collectCStates() (map[string]interface{}, error) {
	cstates := make(map[string]interface{})
	
	// /sys/devices/system/cpu/cpu0/cpuidle/ 확인
	cpuidlePath := "/sys/devices/system/cpu/cpu0/cpuidle"
	if _, err := os.Stat(cpuidlePath); err != nil {
		return cstates, err
	}
	
	states, err := filepath.Glob(filepath.Join(cpuidlePath, "state*"))
	if err != nil {
		return cstates, err
	}
	
	for _, statePath := range states {
		stateName := filepath.Base(statePath)
		stateInfo := make(map[string]string)
		
		// 상태 정보 파일들 읽기
		files := []string{"name", "desc", "latency", "power", "time", "usage"}
		for _, file := range files {
			filePath := filepath.Join(statePath, file)
			if data, err := os.ReadFile(filePath); err == nil {
				stateInfo[file] = strings.TrimSpace(string(data))
			}
		}
		
		cstates[stateName] = stateInfo
	}
	
	return cstates, nil
}

// collectPStates는 CPU P-states 정보를 수집합니다.
func (c *CPUCollector) collectPStates() (map[string]interface{}, error) {
	pstates := make(map[string]interface{})
	
	// Available frequencies
	if data, err := os.ReadFile("/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies"); err == nil {
		frequencies := strings.Fields(strings.TrimSpace(string(data)))
		pstates["available_frequencies"] = frequencies
	}
	
	// Available governors
	if data, err := os.ReadFile("/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"); err == nil {
		governors := strings.Fields(strings.TrimSpace(string(data)))
		pstates["available_governors"] = governors
	}
	
	return pstates, nil
}

// collectTurboBoost는 Turbo Boost 상태를 수집합니다.
func (c *CPUCollector) collectTurboBoost() (map[string]interface{}, error) {
	turboBoost := make(map[string]interface{})
	
	// Intel Turbo Boost
	if data, err := os.ReadFile("/sys/devices/system/cpu/intel_pstate/no_turbo"); err == nil {
		value := strings.TrimSpace(string(data))
		turboBoost["intel_no_turbo"] = value
		turboBoost["intel_turbo_enabled"] = (value == "0")
	}
	
	// AMD Boost
	if data, err := os.ReadFile("/sys/devices/system/cpu/cpufreq/boost"); err == nil {
		value := strings.TrimSpace(string(data))
		turboBoost["boost"] = value
		turboBoost["boost_enabled"] = (value == "1")
	}
	
	return turboBoost, nil
}