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

// StorageCollector는 스토리지 관련 정보를 수집합니다.
type StorageCollector struct {
	*BaseCollector
}

// NewStorageCollector는 새 스토리지 수집기를 생성합니다.
func NewStorageCollector() *StorageCollector {
	return &StorageCollector{
		BaseCollector: NewBaseCollector("storage", "storage"),
	}
}

// Collect는 스토리지 관련 데이터를 수집합니다.
func (s *StorageCollector) Collect(ctx context.Context) (interface{}, error) {
	slog.Debug("스토리지 데이터 수집 시작")
	
	data := &types.StorageData{}
	
	// 1. 디스크 통계
	if diskStats, err := s.collectDiskStats(); err != nil {
		slog.Warn("디스크 통계 수집 실패", "error", err)
	} else {
		data.DiskStats = diskStats
	}
	
	// 2. 마운트 포인트
	if mounts, err := s.collectMounts(); err != nil {
		slog.Debug("마운트 정보 수집 실패", "error", err)
	} else {
		data.Mounts = mounts
	}
	
	// 3. 블록 디바이스
	if blockDevices, err := s.collectBlockDevices(); err != nil {
		slog.Debug("블록 디바이스 수집 실패", "error", err)
	} else {
		data.BlockDevices = blockDevices
	}
	
	// 4. I/O 스케줄러
	if ioScheduler, err := s.collectIOScheduler(); err != nil {
		slog.Debug("I/O 스케줄러 수집 실패", "error", err)
	} else {
		data.IOScheduler = ioScheduler
	}
	
	// 5. Read-ahead 설정
	if readAhead, err := s.collectReadAhead(); err != nil {
		slog.Debug("read-ahead 설정 수집 실패", "error", err)
	} else {
		data.ReadAhead = readAhead
	}
	
	// 6. Queue depth
	if queueDepth, err := s.collectQueueDepth(); err != nil {
		slog.Debug("queue depth 수집 실패", "error", err)
	} else {
		data.QueueDepth = queueDepth
	}
	
	// 7. 파일시스템 정보
	if filesystem, err := s.collectFileSystem(); err != nil {
		slog.Debug("파일시스템 정보 수집 실패", "error", err)
	} else {
		data.FileSystem = filesystem
	}
	
	slog.Debug("스토리지 데이터 수집 완료")
	return data, nil
}

// IsAvailable은 스토리지 수집기가 사용 가능한지 확인합니다.
func (s *StorageCollector) IsAvailable() bool {
	_, err := os.Stat("/proc/diskstats")
	return err == nil
}

// collectDiskStats는 디스크 통계를 수집합니다.
func (s *StorageCollector) collectDiskStats() (json.RawMessage, error) {
	data, err := os.ReadFile("/proc/diskstats")
	if err != nil {
		return nil, err
	}
	
	diskStats := make(map[string]interface{})
	
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		fields := strings.Fields(line)
		if len(fields) >= 14 {
			deviceName := fields[2]
			stats := map[string]interface{}{
				"major":              parseIntSafe(fields[0]),
				"minor":              parseIntSafe(fields[1]),
				"reads_completed":    parseIntSafe(fields[3]),
				"reads_merged":       parseIntSafe(fields[4]),
				"sectors_read":       parseIntSafe(fields[5]),
				"time_reading":       parseIntSafe(fields[6]),
				"writes_completed":   parseIntSafe(fields[7]),
				"writes_merged":      parseIntSafe(fields[8]),
				"sectors_written":    parseIntSafe(fields[9]),
				"time_writing":       parseIntSafe(fields[10]),
				"ios_in_progress":    parseIntSafe(fields[11]),
				"time_io":           parseIntSafe(fields[12]),
				"weighted_time_io":   parseIntSafe(fields[13]),
			}
			diskStats[deviceName] = stats
		}
	}
	
	return json.Marshal(diskStats)
}

// collectMounts는 마운트 정보를 수집합니다.
func (s *StorageCollector) collectMounts() (json.RawMessage, error) {
	data, err := os.ReadFile("/proc/mounts")
	if err != nil {
		return nil, err
	}
	
	var mounts []map[string]string
	
	lines := strings.Split(string(data), "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		fields := strings.Fields(line)
		if len(fields) >= 6 {
			mount := map[string]string{
				"device":     fields[0],
				"mountpoint": fields[1],
				"filesystem": fields[2],
				"options":    fields[3],
				"dump":       fields[4],
				"pass":       fields[5],
			}
			mounts = append(mounts, mount)
		}
	}
	
	return json.Marshal(mounts)
}

// collectBlockDevices는 블록 디바이스 정보를 수집합니다.
func (s *StorageCollector) collectBlockDevices() (json.RawMessage, error) {
	blockDevices := make(map[string]interface{})
	
	// lsblk 명령어 사용
	cmd := exec.Command("lsblk", "-J") // JSON 출력
	if output, err := cmd.Output(); err == nil {
		var lsblkData interface{}
		if err := json.Unmarshal(output, &lsblkData); err == nil {
			blockDevices["lsblk"] = lsblkData
		}
	}
	
	// /sys/block/ 정보도 수집
	if sysBlockInfo, err := s.collectSysBlockInfo(); err == nil {
		blockDevices["sysblock"] = sysBlockInfo
	}
	
	return json.Marshal(blockDevices)
}

// collectSysBlockInfo는 /sys/block/ 디렉토리에서 정보를 수집합니다.
func (s *StorageCollector) collectSysBlockInfo() (map[string]interface{}, error) {
	sysBlockInfo := make(map[string]interface{})
	
	blockDevices, err := filepath.Glob("/sys/block/*")
	if err != nil {
		return nil, err
	}
	
	for _, blockPath := range blockDevices {
		deviceName := filepath.Base(blockPath)
		deviceInfo := make(map[string]string)
		
		// 주요 정보 파일들 읽기
		infoFiles := []string{"size", "removable", "ro", "queue/scheduler"}
		for _, file := range infoFiles {
			filePath := filepath.Join(blockPath, file)
			if data, err := os.ReadFile(filePath); err == nil {
				deviceInfo[file] = strings.TrimSpace(string(data))
			}
		}
		
		sysBlockInfo[deviceName] = deviceInfo
	}
	
	return sysBlockInfo, nil
}

// collectIOScheduler는 I/O 스케줄러 설정을 수집합니다.
func (s *StorageCollector) collectIOScheduler() (map[string]string, error) {
	schedulers := make(map[string]string)
	
	blockDevices, err := filepath.Glob("/sys/block/*/queue/scheduler")
	if err != nil {
		return nil, err
	}
	
	for _, schedulerPath := range blockDevices {
		deviceName := filepath.Base(filepath.Dir(filepath.Dir(schedulerPath)))
		
		if data, err := os.ReadFile(schedulerPath); err == nil {
			scheduleInfo := strings.TrimSpace(string(data))
			// [mq-deadline] none kyber 형식에서 현재 스케줄러 추출
			if start := strings.Index(scheduleInfo, "["); start != -1 {
				if end := strings.Index(scheduleInfo[start:], "]"); end != -1 {
					currentScheduler := scheduleInfo[start+1 : start+end]
					schedulers[deviceName] = currentScheduler
				}
			}
		}
	}
	
	return schedulers, nil
}

// collectReadAhead는 read-ahead 설정을 수집합니다.
func (s *StorageCollector) collectReadAhead() (map[string]int, error) {
	readAhead := make(map[string]int)
	
	blockDevices, err := filepath.Glob("/sys/block/*/queue/read_ahead_kb")
	if err != nil {
		return nil, err
	}
	
	for _, readAheadPath := range blockDevices {
		deviceName := filepath.Base(filepath.Dir(filepath.Dir(readAheadPath)))
		
		if data, err := os.ReadFile(readAheadPath); err == nil {
			if value, err := strconv.Atoi(strings.TrimSpace(string(data))); err == nil {
				readAhead[deviceName] = value
			}
		}
	}
	
	return readAhead, nil
}

// collectQueueDepth는 큐 깊이 설정을 수집합니다.
func (s *StorageCollector) collectQueueDepth() (map[string]int, error) {
	queueDepth := make(map[string]int)
	
	blockDevices, err := filepath.Glob("/sys/block/*/queue/nr_requests")
	if err != nil {
		return nil, err
	}
	
	for _, queuePath := range blockDevices {
		deviceName := filepath.Base(filepath.Dir(filepath.Dir(queuePath)))
		
		if data, err := os.ReadFile(queuePath); err == nil {
			if value, err := strconv.Atoi(strings.TrimSpace(string(data))); err == nil {
				queueDepth[deviceName] = value
			}
		}
	}
	
	return queueDepth, nil
}

// collectFileSystem는 파일시스템 정보를 수집합니다.
func (s *StorageCollector) collectFileSystem() (map[string]interface{}, error) {
	filesystem := make(map[string]interface{})
	
	// df 명령어로 디스크 사용량 수집
	cmd := exec.Command("df", "-h")
	if output, err := cmd.Output(); err == nil {
		filesystem["disk_usage"] = s.parseDfOutput(string(output))
	}
	
	// 파일시스템별 매개변수 수집
	if fsParams, err := s.collectFileSystemParams(); err == nil {
		filesystem["parameters"] = fsParams
	}
	
	return filesystem, nil
}

// parseDfOutput는 df 명령어 출력을 파싱합니다.
func (s *StorageCollector) parseDfOutput(output string) []map[string]string {
	var result []map[string]string
	
	lines := strings.Split(output, "\n")
	if len(lines) < 2 {
		return result
	}
	
	// 헤더 스킵
	for _, line := range lines[1:] {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		fields := strings.Fields(line)
		if len(fields) >= 6 {
			usage := map[string]string{
				"filesystem": fields[0],
				"size":       fields[1],
				"used":       fields[2],
				"available":  fields[3],
				"use_pct":    fields[4],
				"mountpoint": fields[5],
			}
			result = append(result, usage)
		}
	}
	
	return result
}

// collectFileSystemParams는 파일시스템 매개변수를 수집합니다.
func (s *StorageCollector) collectFileSystemParams() (map[string]interface{}, error) {
	params := make(map[string]interface{})
	
	// /proc/sys/fs/ 디렉토리의 매개변수들
	fsParams := map[string]string{
		"file_max":           "/proc/sys/fs/file-max",
		"file_nr":            "/proc/sys/fs/file-nr",
		"inode_nr":           "/proc/sys/fs/inode-nr",
		"aio_max_nr":         "/proc/sys/fs/aio-max-nr",
		"aio_nr":             "/proc/sys/fs/aio-nr",
	}
	
	for key, path := range fsParams {
		if data, err := os.ReadFile(path); err == nil {
			value := strings.TrimSpace(string(data))
			if intVal, err := strconv.Atoi(value); err == nil {
				params[key] = intVal
			} else {
				params[key] = value
			}
		}
	}
	
	return params, nil
}