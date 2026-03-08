package collector

import (
	"context"
	"encoding/json"
	"log/slog"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/ecmoce/infra-auditor/pkg/types"
)

// MemoryCollector는 메모리 관련 정보를 수집합니다.
type MemoryCollector struct {
	*BaseCollector
}

// NewMemoryCollector는 새 메모리 수집기를 생성합니다.
func NewMemoryCollector() *MemoryCollector {
	return &MemoryCollector{
		BaseCollector: NewBaseCollector("memory", "memory"),
	}
}

// Collect는 메모리 관련 데이터를 수집합니다.
func (m *MemoryCollector) Collect(ctx context.Context) (interface{}, error) {
	slog.Debug("메모리 데이터 수집 시작")
	
	data := &types.MemoryData{}
	
	// 1. /proc/meminfo 수집
	if memInfo, err := m.collectMemInfo(); err != nil {
		slog.Warn("meminfo 수집 실패", "error", err)
	} else {
		data.MemInfo = memInfo
	}
	
	// 2. /proc/vmstat 수집
	if vmStat, err := m.collectVmStat(); err != nil {
		slog.Debug("vmstat 수집 실패", "error", err)
	} else {
		data.VmStat = vmStat
	}
	
	// 3. Swappiness 설정
	if swappiness, err := m.collectSwappiness(); err != nil {
		slog.Debug("swappiness 수집 실패", "error", err)
	} else {
		data.Swappiness = swappiness
	}
	
	// 4. HugePages 정보
	if hugePagesTotal, hugePagesFree, hugePagesSize, err := m.collectHugePages(); err != nil {
		slog.Debug("hugepages 수집 실패", "error", err)
	} else {
		data.HugePagesTotal = hugePagesTotal
		data.HugePagesFree = hugePagesFree
		data.HugePagesSize = hugePagesSize
	}
	
	// 5. NUMA 통계
	if numaStats, err := m.collectNUMAStats(); err != nil {
		slog.Debug("NUMA stats 수집 실패", "error", err)
	} else {
		data.NumaStats = numaStats
	}
	
	// 6. OOM Kill 카운트
	if oomKillCount, err := m.collectOOMKillCount(); err != nil {
		slog.Debug("OOM kill count 수집 실패", "error", err)
	} else {
		data.OOMKillCount = oomKillCount
	}
	
	// 7. cgroups 정보
	if cgroups, err := m.collectCgroups(); err != nil {
		slog.Debug("cgroups 수집 실패", "error", err)
	} else {
		data.Cgroups = cgroups
	}
	
	slog.Debug("메모리 데이터 수집 완료")
	return data, nil
}

// IsAvailable은 메모리 수집기가 사용 가능한지 확인합니다.
func (m *MemoryCollector) IsAvailable() bool {
	_, err := os.Stat("/proc/meminfo")
	return err == nil
}

// collectMemInfo는 /proc/meminfo 내용을 수집합니다.
func (m *MemoryCollector) collectMemInfo() (json.RawMessage, error) {
	data, err := os.ReadFile("/proc/meminfo")
	if err != nil {
		return nil, err
	}
	
	// meminfo를 구조화된 데이터로 파싱
	memInfo := make(map[string]interface{})
	
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		parts := strings.Fields(line)
		if len(parts) >= 2 {
			key := strings.TrimSuffix(parts[0], ":")
			valueStr := parts[1]
			
			// 숫자로 변환 시도
			if value, err := strconv.ParseInt(valueStr, 10, 64); err == nil {
				memInfo[key] = value
				// 단위가 있는 경우 추가 정보 저장
				if len(parts) >= 3 {
					memInfo[key+"_unit"] = parts[2]
				}
			} else {
				memInfo[key] = valueStr
			}
		}
	}
	
	return json.Marshal(memInfo)
}

// collectVmStat는 /proc/vmstat 내용을 수집합니다.
func (m *MemoryCollector) collectVmStat() (json.RawMessage, error) {
	data, err := os.ReadFile("/proc/vmstat")
	if err != nil {
		return nil, err
	}
	
	vmStat := make(map[string]interface{})
	
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		parts := strings.Fields(line)
		if len(parts) >= 2 {
			key := parts[0]
			if value, err := strconv.ParseInt(parts[1], 10, 64); err == nil {
				vmStat[key] = value
			} else {
				vmStat[key] = parts[1]
			}
		}
	}
	
	return json.Marshal(vmStat)
}

// collectSwappiness는 vm.swappiness 설정값을 수집합니다.
func (m *MemoryCollector) collectSwappiness() (int, error) {
	data, err := os.ReadFile("/proc/sys/vm/swappiness")
	if err != nil {
		return 0, err
	}
	
	value, err := strconv.Atoi(strings.TrimSpace(string(data)))
	if err != nil {
		return 0, err
	}
	
	return value, nil
}

// collectHugePages는 HugePages 설정 정보를 수집합니다.
func (m *MemoryCollector) collectHugePages() (int, int, int, error) {
	var total, free, size int
	var err error
	
	// HugePages_Total
	if data, readErr := os.ReadFile("/proc/sys/vm/nr_hugepages"); readErr == nil {
		if total, err = strconv.Atoi(strings.TrimSpace(string(data))); err != nil {
			total = 0
		}
	}
	
	// HugePages_Free (meminfo에서 추출)
	if data, readErr := os.ReadFile("/proc/meminfo"); readErr == nil {
		lines := strings.Split(string(data), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, "HugePages_Free:") {
				fields := strings.Fields(line)
				if len(fields) >= 2 {
					if freePages, err := strconv.Atoi(fields[1]); err == nil {
						free = freePages
					}
				}
				break
			}
		}
	}
	
	// Hugepagesize
	if data, readErr := os.ReadFile("/proc/meminfo"); readErr == nil {
		lines := strings.Split(string(data), "\n")
		for _, line := range lines {
			if strings.HasPrefix(line, "Hugepagesize:") {
				fields := strings.Fields(line)
				if len(fields) >= 2 {
					if hugepageSize, err := strconv.Atoi(fields[1]); err == nil {
						size = hugepageSize
					}
				}
				break
			}
		}
	}
	
	return total, free, size, nil
}

// collectNUMAStats는 NUMA 관련 통계를 수집합니다.
func (m *MemoryCollector) collectNUMAStats() (json.RawMessage, error) {
	numaStats := make(map[string]interface{})
	
	// /proc/numastat 확인
	if data, err := os.ReadFile("/proc/numastat"); err == nil {
		numaStats["numastat"] = m.parseNUMAStat(string(data))
	}
	
	// /sys/devices/system/node/ 디렉토리에서 NUMA 노드 정보 수집
	nodePattern := "/sys/devices/system/node/node*"
	if nodes, err := filepath.Glob(nodePattern); err == nil && len(nodes) > 0 {
		nodeInfo := make(map[string]interface{})
		
		for _, nodePath := range nodes {
			nodeName := filepath.Base(nodePath)
			nodeData := make(map[string]interface{})
			
			// meminfo
			if data, err := os.ReadFile(filepath.Join(nodePath, "meminfo")); err == nil {
				nodeData["meminfo"] = m.parseNodeMemInfo(string(data))
			}
			
			// cpulist
			if data, err := os.ReadFile(filepath.Join(nodePath, "cpulist")); err == nil {
				nodeData["cpulist"] = strings.TrimSpace(string(data))
			}
			
			nodeInfo[nodeName] = nodeData
		}
		
		numaStats["nodes"] = nodeInfo
	}
	
	return json.Marshal(numaStats)
}

// parseNUMAStat는 /proc/numastat 내용을 파싱합니다.
func (m *MemoryCollector) parseNUMAStat(data string) map[string]interface{} {
	result := make(map[string]interface{})
	
	lines := strings.Split(data, "\n")
	if len(lines) < 2 {
		return result
	}
	
	// 첫 번째 줄은 헤더 (노드 이름들)
	headers := strings.Fields(lines[0])
	
	// 나머지 줄들은 통계 데이터
	for _, line := range lines[1:] {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		
		statName := fields[0]
		statData := make(map[string]interface{})
		
		// 각 노드별 값 저장
		for i := 1; i < len(fields) && i-1 < len(headers); i++ {
			if value, err := strconv.ParseInt(fields[i], 10, 64); err == nil {
				if i-1 < len(headers) {
					statData[headers[i-1]] = value
				}
			}
		}
		
		result[statName] = statData
	}
	
	return result
}

// parseNodeMemInfo는 NUMA 노드의 meminfo를 파싱합니다.
func (m *MemoryCollector) parseNodeMemInfo(data string) map[string]interface{} {
	result := make(map[string]interface{})
	
	lines := strings.Split(data, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || !strings.Contains(line, ":") {
			continue
		}
		
		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			continue
		}
		
		key := strings.TrimSpace(parts[0])
		valueStr := strings.TrimSpace(parts[1])
		
		// "Node X " 접두어 제거
		if strings.HasPrefix(key, "Node ") {
			if spaceIdx := strings.Index(key[5:], " "); spaceIdx != -1 {
				key = strings.TrimSpace(key[5+spaceIdx+1:])
			}
		}
		
		fields := strings.Fields(valueStr)
		if len(fields) > 0 {
			if value, err := strconv.ParseInt(fields[0], 10, 64); err == nil {
				result[key] = value
				if len(fields) > 1 {
					result[key+"_unit"] = fields[1]
				}
			}
		}
	}
	
	return result
}

// collectOOMKillCount는 OOM killer 발생 횟수를 수집합니다.
func (m *MemoryCollector) collectOOMKillCount() (int, error) {
	// /proc/vmstat에서 oom_kill 카운터 확인
	data, err := os.ReadFile("/proc/vmstat")
	if err != nil {
		return 0, err
	}
	
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		if strings.HasPrefix(line, "oom_kill ") {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				if count, err := strconv.Atoi(fields[1]); err == nil {
					return count, nil
				}
			}
		}
	}
	
	// vmstat에 없으면 dmesg에서 OOM 메시지 카운트
	cmd := exec.Command("dmesg", "--time-format", "iso")
	output, err := cmd.Output()
	if err != nil {
		return 0, err
	}
	
	oomCount := 0
	lines = strings.Split(string(output), "\n")
	for _, line := range lines {
		if strings.Contains(line, "Out of memory") || 
		   strings.Contains(line, "oom-killer") ||
		   strings.Contains(line, "Killed process") {
			oomCount++
		}
	}
	
	return oomCount, nil
}

// collectCgroups는 cgroups 메모리 관련 정보를 수집합니다.
func (m *MemoryCollector) collectCgroups() (map[string]interface{}, error) {
	cgroups := make(map[string]interface{})
	
	// cgroups v1 메모리 정보
	if cgroupsV1, err := m.collectCgroupsV1(); err == nil && len(cgroupsV1) > 0 {
		cgroups["v1"] = cgroupsV1
	}
	
	// cgroups v2 메모리 정보
	if cgroupsV2, err := m.collectCgroupsV2(); err == nil && len(cgroupsV2) > 0 {
		cgroups["v2"] = cgroupsV2
	}
	
	return cgroups, nil
}

// collectCgroupsV1는 cgroups v1 메모리 정보를 수집합니다.
func (m *MemoryCollector) collectCgroupsV1() (map[string]interface{}, error) {
	cgroupsV1 := make(map[string]interface{})
	
	// /sys/fs/cgroup/memory 확인
	memoryRoot := "/sys/fs/cgroup/memory"
	if _, err := os.Stat(memoryRoot); err != nil {
		return cgroupsV1, err
	}
	
	// memory.stat 파일 읽기
	if data, err := os.ReadFile(filepath.Join(memoryRoot, "memory.stat")); err == nil {
		cgroupsV1["memory_stat"] = m.parseCgroupMemoryStat(string(data))
	}
	
	// memory.usage_in_bytes
	if data, err := os.ReadFile(filepath.Join(memoryRoot, "memory.usage_in_bytes")); err == nil {
		if usage, err := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64); err == nil {
			cgroupsV1["usage_in_bytes"] = usage
		}
	}
	
	// memory.limit_in_bytes
	if data, err := os.ReadFile(filepath.Join(memoryRoot, "memory.limit_in_bytes")); err == nil {
		if limit, err := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64); err == nil {
			cgroupsV1["limit_in_bytes"] = limit
		}
	}
	
	return cgroupsV1, nil
}

// collectCgroupsV2는 cgroups v2 메모리 정보를 수집합니다.
func (m *MemoryCollector) collectCgroupsV2() (map[string]interface{}, error) {
	cgroupsV2 := make(map[string]interface{})
	
	// /sys/fs/cgroup/memory.current 확인 (cgroups v2)
	memoryCurrentPath := "/sys/fs/cgroup/memory.current"
	if data, err := os.ReadFile(memoryCurrentPath); err == nil {
		if current, err := strconv.ParseInt(strings.TrimSpace(string(data)), 10, 64); err == nil {
			cgroupsV2["current"] = current
		}
	}
	
	// /sys/fs/cgroup/memory.max
	if data, err := os.ReadFile("/sys/fs/cgroup/memory.max"); err == nil {
		maxValue := strings.TrimSpace(string(data))
		if maxValue == "max" {
			cgroupsV2["max"] = "unlimited"
		} else if max, err := strconv.ParseInt(maxValue, 10, 64); err == nil {
			cgroupsV2["max"] = max
		}
	}
	
	// /sys/fs/cgroup/memory.stat
	if data, err := os.ReadFile("/sys/fs/cgroup/memory.stat"); err == nil {
		cgroupsV2["stat"] = m.parseCgroupMemoryStat(string(data))
	}
	
	return cgroupsV2, nil
}

// parseCgroupMemoryStat는 cgroup memory.stat 파일을 파싱합니다.
func (m *MemoryCollector) parseCgroupMemoryStat(data string) map[string]interface{} {
	result := make(map[string]interface{})
	
	lines := strings.Split(data, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		parts := strings.Fields(line)
		if len(parts) >= 2 {
			key := parts[0]
			if value, err := strconv.ParseInt(parts[1], 10, 64); err == nil {
				result[key] = value
			} else {
				result[key] = parts[1]
			}
		}
	}
	
	return result
}